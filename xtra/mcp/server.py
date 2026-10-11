import os
import sys
import signal
import argparse
from typing import List, Optional, Dict, Any
from mcp.server.fastmcp import FastMCP
import mcp.types as types
from dotenv import load_dotenv

load_dotenv(override=True)

from xtra.sdk.client import SupermarketClient
from xtra.sdk.colruyt import ColruytClient
from xtra.sdk.models import Product
from xtra.catalog.db import Database, DEFAULT_DB_PATH

mcp = FastMCP("colruyt-xtra")

# Global client and DB references
client: Optional[SupermarketClient] = None
db: Optional[Database] = None


def get_db() -> Database:
    global db
    if db is None:
        db = Database(DEFAULT_DB_PATH)
    return db


def get_client() -> Optional[ColruytClient]:
    global client
    if client is not None:
        return client
    session_id = os.environ.get("CLPBFF_SESSION")
    api_key = os.environ.get("X_CG_APIKEY") or os.environ.get("COLRUYT_API_KEY")
    place_id = os.environ.get("COLRUYT_PLACE_ID")
    if not session_id:
        return None
    try:
        return ColruytClient(session_id=session_id, api_key=api_key, place_id=place_id)
    except ValueError:
        return None


@mcp.tool(
    name="lookup_products_in_database",
    description="Look up product names in the local SQLite database to retrieve matching Colruyt product IDs and product details before adding them to the shopping list. Returns matched products and warnings for any unresolved names."
)
async def lookup_products_in_database_tool(names: List[str]) -> Dict[str, Any]:
    """Look up product names in local database."""
    database = get_db()
    matches = []
    unresolved = []

    for name in names:
        p = database.find_product(name, score_threshold=80)
        if p:
            matches.append({
                "query": name,
                "product_id": p.product_id,
                "name": p.name,
                "brand": p.brand,
                "content": p.content
            })
        else:
            unresolved.append({
                "query": name,
                "warning": f"Product '{name}' not found in local database. Please map it using the catalog ingest tool."
            })

    return {
        "status": "success",
        "matches": matches,
        "unresolved": unresolved,
        "matched_count": len(matches),
        "unresolved_count": len(unresolved)
    }


@mcp.tool(
    name="add_items_to_list",
    description="Add products to the user's supermarket shopping list by their Colruyt product IDs. Use lookup_products_in_database first if you only have product names."
)
async def add_items_to_list_tool(product_ids: List[str]) -> Dict[str, Any]:
    """Add products to shopping list by product IDs."""
    curr_client = get_client()
    if not curr_client or not curr_client.session_id:
        return {
            "status": "error",
            "error": "Colruyt client not properly initialized. Please set the CLPBFF_SESSION environment variable."
        }

    try:
        products = [Product(name=f"Product {pid}", product_id=pid) for pid in product_ids]
        updated_list = await curr_client.add_items_to_list(products)
        return {
            "status": "success",
            "added_count": len(product_ids),
            "product_ids": product_ids,
            "total_list_count": len(updated_list)
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool(
    name="get_shopping_list",
    description="Retrieve the current active Colruyt supermarket shopping list, including list item IDs (UUIDs), descriptions, product IDs, and completion status."
)
async def get_shopping_list_tool(limit: int = 255, offset: int = 0) -> Dict[str, Any]:
    """Retrieve current shopping list."""
    curr_client = get_client()
    if not curr_client or not curr_client.session_id:
        return {
            "status": "error",
            "error": "Colruyt client not properly initialized. Please set the CLPBFF_SESSION environment variable."
        }

    try:
        items = await curr_client.get_shopping_list(limit=limit, offset=offset)
        formatted_items = []
        for i in items:
            formatted_items.append({
                "item_id": i.id,
                "description": i.description,
                "product_id": i.productData.productId if i.productData else None,
                "quantity": i.productData.quantity if i.productData else 1,
                "completed": bool(i.completedAt),
                "created_at": i.createdAt
            })
        return {
            "status": "success",
            "count": len(formatted_items),
            "items": formatted_items
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool(
    name="remove_items_from_list",
    description="Remove items from the shopping list using their list item IDs (UUIDs, obtainable via get_shopping_list)."
)
async def remove_items_from_list_tool(item_ids: List[str]) -> Dict[str, Any]:
    """Remove items from shopping list by item UUIDs."""
    curr_client = get_client()
    if not curr_client or not curr_client.session_id:
        return {
            "status": "error",
            "error": "Colruyt client not properly initialized. Please set the CLPBFF_SESSION environment variable."
        }

    removed = []
    failed = []

    for item_id in item_ids:
        try:
            ok = await curr_client.remove_item_from_list(item_id)
            if ok:
                removed.append(item_id)
            else:
                failed.append({"item_id": item_id, "error": "Server returned unsuccessful status."})
        except Exception as e:
            failed.append({"item_id": item_id, "error": str(e)})

    return {
        "status": "success" if not failed else ("partial" if removed else "error"),
        "removed_item_ids": removed,
        "failed_items": failed,
        "removed_count": len(removed),
        "failed_count": len(failed)
    }


async def handle_list_tools() -> List[types.Tool]:
    """Compatibility helper to list registered tools."""
    return await mcp.list_tools()


async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
    """Compatibility helper to call registered tools."""
    res = await mcp.call_tool(name, arguments)
    if isinstance(res, tuple):
        return res[0]
    return [types.TextContent(type="text", text=str(res))]


def _handle_sigterm(signum, frame):
    sys.exit(0)


def main():
    global client, db

    try:
        signal.signal(signal.SIGTERM, _handle_sigterm)
    except (ValueError, AttributeError):
        pass

    parser = argparse.ArgumentParser(description="Colruyt Xtra MCP Server")
    parser.add_argument("--session-id", "-s", help="Colruyt Xtra session ID (clpbff_session cookie)")
    parser.add_argument("--api-key", "-a", help="Custom x-cg-apikey header value")
    parser.add_argument("--place-id", "-p", help="Colruyt store ID (placeId)")
    parser.add_argument("--db-path", help="Path to SQLite database", default=DEFAULT_DB_PATH)
    args, unknown = parser.parse_known_args()

    session_id = args.session_id or os.environ.get("CLPBFF_SESSION")
    api_key = args.api_key or os.environ.get("X_CG_APIKEY")
    place_id = args.place_id or os.environ.get("COLRUYT_PLACE_ID")
    db_path = args.db_path

    if db_path:
        db = Database(db_path)

    if not session_id:
        print("Warning: session_id not set via CLI argument or CLPBFF_SESSION environment variable.", file=sys.stderr)

    try:
        client = ColruytClient(session_id=session_id, api_key=api_key, place_id=place_id)
    except Exception:
        pass

    try:
        mcp.run(transport="stdio")
    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)


if __name__ == "__main__":
    main()
