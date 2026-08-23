import argparse
import os
import sys

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from xtra.db import Database

def main():
    parser = argparse.ArgumentParser(
        description="Delete a product record from the Colruyt products database by normalized name or product ID."
    )
    parser.add_argument(
        "-n", "--normalized-name",
        help="Normalized ingredient name to delete (e.g. 'kipfilet')"
    )
    parser.add_argument(
        "-p", "--product-id",
        help="Colruyt product ID to delete (e.g. '4804565')"
    )
    parser.add_argument(
        "-d", "--db-path",
        help="Path to SQLite database file (optional, defaults to resources/colruyt_products.db)"
    )

    args = parser.parse_args()

    if not args.normalized_name and not args.product_id:
        parser.error("At least one of --normalized-name (-n) or --product-id (-p) is required.")

    db = Database(db_path=args.db_path)
    try:
        deleted_count = db.delete_product(
            normalized_name=args.normalized_name,
            product_id=args.product_id
        )
        if deleted_count > 0:
            print(f"Successfully deleted {deleted_count} record(s).")
        else:
            print("No matching record found to delete.")
    except Exception as e:
        print(f"Error deleting record: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
