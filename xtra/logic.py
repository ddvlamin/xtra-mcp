import re
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
from xtra.formatting import (
    format_ingredient_label,
    format_resolved_products_list,
    append_or_update_recipe_section,
    format_ambiguous_options_markdown,
)

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
    Returns a tuple of (query, Product | List[Product]).
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



