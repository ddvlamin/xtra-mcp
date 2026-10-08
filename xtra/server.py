import os
import sys
import argparse
from typing import List, Optional, Dict, Any
from mcp.server.fastmcp import FastMCP
import mcp.types as types
from dotenv import load_dotenv

load_dotenv(override=True)
from xtra.client import SupermarketClient
from xtra.colruyt import ColruytClient
from xtra.models import Product
from xtra.session import (
    start_resolution_session,
    resolve_session_ingredient_choice,
    paginate_session_ingredient,
    session_manager,
)

mcp = FastMCP("colruyt-xtra")

# Global client (initialized at startup or dynamically)
client: Optional[SupermarketClient] = None

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
    name="start_recipe_resolution",
    description="Find, search, and resolve products or ingredients (for single items like 'bananas', multiple items like ['bananas', 'hummus'], or recipe files/content) against the supermarket catalog. Use this tool whenever the user asks to find, search, look up, or resolve products or ingredients. IMPORTANT: Always use this MCP tool instead of running terminal search scripts. Display the 'presentation_markdown' field directly to the user."
)
async def start_recipe_resolution_tool(
    ingredients: Optional[List[str]] = None,
    recipe_filename: Optional[str] = None,
    recipe_content: Optional[str] = None,
    session_id: Optional[str] = None,
    limit: int = 5
) -> Dict[str, Any]:
    """Start an interactive ingredient/recipe resolution session."""
    curr_client = get_client()
    if not curr_client or not curr_client.session_id:
        return {
            "status": "error",
            "error": "Colruyt client not properly initialized. Please set the CLPBFF_SESSION environment variable or pass --session-id at server startup."
        }

    try:
        return await start_resolution_session(
            ingredients=ingredients,
            recipe_filename=recipe_filename,
            recipe_content=recipe_content,
            session_id=session_id,
            client=curr_client,
            limit=limit
        )
    except Exception as e:
        return {"status": "error", "error": str(e)}

@mcp.tool(
    name="resolve_ingredient_choice",
    description="Locks in the user's product choice for the active ingredient in a resolution session, persists the mapping to SQLite, and automatically advances to the next unresolved item. IMPORTANT: Display the 'presentation_markdown' field directly to the user."
)
async def resolve_ingredient_choice_tool(
    session_id: str,
    selected_product_id: str,
    ingredient_name: Optional[str] = None,
    selected_option_index: Optional[int] = None,
    limit: int = 5
) -> Dict[str, Any]:
    """Resolve current active ingredient with selected product ID and advance to next item."""
    curr_client = get_client()
    if not curr_client or not curr_client.session_id:
        return {
            "status": "error",
            "error": "Colruyt client not properly initialized. Please set the CLPBFF_SESSION environment variable or pass --session-id at server startup."
        }

    try:
        return await resolve_session_ingredient_choice(
            session_id=session_id,
            selected_product_id=selected_product_id,
            ingredient_name=ingredient_name,
            selected_option_index=selected_option_index,
            client=curr_client,
            limit=limit
        )
    except Exception as e:
        return {"status": "error", "error": str(e)}

@mcp.tool(
    name="paginate_active_ingredient",
    description="Fetches the next page of product candidate options for the active ingredient in a resolution session when the user requests more options. IMPORTANT: Display the 'presentation_markdown' field directly to the user."
)
async def paginate_active_ingredient_tool(
    session_id: str,
    ingredient_name: Optional[str] = None,
    offset: int = 0,
    limit: int = 5
) -> Dict[str, Any]:
    """Paginate candidate products for the active ingredient in a session."""
    try:
        return await paginate_session_ingredient(
            session_id=session_id,
            ingredient_name=ingredient_name,
            offset=offset,
            limit=limit
        )
    except Exception as e:
        return {"status": "error", "error": str(e)}

@mcp.tool(
    name="add_items_to_list",
    description="Add products to the user's supermarket shopping list. Use this tool whenever the user asks to add product IDs or items directly to their shopping list."
)
async def add_items_to_list_tool(product_ids: List[str]) -> Dict[str, Any]:
    """Add products to shopping list by product IDs."""
    curr_client = get_client()
    if not curr_client or not curr_client.session_id:
        return {
            "status": "error",
            "error": "Colruyt client not properly initialized. Please set the CLPBFF_SESSION environment variable or pass --session-id at server startup."
        }

    try:
        dummy_products = [Product(name=f"Product {pid}", product_id=pid) for pid in product_ids]
        updated_list = await curr_client.add_items_to_list(dummy_products)
        return {
            "status": "success",
            "added_count": len(product_ids),
            "product_ids": product_ids,
            "total_list_count": len(updated_list)
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

@mcp.tool(
    name="add_recipe_to_list",
    description="Parse a recipe markdown file and add its resolved ingredients to the shopping list. Use this tool whenever the user asks to add all ingredients from a recipe file to their shopping list."
)
async def add_recipe_to_list_tool(recipe_filename: str) -> Dict[str, Any]:
    """Parse a recipe markdown file and add ingredients to the shopping list."""
    curr_client = get_client()
    if not curr_client or not curr_client.session_id:
        return {
            "status": "error",
            "error": "Colruyt client not properly initialized. Please set the CLPBFF_SESSION environment variable or pass --session-id at server startup."
        }

    try:
        path = recipe_filename
        if not os.path.exists(path):
            return {"status": "error", "error": f"File '{path}' not found."}

        res = await start_resolution_session(recipe_filename=path, client=curr_client)
        if res.get("status") == "error":
            return res

        session = session_manager.get_session(res["session_id"])
        if not session:
            return {"status": "error", "error": "Could not retrieve resolution session."}

        to_add = [item.resolved_product for item in session.ingredients if item.resolved_product]
        updated_list = []
        if to_add:
            updated_list = await curr_client.add_items_to_list(to_add)

        return {
            "status": "success" if session.is_completed else "partial",
            "recipe_filename": recipe_filename,
            "session_id": session.session_id,
            "resolved_count": session.resolved_count,
            "total_count": session.total_count,
            "added_count": len(to_add),
            "total_list_count": len(updated_list) if to_add else 0,
            "presentation_markdown": res.get("presentation_markdown")
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

@mcp.prompt()
def product_assistant_mode() -> str:
    """System instructions for guiding product discovery & list selection."""
    return (
        "You are an interactive supermarket shopping and recipe assistant.\n\n"
        "RULES FOR RESOLVING INGREDIENTS & RECIPES:\n"
        "1. For recipes or ingredient lists (even single ingredients), call `start_recipe_resolution` to manage a step-by-step resolution session.\n"
        "2. Always resolve one ingredient at a time. Never overwhelm the user with multiple product lists at once.\n"
        "3. At each step, display the preformatted list directly from `presentation_markdown` (showing `[X/N] Finding: ...` and numbered candidate products).\n"
        "4. When the user picks an item number or product ID in a session, call `resolve_ingredient_choice` with the session_id and selected product ID.\n"
        "5. If the user asks for more options or next page, call `paginate_active_ingredient` with the next_offset.\n"
        "6. When all items are resolved, display the final confirmed grocery list from `presentation_markdown`."
    )

async def handle_list_tools() -> List[types.Tool]:
    """Compatibility helper to list registered tools."""
    return await mcp.list_tools()

async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
    """Compatibility helper to call registered tools."""
    res = await mcp.call_tool(name, arguments)
    if isinstance(res, tuple):
        return res[0]
    return [types.TextContent(type="text", text=str(res))]

async def handle_list_prompts():
    """Compatibility helper to list registered prompts."""
    return await mcp.list_prompts()

async def handle_get_prompt(name: str, arguments: Optional[Dict[str, Any]] = None):
    """Compatibility helper to get prompt content."""
    return await mcp.get_prompt(name, arguments)

import signal

def _handle_sigterm(signum, frame):
    sys.exit(0)

def main():
    global client

    # Handle SIGTERM cleanly on MCP reload
    try:
        signal.signal(signal.SIGTERM, _handle_sigterm)
    except (ValueError, AttributeError):
        pass

    parser = argparse.ArgumentParser(description="Colruyt Xtra MCP Server")
    parser.add_argument("--session-id", "-s", help="Colruyt Xtra session ID (clpbff_session cookie)")
    parser.add_argument("--api-key", "-a", help="Custom x-cg-apikey header value")
    parser.add_argument("--place-id", "-p", help="Colruyt store ID (placeId)")
    args, unknown = parser.parse_known_args()

    session_id = args.session_id or os.environ.get("CLPBFF_SESSION")
    api_key = args.api_key or os.environ.get("X_CG_APIKEY")
    place_id = args.place_id or os.environ.get("COLRUYT_PLACE_ID")

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

