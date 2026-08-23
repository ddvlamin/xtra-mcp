import re
from dataclasses import dataclass
from typing import List, Optional, Union, Tuple
from xtra.models import Product, ExtractedIngredient
from xtra.client import SupermarketClient
from xtra.db import Database
from xtra.extractor import (
    IngredientExtractor,
    LLMIngredientExtractor,
    BaseIngredientExtractor,
    ExtractionError
)

@dataclass
class RecipeResolutionResult:
    """Encapsulates the outcome of resolving all ingredients in a recipe."""
    resolved: List[Tuple[ExtractedIngredient, Product]]
    ambiguous: List[Tuple[ExtractedIngredient, str, List[Product]]]
    not_found: List[Tuple[ExtractedIngredient, str]]

    @property
    def is_complete(self) -> bool:
        return len(self.ambiguous) == 0 and len(self.not_found) == 0

    @property
    def total_count(self) -> int:
        return len(self.resolved) + len(self.ambiguous) + len(self.not_found)

    @property
    def resolved_count(self) -> int:
        return len(self.resolved)

def format_ingredient_label(item: Union[ExtractedIngredient, dict, str]) -> str:
    """Formats an ingredient object into a readable label with quantity and unit."""
    if isinstance(item, ExtractedIngredient):
        name = item.name
        qty = item.quantity
        unit = item.unit
    elif isinstance(item, dict):
        name = item.get("name", "")
        qty = item.get("quantity")
        unit = item.get("unit")
    else:
        return str(item)

    qty_str = ""
    if qty is not None and unit is not None:
        qty_str = f" ({qty} {unit})"
    elif qty is not None:
        qty_str = f" ({qty})"
    elif unit is not None:
        qty_str = f" ({unit})"

    return f"{name}{qty_str}"

def extract_ingredients_section(md_content: str) -> str:
    """Extracts raw text under the Ingredients/Ingrediënten heading in a recipe."""
    match = re.search(r"##\s*(?:[^\w\s]+\s*)?(?:Ingrediënten|Ingredients)\s*\n(.*?)(?:\n##|\Z)", md_content, re.DOTALL | re.IGNORECASE)
    if not match:
        return ""
    return match.group(1).strip()

async def extract_ingredients_with_llm(
    ingredients_text: str,
    host: Optional[str] = None,
    model: Optional[str] = None,
    timeout: Optional[float] = None
) -> List[ExtractedIngredient]:
    """Extracts structured ingredient objects using local qwen2.5:3b LLM via IngredientExtractor.

    Raises ExtractionError on connection failure or invalid LLM response.
    """
    extractor = IngredientExtractor(host=host, model=model, timeout=timeout)
    return await extractor.extract(ingredients_text)

async def resolve_ingredient(
    ingredient: str,
    client: SupermarketClient,
    db: Optional[Database] = None
) -> Tuple[str, Union[Product, List[Product]]]:
    """Resolves an ingredient string to a Product using database fuzzy matching and search.
    Returns a tuple of (normalized_ingredient, Product | List[Product]).
    """
    if db is None:
        db = Database()

    query = ingredient.strip()
    
    # 1. Database fuzzy matching lookup (threshold >= 80)
    fuzzy_match = db.find_product(query, score_threshold=80)
    if fuzzy_match:
        return query, fuzzy_match

    # 2. Live search API
    search_results = await client.search_products(query)
    if not search_results:
        return query, []

    resolved_product: Optional[Product] = None

    if len(search_results) == 1:
        resolved_product = search_results[0]
    else:
        return query, search_results

    # 3. Fetch product info via client & store product in DB
    if resolved_product:
        gtin = resolved_product.gtin[0] if (resolved_product.gtin and len(resolved_product.gtin) > 0) else None # TODO: gtin is probably still Colruyt specific
        product_info = await client.get_product_info(resolved_product.product_id, gtin=gtin)
        
        resolved_product.query = query
        resolved_product.description = product_info.get("product_description")
        resolved_product.conservation_info = product_info.get("conservation_info")
        resolved_product.usage_info = product_info.get("usage_info")
        if product_info.get("content"):
            resolved_product.content = product_info.get("content")

        stored = db.store_product(resolved_product)
        return query, stored

    return query, []

async def store_resolved_product(
    ingredient: str,
    product_id: str,
    name: str,
    brand: Optional[str] = None,
    client: Optional[SupermarketClient] = None,
    db: Optional[Database] = None,
    top_category_name: Optional[str] = None
) -> Product:
    """Stores a chosen product resolution into the local SQLite database.

    Args:
        ingredient: String representing the search query/ingredient.
        product_id: Selected Colruyt product ID.
        name: Name of the product.
        brand: Optional brand name.
        client: Optional SupermarketClient instance to fetch additional details.
        db: Optional Database instance.
        top_category_name: Optional top category name.
    """
    if db is None:
        db = Database()

    product = Product(
        query=ingredient,
        product_id=product_id,
        name=name,
        brand=brand,
        top_category_name=top_category_name
    )

    if client:
        try:
            product_info = await client.get_product_info(product_id)
            product.description = product_info.get("product_description")
            product.conservation_info = product_info.get("conservation_info")
            product.usage_info = product_info.get("usage_info")
            if product_info.get("content"):
                product.content = product_info.get("content")
        except Exception:
            pass

    return db.store_product(product)

async def resolve_recipe_ingredients(
    content: str,
    client: SupermarketClient,
    db: Optional[Database] = None
) -> Tuple[Optional[str], Optional[RecipeResolutionResult]]:
    """Extracts ingredients from recipe markdown and resolves each against Colruyt/DB.
    Returns (error_message, RecipeResolutionResult).
    """
    ingredients_section = extract_ingredients_section(content)
    if not ingredients_section:
        return "No '## Ingredients' or '## Ingrediënten' section found in the recipe.", None

    try:
        extracted_ingredients = await extract_ingredients_with_llm(ingredients_section)
    except Exception as e:
        return f"Failed to extract ingredients from recipe: {e}", None

    if not extracted_ingredients:
        return "Could not extract any ingredients from the recipe.", None

    resolved = []
    ambiguous = []
    not_found = []

    for item in extracted_ingredients:
        query, res = await resolve_ingredient(item.name, client, db=db)
        if isinstance(res, Product):
            resolved.append((item, res))
        elif isinstance(res, list) and res:
            ambiguous.append((item, query, res))
        else:
            not_found.append((item, query))

    result = RecipeResolutionResult(resolved=resolved, ambiguous=ambiguous, not_found=not_found)
    return None, result

def format_resolved_products_list(
    resolved_items: List[Tuple[ExtractedIngredient, Product]]
) -> str:
    """Formats resolved products into markdown bullet list items with [productId=...]."""
    lines = []
    for ing, prod in resolved_items:
        label = format_ingredient_label(ing)
        lines.append(f"- {label} [productId={prod.product_id}]")
    return "\n".join(lines)

def append_or_update_recipe_section(
    recipe_content: str,
    section_title: str,
    section_body: str
) -> str:
    """Appends or cleanly updates a markdown section in recipe content."""
    pattern = rf"##\s*{re.escape(section_title)}\s*\n.*?(?=\n##|\Z)"
    new_section = f"## {section_title}\n{section_body.strip()}\n"
    if re.search(pattern, recipe_content, flags=re.DOTALL):
        return re.sub(pattern, new_section.strip(), recipe_content, flags=re.DOTALL).rstrip() + "\n"
    else:
        trimmed = recipe_content.rstrip()
        return f"{trimmed}\n\n{new_section}"

def format_resolution_progress(
    result: RecipeResolutionResult,
    offset: int = 0
) -> str:
    """Formats resolution progress and prompts for ambiguous ingredients."""
    lines = []
    for ing, prod in result.resolved:
        label = format_ingredient_label(ing)
        lines.append(f"✅ {label} -> {prod.name} [productId={prod.product_id}]")
    for ing, _, _ in result.ambiguous:
        label = format_ingredient_label(ing)
        lines.append(f"❓ {label} (Ambiguous)")
    for ing, _ in result.not_found:
        label = format_ingredient_label(ing)
        lines.append(f"❌ {label} (Not found)")

    if result.is_complete:
        return f"Recipe ingredient resolution complete ({result.total_count}/{result.total_count} items resolved):\n" + "\n".join(lines)

    first_ing, first_query, first_options = result.ambiguous[0] if result.ambiguous else (None, None, [])
    report = f"Recipe resolution progress ({result.resolved_count}/{result.total_count} resolved, {len(result.ambiguous)} ambiguous):\n" + "\n".join(lines)

    if first_ing and first_options:
        first_label = format_ingredient_label(first_ing)
        report += f"\n\nPlease choose an option for ambiguous ingredient (1 of {len(result.ambiguous)}): '{first_label}' (query: '{first_query}'):\n"
        page_size = 5
        batch = first_options[offset : offset + page_size]
        for i, opt in enumerate(batch):
            brand_str = f" [{opt.brand}]" if opt.brand else ""
            report += f"  {i+1}. {opt.name}{brand_str} ({opt.product_id})\n"
        if (offset + len(batch)) < len(first_options):
            report += f"  {len(batch)+1}. Other\n"

    return report


