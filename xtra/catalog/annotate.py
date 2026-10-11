import os
import sys
import glob
import argparse
from typing import List, Optional, Tuple
from xtra.sdk.models import ExtractedIngredient
from xtra.catalog.db import Database, DEFAULT_DB_PATH
from xtra.catalog.extractor import (
    parse_recipe_ingredients,
    extract_resolved_products,
    format_resolved_products_list,
    append_or_update_recipe_section,
)


def annotate_recipe_content(
    content: str,
    db: Database,
    recipe_name: str = "recipe"
) -> Tuple[str, List[Tuple[ExtractedIngredient, str]], List[str]]:
    """Annotates recipe text by resolving ingredients against SQLite DB.

    Returns:
        (updated_content, resolved_items, warning_messages)
    """
    ingredients = parse_recipe_ingredients(content)
    existing_resolved = extract_resolved_products(content)
    existing_map = {item["ingredient"].lower(): item["productId"] for item in existing_resolved}

    resolved_items: List[Tuple[ExtractedIngredient, str]] = []
    warnings: List[str] = []

    for ing in ingredients:
        clean_name = ing.name.strip().lower()

        # 1. Check if already resolved in the recipe's ## Resolved Products
        if clean_name in existing_map:
            resolved_items.append((ing, existing_map[clean_name]))
            continue

        # 2. Check local database
        product = db.find_product(clean_name, score_threshold=80)
        if product:
            resolved_items.append((ing, product.product_id))
        else:
            warnings.append(
                f"[{recipe_name}] WARNING: Ingredient '{ing.name}' not found in database. Run ingest.py first."
            )

    if resolved_items:
        section_body = format_resolved_products_list(resolved_items)
        updated_content = append_or_update_recipe_section(content, "Resolved Products", section_body)
    else:
        updated_content = content

    return updated_content, resolved_items, warnings


def annotate_recipe_file(
    file_path: str,
    db: Database
) -> Tuple[int, int]:
    """Annotates a single recipe file in-place.

    Returns (resolved_count, warning_count).
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    recipe_name = os.path.basename(file_path)
    updated_content, resolved, warnings = annotate_recipe_content(content, db, recipe_name=recipe_name)

    for w in warnings:
        print(w, file=sys.stderr)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(updated_content)

    print(f"✓ Annotated '{recipe_name}': {len(resolved)} resolved, {len(warnings)} warning(s).")
    return len(resolved), len(warnings)


def find_recipe_files(target_path: str) -> List[str]:
    """Finds all markdown recipe files from target path or directory."""
    if os.path.isfile(target_path):
        return [target_path]
    elif os.path.isdir(target_path):
        pattern = os.path.join(target_path, "**", "*.md")
        return sorted(glob.glob(pattern, recursive=True))
    return []


def run_annotate(
    file_path: Optional[str] = None,
    dir_path: Optional[str] = None,
    db_path: Optional[str] = None
):
    target = file_path or dir_path
    if not target:
        print("Error: Must specify either --file or --dir", file=sys.stderr)
        sys.exit(1)

    recipe_files = find_recipe_files(target)
    if not recipe_files:
        print(f"No markdown files found at: {target}", file=sys.stderr)
        sys.exit(1)

    db = Database(db_path=db_path or DEFAULT_DB_PATH)

    total_resolved = 0
    total_warnings = 0

    print(f"Annotating {len(recipe_files)} recipe file(s)...")
    for r_file in recipe_files:
        res, warn = annotate_recipe_file(r_file, db)
        total_resolved += res
        total_warnings += warn

    print(f"\nAnnotation completed: {total_resolved} total resolved, {total_warnings} total warning(s).")


def main():
    parser = argparse.ArgumentParser(
        description="Annotate recipe markdown files in-place with Colruyt product IDs from the local database."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", "-f", help="Path to a single recipe markdown file")
    group.add_argument("--dir", "-d", help="Path to directory containing recipe markdown files")
    parser.add_argument("--db-path", help="Path to SQLite database", default=DEFAULT_DB_PATH)

    args = parser.parse_args()
    run_annotate(
        file_path=args.file,
        dir_path=args.dir,
        db_path=args.db_path
    )


if __name__ == "__main__":
    main()
