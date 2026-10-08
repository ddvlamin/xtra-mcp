import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Union, Any, Tuple
from pydantic import BaseModel, Field

from xtra.models import Product, ExtractedIngredient
from xtra.colruyt import ColruytClient
from xtra.db import Database
from xtra.logic import (
    resolve_ingredient,
    store_resolved_product,
    extract_ingredients_section,
    extract_ingredients_with_llm,
)
from xtra.formatting import (
    format_ingredient_label,
    format_ambiguous_options_markdown,
    format_resolved_products_list,
    append_or_update_recipe_section,
    format_session_progress_presentation,
)

class SessionItemStatus(str, Enum):
    UNRESOLVED = "unresolved"
    AWAITING_SELECTION = "awaiting_selection"
    RESOLVED = "resolved"

class SessionIngredient(BaseModel):
    name: str
    query: str
    quantity: Optional[Union[float, int, str]] = None
    unit: Optional[str] = None
    status: SessionItemStatus = SessionItemStatus.UNRESOLVED
    resolved_product: Optional[Product] = None
    candidate_products: List[Product] = Field(default_factory=list)
    current_offset: int = 0

class RecipeSession(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    recipe_filename: Optional[str] = None
    ingredients: List[SessionIngredient] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def total_count(self) -> int:
        return len(self.ingredients)

    @property
    def resolved_count(self) -> int:
        return sum(1 for item in self.ingredients if item.status == SessionItemStatus.RESOLVED)

    @property
    def remaining_count(self) -> int:
        return self.total_count - self.resolved_count

    @property
    def is_completed(self) -> bool:
        return self.remaining_count == 0 and self.total_count > 0

    def get_active_item_index(self) -> Optional[int]:
        for idx, item in enumerate(self.ingredients):
            if item.status in (SessionItemStatus.UNRESOLVED, SessionItemStatus.AWAITING_SELECTION):
                return idx
        return None

    def get_active_item(self) -> Optional[SessionIngredient]:
        idx = self.get_active_item_index()
        return self.ingredients[idx] if idx is not None else None

class SessionManager:
    """In-memory manager for active ingredient resolution sessions."""
    def __init__(self):
        self.sessions: Dict[str, RecipeSession] = {}

    def get_session(self, session_id: str) -> Optional[RecipeSession]:
        return self.sessions.get(session_id)

    def create_session(
        self,
        ingredients: List[SessionIngredient],
        recipe_filename: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> RecipeSession:
        sid = session_id or str(uuid.uuid4())[:8]
        session = RecipeSession(
            session_id=sid,
            recipe_filename=recipe_filename,
            ingredients=ingredients
        )
        self.sessions[sid] = session
        return session

    def delete_session(self, session_id: str) -> bool:
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False

# Global in-memory session manager
session_manager = SessionManager()

async def start_resolution_session(
    ingredients: Optional[List[Union[str, Dict[str, Any]]]] = None,
    recipe_filename: Optional[str] = None,
    recipe_content: Optional[str] = None,
    session_id: Optional[str] = None,
    client: Optional[ColruytClient] = None,
    db: Optional[Database] = None,
    limit: int = 5
) -> Dict[str, Any]:
    """Initializes a recipe / ingredient resolution session and resolves unambiguous items."""
    import os
    if db is None:
        db = Database()

    extracted: List[ExtractedIngredient] = []
    if recipe_content or recipe_filename:
        content = recipe_content
        if not content and recipe_filename:
            if not os.path.exists(recipe_filename):
                return {"status": "error", "error": f"Recipe file '{recipe_filename}' not found."}
            with open(recipe_filename, "r", encoding="utf-8") as f:
                content = f.read()

        ingredients_section = extract_ingredients_section(content or "")
        if not ingredients_section:
            return {"status": "error", "error": "No '## Ingredients' or '## Ingrediënten' section found in the recipe."}
        try:
            extracted = await extract_ingredients_with_llm(ingredients_section)
        except Exception as e:
            return {"status": "error", "error": f"Failed to extract ingredients with LLM: {e}"}
    elif ingredients:
        for item in ingredients:
            if isinstance(item, str):
                extracted.append(ExtractedIngredient(name=item))
            elif isinstance(item, dict):
                extracted.append(ExtractedIngredient(**item))

    if not extracted:
        return {"status": "error", "error": "No ingredients found or provided to resolve."}

    session_items: List[SessionIngredient] = []
    for ing in extracted:
        query, resolved = await resolve_ingredient(ing.name, client=client, db=db)
        if isinstance(resolved, Product):
            session_items.append(SessionIngredient(
                name=ing.name,
                query=query,
                quantity=ing.quantity,
                unit=ing.unit,
                status=SessionItemStatus.RESOLVED,
                resolved_product=resolved
            ))
        elif isinstance(resolved, list):
            session_items.append(SessionIngredient(
                name=ing.name,
                query=query,
                quantity=ing.quantity,
                unit=ing.unit,
                status=SessionItemStatus.AWAITING_SELECTION,
                candidate_products=resolved
            ))
        else:
            session_items.append(SessionIngredient(
                name=ing.name,
                query=query,
                quantity=ing.quantity,
                unit=ing.unit,
                status=SessionItemStatus.AWAITING_SELECTION,
                candidate_products=[]
            ))

    session = session_manager.create_session(
        ingredients=session_items,
        recipe_filename=recipe_filename,
        session_id=session_id
    )

    active_item = session.get_active_item()
    if session.is_completed:
        if recipe_filename and os.path.exists(recipe_filename):
            with open(recipe_filename, "r", encoding="utf-8") as f:
                content = f.read()
            resolved_tuples = [
                (ExtractedIngredient(name=it.name, quantity=it.quantity, unit=it.unit), it.resolved_product)
                for it in session.ingredients if it.resolved_product
            ]
            prod_list_md = format_resolved_products_list(resolved_tuples)
            updated = append_or_update_recipe_section(content, "Resolved Products", prod_list_md)
            with open(recipe_filename, "w", encoding="utf-8") as f:
                f.write(updated)

        return {
            "status": "completed",
            "session_id": session.session_id,
            "total_count": session.total_count,
            "resolved_count": session.resolved_count,
            "remaining_count": 0,
            "resolved": [
                {"ingredient": it.name, "product": it.resolved_product.model_dump() if it.resolved_product else None}
                for it in session.ingredients
            ],
            "presentation_markdown": format_session_progress_presentation(session, None, limit)
        }

    paged = active_item.candidate_products[0:limit] if active_item else []
    has_more = len(active_item.candidate_products) > limit if active_item else False

    return {
        "status": "in_progress",
        "session_id": session.session_id,
        "total_count": session.total_count,
        "resolved_count": session.resolved_count,
        "remaining_count": session.remaining_count,
        "active_ingredient": {
            "name": active_item.name,
            "query": active_item.query,
            "step": (session.get_active_item_index() or 0) + 1,
            "total": session.total_count,
            "results": [p.model_dump() for p in paged],
            "pagination": {
                "offset": 0,
                "limit": limit,
                "total_matches": len(active_item.candidate_products),
                "has_more": has_more,
                "next_offset": limit if has_more else None
            }
        },
        "presentation_markdown": format_session_progress_presentation(session, active_item, limit)
    }

async def resolve_session_ingredient_choice(
    session_id: str,
    selected_product_id: str,
    ingredient_name: Optional[str] = None,
    selected_option_index: Optional[int] = None,
    client: Optional[ColruytClient] = None,
    db: Optional[Database] = None,
    limit: int = 5
) -> Dict[str, Any]:
    """Locks in product choice for active ingredient, saves to SQLite, and advances to next."""
    import os
    if db is None:
        db = Database()

    session = session_manager.get_session(session_id)
    if not session:
        return {"status": "error", "error": f"Session '{session_id}' not found."}

    active_item = None
    if ingredient_name:
        for it in session.ingredients:
            if it.name.lower() == ingredient_name.lower() and it.status != SessionItemStatus.RESOLVED:
                active_item = it
                break

    if not active_item:
        active_item = session.get_active_item()

    if not active_item:
        return {
            "status": "completed",
            "session_id": session.session_id,
            "message": "All ingredients in this session are already resolved.",
            "total_count": session.total_count,
            "resolved_count": session.resolved_count,
            "remaining_count": 0,
            "presentation_markdown": format_session_progress_presentation(session, None, limit)
        }

    # Find matching product in candidates or fetch
    chosen_product: Optional[Product] = None
    if selected_option_index is not None and 1 <= selected_option_index <= len(active_item.candidate_products):
        chosen_product = active_item.candidate_products[selected_option_index - 1]
    else:
        for p in active_item.candidate_products:
            if p.product_id == selected_product_id:
                chosen_product = p
                break

    if not chosen_product:
        # Fallback: create product reference with selected_product_id
        chosen_product = Product(
            product_id=selected_product_id,
            name=active_item.name,
            query=active_item.query
        )

    # Persist in DB
    stored = await store_resolved_product(
        ingredient=active_item.name,
        product_id=chosen_product.product_id,
        name=chosen_product.name,
        brand=chosen_product.brand,
        client=client,
        top_category_name=chosen_product.top_category_name,
        db=db
    )

    active_item.status = SessionItemStatus.RESOLVED
    active_item.resolved_product = stored

    # Check if session is now complete
    if session.is_completed:
        if session.recipe_filename and os.path.exists(session.recipe_filename):
            with open(session.recipe_filename, "r", encoding="utf-8") as f:
                content = f.read()
            resolved_tuples = [
                (ExtractedIngredient(name=it.name, quantity=it.quantity, unit=it.unit), it.resolved_product)
                for it in session.ingredients if it.resolved_product
            ]
            prod_list_md = format_resolved_products_list(resolved_tuples)
            updated = append_or_update_recipe_section(content, "Resolved Products", prod_list_md)
            with open(session.recipe_filename, "w", encoding="utf-8") as f:
                f.write(updated)

        return {
            "status": "completed",
            "session_id": session.session_id,
            "total_count": session.total_count,
            "resolved_count": session.resolved_count,
            "remaining_count": 0,
            "resolved": [
                {"ingredient": it.name, "product": it.resolved_product.model_dump() if it.resolved_product else None}
                for it in session.ingredients
            ],
            "presentation_markdown": format_session_progress_presentation(session, None, limit)
        }

    # Next active ingredient
    next_item = session.get_active_item()
    paged = next_item.candidate_products[0:limit] if next_item else []
    has_more = len(next_item.candidate_products) > limit if next_item else False

    return {
        "status": "in_progress",
        "session_id": session.session_id,
        "total_count": session.total_count,
        "resolved_count": session.resolved_count,
        "remaining_count": session.remaining_count,
        "next_ingredient": {
            "name": next_item.name,
            "query": next_item.query,
            "step": (session.get_active_item_index() or 0) + 1,
            "total": session.total_count,
            "results": [p.model_dump() for p in paged],
            "pagination": {
                "offset": 0,
                "limit": limit,
                "total_matches": len(next_item.candidate_products),
                "has_more": has_more,
                "next_offset": limit if has_more else None
            }
        },
        "presentation_markdown": format_session_progress_presentation(session, next_item, limit)
    }

async def paginate_session_ingredient(
    session_id: str,
    ingredient_name: Optional[str] = None,
    offset: int = 0,
    limit: int = 5
) -> Dict[str, Any]:
    """Paginates the candidate product options for active ingredient."""
    session = session_manager.get_session(session_id)
    if not session:
        return {"status": "error", "error": f"Session '{session_id}' not found."}

    active_item = None
    if ingredient_name:
        for it in session.ingredients:
            if it.name.lower() == ingredient_name.lower():
                active_item = it
                break

    if not active_item:
        active_item = session.get_active_item()

    if not active_item:
        return {"status": "error", "error": "No active ingredient found in session."}

    active_item.current_offset = max(0, offset)
    paged = active_item.candidate_products[active_item.current_offset : active_item.current_offset + limit]
    has_more = (active_item.current_offset + limit) < len(active_item.candidate_products)
    next_offset = active_item.current_offset + limit if has_more else None

    return {
        "status": "in_progress",
        "session_id": session.session_id,
        "ingredient": {
            "name": active_item.name,
            "query": active_item.query,
            "step": (session.get_active_item_index() or 0) + 1,
            "total": session.total_count,
            "results": [p.model_dump() for p in paged],
            "pagination": {
                "offset": active_item.current_offset,
                "limit": limit,
                "total_matches": len(active_item.candidate_products),
                "has_more": has_more,
                "next_offset": next_offset
            }
        },
        "presentation_markdown": format_session_progress_presentation(session, active_item, limit)
    }
