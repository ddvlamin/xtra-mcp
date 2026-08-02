import re
from typing import List, Union, Optional
from xtra.models import Product
from xtra.client import SupermarketClient
from xtra.db import Database

def extract_ingredients(md_content: str) -> List[str]:
    """Extracts ingredients from a markdown recipe."""
    match = re.search(r"## 🛒 Ingrediënten\n(.*?)(?:\n##|\Z)", md_content, re.DOTALL)
    if not match:
        return []
    
    ingredients_lines = match.group(1).strip().split("\n")
    ingredients = []
    
    for line in ingredients_lines:
        if line.startswith("*"):
            clean_line = re.sub(r"^\*\s+(\*\*.*?\:\*\*\s*)?", "", line).strip()
            parts = [p.strip() for p in clean_line.split(",")]
            ingredients.extend(parts)
            
    return [i for i in ingredients if i]

def clean_ingredient(ingredient: str) -> str:
    """Removes quantities and units from an ingredient string to form a normalized ingredient name."""
    ingredient = re.sub(r"^[0-9½¼¾\s/]+", "", ingredient).strip()
    units = ["l", "ml", "g", "kg", "el", "tl", "koffielepels", "dikke koffielepels", "kop", "koppen", "scheutje", "bot", "plant", "enkele"]
    pattern = r"^\b(" + "|".join(units) + r")\b\s+"
    ingredient = re.sub(pattern, "", ingredient).strip()
    return ingredient

async def resolve_ingredient(
    ingredient: str,
    client: SupermarketClient,
    most_bought: List[Product],
    db: Optional[Database] = None
) -> Union[Product, List[Product]]:
    """Resolves an ingredient string to a Product using database fuzzy matching, search, and most_bought list."""
    if db is None:
        db = Database()

    query = clean_ingredient(ingredient)
    
    # 1. Database fuzzy matching lookup (threshold >= 80)
    fuzzy_match = db.find_product(query, score_threshold=80)
    if fuzzy_match:
        return fuzzy_match

    # 2. Live search API
    search_results = await client.search_products(query)
    if not search_results:
        return []

    resolved_product: Optional[Product] = None

    if len(search_results) == 1:
        resolved_product = search_results[0]
    else:
        # Cross-reference with most_bought
        mb_ids = {p.product_id for p in most_bought}
        matches = [p for p in search_results if p.product_id in mb_ids]
        if len(matches) == 1:
            resolved_product = matches[0]
        elif len(matches) > 1:
            return matches
        else:
            return search_results[:5]

    # 3. Fetch product info via client & store product in DB
    if resolved_product:
        gtin = resolved_product.gtin[0] if (resolved_product.gtin and len(resolved_product.gtin) > 0) else None # TODO: gtin is probably still Colruyt specific
        product_info = await client.get_product_info(resolved_product.product_id, gtin=gtin)
        
        resolved_product.normalized_name = query
        resolved_product.description = product_info.get("product_description")
        resolved_product.conservation_info = product_info.get("conservation_info")
        resolved_product.usage_info = product_info.get("usage_info")
        if product_info.get("content"):
            resolved_product.content = product_info.get("content")

        stored = db.store_product(resolved_product)
        return stored

    return []
