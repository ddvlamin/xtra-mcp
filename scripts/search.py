import argparse
import asyncio
import os
import sys
from dotenv import load_dotenv

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from xtra.colruyt import ColruytClient

# Load environment variables from .env
load_dotenv()

async def main():
    parser = argparse.ArgumentParser(
        description="Search Colruyt products by query."
    )
    parser.add_argument(
        "query",
        nargs="?",
        help="Search query string (e.g. 'aardbeien')"
    )
    parser.add_argument(
        "-q", "--query",
        dest="query_opt",
        help="Alternative search query option"
    )
    parser.add_argument(
        "-s", "--session-id",
        help="Colruyt session ID (defaults to CLPBFF_SESSION env var)"
    )
    parser.add_argument(
        "-a", "--api-key",
        help="Colruyt API key (defaults to X_CG_APIKEY env var)"
    )
    parser.add_argument(
        "-p", "--place-id",
        help="Colruyt place ID (defaults to COLRUYT_PLACE_ID env var)"
    )

    args = parser.parse_args()
    query = args.query or args.query_opt

    if not query:
        parser.error("Query parameter is required. Usage: python scripts/search.py <query>")

    session_id = args.session_id or os.getenv("CLPBFF_SESSION")
    api_key = args.api_key or os.getenv("X_CG_APIKEY")
    place_id = args.place_id or os.getenv("COLRUYT_PLACE_ID")

    if not session_id:
        print("Error: CLPBFF_SESSION not found in environment or .env file.", file=sys.stderr)
        sys.exit(1)

    client = ColruytClient(session_id=session_id, api_key=api_key, place_id=place_id)
    print(f"Searching for: '{query}'...")

    try:
        results = await client.search_products(query)
        if not results:
            print("No products found.")
        else:
            print(f"Found {len(results)} products:")
            for p in results:
                line = f"- {p.name} ({p.product_id})"
                if p.brand:
                    line += f" [Brand: {p.brand}]"
                print(line)
    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
