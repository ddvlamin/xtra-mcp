import os
import sys
import glob
import asyncio
import argparse
from typing import List, Optional
from xtra.sdk.colruyt import ColruytClient
from xtra.sdk.models import Product, ExtractedIngredient
from xtra.catalog.db import Database, DEFAULT_DB_PATH
from xtra.catalog.extractor import parse_recipe_ingredients


async def search_and_prompt_candidate(
    ingredient: ExtractedIngredient,
    client: ColruytClient,
    db: Database
) -> Optional[Product]:
    """Search for an ingredient and prompt user interactively to confirm choice."""
    current_query = ingredient.name

    while True:
        print(f"\nSearching Colruyt for: '{current_query}' (from recipe: '{ingredient.name}')")
        try:
            candidates = await client.search_products(current_query)
        except Exception as e:
            print(f"Error searching Colruyt: {e}")
            candidates = []

        if not candidates:
            print(f"No products found for query '{current_query}'.")
            action = input("Enter new search term, or 's' to skip: ").strip()
            if not action or action.lower() == "s":
                return None
            current_query = action
            continue

        print(f"\nTop candidates for '{current_query}':")
        limit = min(5, len(candidates))
        for idx in range(limit):
            cand = candidates[idx]
            brand_str = f" [{cand.brand}]" if cand.brand else ""
            content_str = f" ({cand.content})" if cand.content else ""
            print(f"  [{idx + 1}] {cand.name}{brand_str}{content_str} (ID: {cand.product_id})")

        print("  [s] Skip this ingredient")
        print("  [c] Custom search term")

        choice = input("Select option [1-5], 's' to skip, 'c' to search: ").strip()

        if choice.lower() == "s":
            return None
        elif choice.lower() == "c":
            custom_term = input("Enter new search term: ").strip()
            if custom_term:
                current_query = custom_term
            continue
        elif choice.isdigit():
            opt_idx = int(choice) - 1
            if 0 <= opt_idx < limit:
                selected = candidates[opt_idx]
                product_to_store = Product(
                    query=ingredient.name.strip().lower(),
                    product_id=selected.product_id,
                    name=selected.name,
                    brand=selected.brand,
                    description=selected.description,
                    content=selected.content,
                    top_category_name=selected.top_category_name,
                )
                db.store_product(product_to_store)
                print(f"✓ Saved mapping: '{ingredient.name}' -> {selected.name} [{selected.product_id}] in database.")
                return product_to_store
            else:
                print("Invalid option number.")
        else:
            print("Invalid input.")


async def process_recipe_file(
    file_path: str,
    client: ColruytClient,
    db: Database
):
    print(f"\n==========================================")
    print(f"Processing recipe: {os.path.basename(file_path)}")
    print(f"==========================================")

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    ingredients = parse_recipe_ingredients(content)
    if not ingredients:
        print(f"No ingredients found in {file_path}")
        return

    print(f"Found {len(ingredients)} ingredients.")

    for ing in ingredients:
        existing = db.find_product(ing.name, score_threshold=85)
        if existing:
            print(f"✓ Already in DB: '{ing.name}' -> {existing.name} [{existing.product_id}]")
            continue

        await search_and_prompt_candidate(ing, client, db)


def find_recipe_files(target_path: str) -> List[str]:
    """Finds all markdown recipe files from target path or directory."""
    if os.path.isfile(target_path):
        return [target_path]
    elif os.path.isdir(target_path):
        pattern = os.path.join(target_path, "**", "*.md")
        return sorted(glob.glob(pattern, recursive=True))
    return []


async def run_ingest(
    file_path: Optional[str] = None,
    dir_path: Optional[str] = None,
    db_path: Optional[str] = None,
    place_id: Optional[str] = None
):
    target = file_path or dir_path
    if not target:
        print("Error: Must specify either --file or --dir", file_path=sys.stderr)
        sys.exit(1)

    recipe_files = find_recipe_files(target)
    if not recipe_files:
        print(f"No markdown files found at: {target}")
        sys.exit(1)

    db = Database(db_path=db_path or DEFAULT_DB_PATH)
    try:
        client = ColruytClient(place_id=place_id)
    except Exception as e:
        print(f"Error initializing Colruyt client: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(recipe_files)} recipe file(s) to process.")
    for r_file in recipe_files:
        await process_recipe_file(r_file, client, db)

    print("\nIngestion complete.")


def main():
    parser = argparse.ArgumentParser(
        description="Interactive tool to lookup ingredients from recipes in Colruyt and populate local SQLite DB."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", "-f", help="Path to a single recipe markdown file")
    group.add_argument("--dir", "-d", help="Path to directory containing recipe markdown files")
    parser.add_argument("--db-path", help="Path to SQLite database", default=DEFAULT_DB_PATH)
    parser.add_argument("--place-id", help="Colruyt store place ID")

    args = parser.parse_args()
    asyncio.run(run_ingest(
        file_path=args.file,
        dir_path=args.dir,
        db_path=args.db_path,
        place_id=args.place_id
    ))


if __name__ == "__main__":
    main()
