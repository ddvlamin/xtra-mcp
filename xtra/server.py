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
from xtra.logic import (
    resolve_ingredient,
    store_resolved_product,
    resolve_recipe_ingredients,
    format_resolved_products_list,
    append_or_update_recipe_section,
    format_ambiguous_options_markdown,
    format_resolution_progress,
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
    name="resolve_ingredient",
    description="Resolve an ingredient string to its corresponding supermarket product id using local SQLite fuzzy matching and the supermarket provider's search API. Use this tool whenever the user asks to resolve, search, or find a product ID for a single ingredient or item. IMPORTANT: When status is 'ambiguous', ALWAYS output the 'presentation_markdown' field directly to the user so they can pick an option number or request the next page, then call store_resolved_product with their choice."
)
async def resolve_ingredient_tool(
    ingredient: str,
    limit: int = 5,
    offset: int = 0
) -> Dict[str, Any]:
    """Resolve an ingredient string to a Colruyt product."""
    curr_client = get_client()
    if not curr_client or not curr_client.session_id:
        return {
            "status": "error",
            "error": "Colruyt client not properly initialized. Please set the CLPBFF_SESSION environment variable or pass --session-id at server startup."
        }

    try:
        query, resolved = await resolve_ingredient(ingredient, curr_client)

        if isinstance(resolved, Product):
            return {
                "status": "resolved",
                "query": query,
                "ingredient": ingredient,
                "product": resolved.model_dump()
            }
        elif isinstance(resolved, list) and resolved:
            paged_items = [p.model_dump() for p in resolved[offset : offset + limit]]
            has_more = (offset + limit) < len(resolved)
            next_offset = offset + limit if has_more else None
            presentation_md = format_ambiguous_options_markdown(
                ingredient=ingredient,
                query=query,
                options=paged_items,
                has_more=has_more,
                next_offset=next_offset
            )
            return {
                "status": "ambiguous",
                "query": query,
                "ingredient": ingredient,
                "results": paged_items,
                "pagination": {
                    "offset": offset,
                    "limit": limit,
                    "total_matches": len(resolved),
                    "has_more": has_more,
                    "next_offset": next_offset
                },
                "presentation_markdown": presentation_md
            }
        else:
            return {
                "status": "not_found",
                "query": query,
                "ingredient": ingredient,
                "results": [],
                "pagination": {
                    "offset": offset,
                    "limit": limit,
                    "total_matches": 0,
                    "has_more": False,
                    "next_offset": None
                }
            }
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
    description="Parse a recipe markdown file and add ingredients to the shopping list. Use this tool whenever the user asks to add all ingredients from a recipe file to their shopping list."
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

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        error, result = await resolve_recipe_ingredients(content, curr_client)
        if error or result is None:
            return {"status": "error", "error": error}

        to_add = [prod for _, prod in result.resolved]
        updated_list = []
        if to_add:
            updated_list = await curr_client.add_items_to_list(to_add)

        return {
            "status": "success" if result.is_complete else "partial",
            "recipe_filename": recipe_filename,
            "resolved": [
                {"ingredient": ing.model_dump(), "product": prod.model_dump()}
                for ing, prod in result.resolved
            ],
            "ambiguous": [
                {
                    "ingredient": ing.model_dump(),
                    "query": q,
                    "options": [opt.model_dump() for opt in opts]
                }
                for ing, q, opts in result.ambiguous
            ],
            "not_found": [
                {"ingredient": ing.model_dump(), "query": q}
                for ing, q in result.not_found
            ],
            "added_count": len(to_add),
            "total_list_count": len(updated_list) if to_add else 0
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

@mcp.tool(
    name="resolve_recipe",
    description="Resolve all ingredients in a recipe using LLM extraction and product id resolution. Use this tool whenever the user asks to resolve, check, or look up products for all ingredients in a recipe without modifying the file. IMPORTANT: When status is 'incomplete' or ingredients are ambiguous, ALWAYS output the 'presentation_markdown' field directly to the user."
)
async def resolve_recipe_tool(
    recipe_filename: Optional[str] = None,
    recipe_content: Optional[str] = None,
    limit: int = 5,
    offset: int = 0
) -> Dict[str, Any]:
    """Resolve all ingredients in a recipe."""
    curr_client = get_client()
    if not curr_client or not curr_client.session_id:
        return {
            "status": "error",
            "error": "Colruyt client not properly initialized. Please set the CLPBFF_SESSION environment variable or pass --session-id at server startup."
        }

    try:
        content = recipe_content
        if not content and recipe_filename:
            if not os.path.exists(recipe_filename):
                return {"status": "error", "error": f"Recipe file '{recipe_filename}' not found."}
            with open(recipe_filename, "r", encoding="utf-8") as f:
                content = f.read()

        if not content:
            return {"status": "error", "error": "Either recipe_filename or recipe_content must be provided."}

        error, result = await resolve_recipe_ingredients(content, curr_client)
        if error or result is None:
            return {"status": "error", "error": error}

        ambiguous_data = []
        for ing, q, opts in result.ambiguous:
            paged_opts = [opt.model_dump() for opt in opts[offset : offset + limit]]
            has_more = (offset + limit) < len(opts)
            next_offset = offset + limit if has_more else None
            presentation_md = format_ambiguous_options_markdown(
                ingredient=ing.name,
                query=q,
                options=paged_opts,
                has_more=has_more,
                next_offset=next_offset
            )
            ambiguous_data.append({
                "ingredient": ing.model_dump(),
                "query": q,
                "options": paged_opts,
                "pagination": {
                    "offset": offset,
                    "limit": limit,
                    "total_matches": len(opts),
                    "has_more": has_more,
                    "next_offset": next_offset
                },
                "presentation_markdown": presentation_md
            })

        return {
            "status": "complete" if result.is_complete else "incomplete",
            "total_count": result.total_count,
            "resolved_count": result.resolved_count,
            "ambiguous_count": len(result.ambiguous),
            "not_found_count": len(result.not_found),
            "resolved": [
                {"ingredient": ing.model_dump(), "product": prod.model_dump()}
                for ing, prod in result.resolved
            ],
            "ambiguous": ambiguous_data,
            "not_found": [
                {"ingredient": ing.model_dump(), "query": q}
                for ing, q in result.not_found
            ],
            "presentation_markdown": format_resolution_progress(result, offset, limit)
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

@mcp.tool(
    name="annotate_recipe_with_productids",
    description="Extract and resolve all ingredients in a recipe markdown file to product ids and append or update a '## Resolved Products' section at the end of the file (format: '- <ingredient> [productId=<id>]'). Use this tool whenever the user asks to annotate, add, or append resolved product IDs to a recipe markdown file. Only writes to the file when 100% of ingredients are resolved; if incomplete or ambiguous, ALWAYS output the 'presentation_markdown' field directly to the user."
)
async def annotate_recipe_with_productids_tool(
    recipe_filename: str,
    limit: int = 5,
    offset: int = 0
) -> Dict[str, Any]:
    """Extract and annotate recipe markdown with resolved product IDs."""
    curr_client = get_client()
    if not curr_client or not curr_client.session_id:
        return {
            "status": "error",
            "error": "Colruyt client not properly initialized. Please set the CLPBFF_SESSION environment variable or pass --session-id at server startup."
        }

    try:
        if not os.path.exists(recipe_filename):
            return {"status": "error", "error": f"Recipe file '{recipe_filename}' not found."}

        with open(recipe_filename, "r", encoding="utf-8") as f:
            content = f.read()

        error, result = await resolve_recipe_ingredients(content, curr_client)
        if error or result is None:
            return {"status": "error", "error": error}

        if not result.is_complete:
            ambiguous_data = []
            for ing, q, opts in result.ambiguous:
                paged_opts = [opt.model_dump() for opt in opts[offset : offset + limit]]
                has_more = (offset + limit) < len(opts)
                next_offset = offset + limit if has_more else None
                presentation_md = format_ambiguous_options_markdown(
                    ingredient=ing.name,
                    query=q,
                    options=paged_opts,
                    has_more=has_more,
                    next_offset=next_offset
                )
                ambiguous_data.append({
                    "ingredient": ing.model_dump(),
                    "query": q,
                    "options": paged_opts,
                    "pagination": {
                        "offset": offset,
                        "limit": limit,
                        "total_matches": len(opts),
                        "has_more": has_more,
                        "next_offset": next_offset
                    },
                    "presentation_markdown": presentation_md
                })
            return {
                "status": "incomplete",
                "message": f"Cannot annotate recipe: not all ingredients are resolved ({result.resolved_count}/{result.total_count} resolved).",
                "total_count": result.total_count,
                "resolved_count": result.resolved_count,
                "ambiguous_count": len(result.ambiguous),
                "not_found_count": len(result.not_found),
                "resolved": [
                    {"ingredient": ing.model_dump(), "product": prod.model_dump()}
                    for ing, prod in result.resolved
                ],
                "ambiguous": ambiguous_data,
                "not_found": [
                    {"ingredient": ing.model_dump(), "query": q}
                    for ing, q in result.not_found
                ],
                "presentation_markdown": format_resolution_progress(result, offset, limit)
            }

        products_list_md = format_resolved_products_list(result.resolved)
        updated_content = append_or_update_recipe_section(content, "Resolved Products", products_list_md)

        with open(recipe_filename, "w", encoding="utf-8") as f:
            f.write(updated_content)

        return {
            "status": "annotated",
            "recipe_filename": recipe_filename,
            "resolved_count": len(result.resolved),
            "resolved": [
                {"ingredient": ing.model_dump(), "product": prod.model_dump()}
                for ing, prod in result.resolved
            ]
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

@mcp.tool(
    name="store_resolved_product",
    description="Store a resolved product mapping for an ingredient in the local SQLite database after a user selection. Use this tool whenever the user asks to store, save, remember, or map a product selection for an ingredient."
)
async def store_resolved_product_tool(
    ingredient: str,
    product_id: str,
    name: str,
    brand: Optional[str] = None,
    top_category_name: Optional[str] = None
) -> Dict[str, Any]:
    """Store resolved product mapping in local SQLite database."""
    curr_client = get_client()
    if not curr_client or not curr_client.session_id:
        return {
            "status": "error",
            "error": "Colruyt client not properly initialized. Please set the CLPBFF_SESSION environment variable or pass --session-id at server startup."
        }

    try:
        stored = await store_resolved_product(
            ingredient=ingredient,
            product_id=product_id,
            name=name,
            brand=brand,
            client=curr_client,
            top_category_name=top_category_name
        )
        return {
            "status": "stored",
            "query": ingredient,
            "product": stored.model_dump()
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

@mcp.prompt()
def product_assistant_mode() -> str:
    """System instructions for guiding product discovery & list selection."""
    return (
        "You are an interactive supermarket shopping and recipe assistant.\n\n"
        "When resolving ingredients or recipes, if a tool response indicates status 'ambiguous' or 'incomplete':\n"
        "1. Display the items using the preformatted list in 'presentation_markdown' (at most 5 items in a clean numbered list with name, brand, and category).\n"
        "2. Always inform the user if additional results exist on the next page.\n"
        "3. Explicitly offer two actions: pick a number to resolve and remember the product (via 'store_resolved_product'), or request 'next' to see more options with next_offset."
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

def main():
    global client

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

    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
