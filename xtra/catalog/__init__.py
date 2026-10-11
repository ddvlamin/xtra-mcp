"""Catalog package for product database, ingredient ingestion, and recipe annotation."""

from xtra.catalog.db import Database
from xtra.catalog.extractor import (
    extract_ingredients_section,
    extract_resolved_products,
    parse_recipe_ingredients,
    append_or_update_recipe_section,
    format_resolved_products_list,
    format_ingredient_label,
    ExtractionError,
    BaseIngredientExtractor,
    LLMIngredientExtractor,
    IngredientExtractor,
)

__all__ = [
    "Database",
    "extract_ingredients_section",
    "extract_resolved_products",
    "parse_recipe_ingredients",
    "append_or_update_recipe_section",
    "format_resolved_products_list",
    "format_ingredient_label",
    "ExtractionError",
    "BaseIngredientExtractor",
    "LLMIngredientExtractor",
    "IngredientExtractor",
]
