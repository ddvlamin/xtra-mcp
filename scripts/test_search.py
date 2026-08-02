import asyncio
import os
from dotenv import load_dotenv
from xtra.colruyt import ColruytClient

# Load environment variables from .env
load_dotenv()

async def main():
    session_id = os.getenv("CLPBFF_SESSION")
    api_key = os.getenv("X_CG_APIKEY")
    place_id = os.getenv("COLRUYT_PLACE_ID")

    if not session_id:
        print("Error: CLPBFF_SESSION not found in environment or .env file.")
        return

    print(f"Initializing client with session: {session_id[:8]}...")
    client = ColruytClient(session_id=session_id, api_key=api_key, place_id=place_id)

    query = "aardbeien"
    print(f"Searching for: '{query}'...")
    
    try:
        results = await client.search_products(query)
        if not results:
            print("No products found.")
        else:
            print(f"Found {len(results)} products:")
            for p in results:
                print(f"- {p.name} ({p.product_id})")
                if p.brand:
                    print(f"  Brand: {p.brand}")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(main())
