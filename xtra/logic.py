import re
import os
from typing import List, Union, Dict, Optional
from xtra.models import Product, ProductMapping
from xtra.client import ColruytClient
from xtra.db import Database
from xtra.scraper import scrape_product_info

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
    """Removes quantities and units from an ingredient string."""
    ingredient = re.sub(r"^[0-9½¼¾\s/]+", "", ingredient).strip()
    units = ["l", "ml", "g", "kg", "el", "tl", "koffielepels", "dikke koffielepels", "kop", "koppen", "scheutje", "bot", "plant", "enkele"]
    pattern = r"^\b(" + "|".join(units) + r")\b\s+"
    ingredient = re.sub(pattern, "", ingredient).strip()
    return ingredient

def mapping_to_product(mapping: ProductMapping) -> Product:
    return Product(
        name=mapping.product_name,
        technicalArticleNumber=mapping.product_id,
        brand=mapping.product_brand,
        content=mapping.content,
        description=mapping.product_description,
        conservation_info=mapping.conservation_info,
        usage_info=mapping.usage_info
    )

async def save_product_mapping_logic(
    cleaned_ingredient: str,
    product_id: str,
    product_name: str,
    product_brand: Optional[str] = None,
    db: Optional[Database] = None,
    gtin: Optional[str] = None
) -> ProductMapping:
    if db is None:
        db = Database()

    cleaned = clean_ingredient(cleaned_ingredient)
    scraped_info = await scrape_product_info(product_id, gtin=gtin)

    mapping = ProductMapping(
        cleaned_ingredient=cleaned,
        product_id=product_id,
        product_name=product_name,
        product_brand=product_brand,
        product_description=scraped_info.get("product_description"),
        conservation_info=scraped_info.get("conservation_info"),
        usage_info=scraped_info.get("usage_info"),
        content=scraped_info.get("content")
    )
    return db.save_mapping(mapping)

async def resolve_ingredient(
    ingredient: str,
    client: ColruytClient,
    most_bought: List[Product],
    db: Optional[Database] = None
) -> Union[Product, List[Product]]:
    """Resolves an ingredient string to a Product using database fuzzy matching, search, and most_bought list."""
    if db is None:
        db = Database()

    query = clean_ingredient(ingredient)
    
    # 1. Database fuzzy matching lookup (threshold >= 80)
    fuzzy_match = db.find_fuzzy_mapping(query, score_threshold=80)
    if fuzzy_match:
        return mapping_to_product(fuzzy_match)

    # 2. Live search API
    search_results = await client.search_products(query)
    if not search_results:
        return []

    resolved_product: Optional[Product] = None

    if len(search_results) == 1:
        resolved_product = search_results[0]
    else:
        # Cross-reference with most_bought
        mb_ids = {p.technicalArticleNumber for p in most_bought}
        matches = [p for p in search_results if p.technicalArticleNumber in mb_ids]
        if len(matches) == 1:
            resolved_product = matches[0]
        elif len(matches) > 1:
            return matches
        else:
            return search_results[:5]

    # 3. Scrape metadata & auto-save mapping for uniquely resolved product
    if resolved_product:
        gtin = resolved_product.gtin[0] if (resolved_product.gtin and len(resolved_product.gtin) > 0) else None
        scraped_info = await scrape_product_info(resolved_product.technicalArticleNumber, gtin=gtin)

        resolved_product.description = scraped_info.get("product_description")
        resolved_product.conservation_info = scraped_info.get("conservation_info")
        resolved_product.usage_info = scraped_info.get("usage_info")
        if scraped_info.get("content"):
            resolved_product.content = scraped_info.get("content")

        mapping = ProductMapping(
            cleaned_ingredient=query,
            product_id=resolved_product.technicalArticleNumber,
            product_name=resolved_product.name,
            product_brand=resolved_product.brand,
            product_description=resolved_product.description,
            conservation_info=resolved_product.conservation_info,
            usage_info=resolved_product.usage_info,
            content=resolved_product.content
        )
        db.save_mapping(mapping)
        return resolved_product

    return []
