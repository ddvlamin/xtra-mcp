import re
import os
from typing import List, Union, Dict
from src.models import Product
from src.client import ColruytClient

def extract_ingredients(md_content: str) -> List[str]:
    """Extracts ingredients from a markdown recipe."""
    # Find the section starting with "## 🛒 Ingrediënten"
    match = re.search(r"## 🛒 Ingrediënten\n(.*?)(?:\n##|\Z)", md_content, re.DOTALL)
    if not match:
        return []
    
    ingredients_lines = match.group(1).strip().split("\n")
    ingredients = []
    
    for line in ingredients_lines:
        if line.startswith("*"):
            # Remove bullets and categories like "**Eiwit:**"
            # Example: "* **Eiwit:** 3 kipfilets" -> "3 kipfilets"
            clean_line = re.sub(r"^\*\s+(\*\*.*?\:\*\*\s*)?", "", line).strip()
            
            # Split by comma if multiple ingredients are on one line
            parts = [p.strip() for p in clean_line.split(",")]
            ingredients.extend(parts)
            
    return [i for i in ingredients if i]

def clean_ingredient(ingredient: str) -> str:
    """Removes quantities and units from an ingredient string."""
    # Example: "3 kipfilets" -> "kipfilets"
    # Example: "½ l kokosmelk" -> "kokosmelk"
    # Example: "2 dikke koffielepels rode currypasta" -> "rode currypasta"
    
    # Remove leading quantities (including fractions)
    ingredient = re.sub(r"^[0-9½¼¾\s/]+", "", ingredient).strip()
    
    # Remove common units
    units = ["l", "ml", "g", "kg", "el", "tl", "koffielepels", "dikke koffielepels", "kop", "koppen", "scheutje", "bot", "plant", "enkele"]
    pattern = r"^\b(" + "|".join(units) + r")\b\s+"
    ingredient = re.sub(pattern, "", ingredient).strip()
    
    return ingredient

async def resolve_ingredient(ingredient: str, client: ColruytClient, most_bought: List[Product]) -> Union[Product, List[Product]]:
    """Resolves an ingredient string to a Product using search and most_bought list."""
    query = clean_ingredient(ingredient)
    search_results = await client.search_products(query)
    
    if not search_results:
        return []
    
    if len(search_results) == 1:
        return search_results[0]
    
    # Multiple results, cross-reference with most_bought
    mb_ids = {p.technicalArticleNumber for p in most_bought}
    matches = [p for p in search_results if p.technicalArticleNumber in mb_ids]
    
    if len(matches) == 1:
        return matches[0]
    
    if len(matches) > 1:
        return matches # Return all most bought matches
        
    return search_results[:5] # Return top 5 search results if no most bought match
