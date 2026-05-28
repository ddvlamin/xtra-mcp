import asyncio
import os
from dotenv import load_dotenv
from src.client import ColruytClient

# Load environment variables from .env
load_dotenv()

async def main():
    session_id = os.getenv("CLPBFF_SESSION")
    api_key = os.getenv("X_CG_APIKEY")

    if not session_id:
        print("Error: CLPBFF_SESSION not found in environment or .env file.")
        return

    print(f"Initializing client with session: {session_id[:8]}...")
    client = ColruytClient(session_id=session_id, api_key=api_key)

    query = "aardbeien"
    print(f"Searching for: '{query}'...")
    
    try:
        results = await client.search_products(query)
        if not results:
            print("No products found.")
        else:
            print(f"Found {len(results)} products:")
            for p in results:
                price_str = f"€{p.price.basicPrice}" if p.price else "N/A"
                print(f"- {p.name} ({p.technicalArticleNumber}) - {price_str}")
                if p.brand:
                    print(f"  Brand: {p.brand}")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(main())
