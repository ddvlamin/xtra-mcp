import os
import sys
import argparse
import asyncio
from typing import List, Optional, Dict, Any
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.types as types
import mcp.server.stdio
from dotenv import load_dotenv
load_dotenv(override=True)
from xtra.client import SupermarketClient
from xtra.colruyt import ColruytClient
from xtra.models import Product
from xtra.logic import (
    resolve_ingredient,
    store_resolved_product,
    resolve_recipe_ingredients,
    format_ingredient_label,
    format_resolved_products_list,
    append_or_update_recipe_section,
    format_resolution_progress
)

# Initialize server
server = Server("colruyt-xtra")

# Global client (initialized at startup)
client: Optional[SupermarketClient] = None

def get_client() -> Optional[ColruytClient]:
    global client
    if client is not None:
        return client
    session_id = os.environ.get("CLPBFF_SESSION")
    api_key = os.environ.get("X_CG_APIKEY")
    place_id = os.environ.get("COLRUYT_PLACE_ID")
    if not session_id:
        return None
    return ColruytClient(session_id=session_id, api_key=api_key, place_id=place_id)

@server.list_tools()
async def handle_list_tools() -> List[types.Tool]:
    return [
        types.Tool(
            name="resolve_ingredient",
            description="Resolve an ingredient string to its corresponding supermarket product id using local SQLite fuzzy matching and search API. Use this tool whenever the user asks to resolve, search, or find a product ID for a single ingredient or item. If ambiguous, up to 5 options are returned from the list. The sixth option is 'other' and if chosen, increase offset by 5 on the next call.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ingredient": {"type": "string", "description": "Ingredient string to resolve"},
                    "offset": {"type": "integer", "description": "Offset for options pagination (default: 0)"}
                },
                "required": ["ingredient"]
            }
        ),
        types.Tool(
            name="add_items_to_list",
            description="Add products to the user's supermarket shopping list. Use this tool whenever the user asks to add product IDs or items directly to their shopping list.",
            inputSchema={
                "type": "object",
                "properties": {
                    "product_ids": {
                        "type": "array", 
                        "items": {"type": "string"},
                        "description": "List of product IDs"
                    }
                },
                "required": ["product_ids"]
            }
        ),
        types.Tool(
            name="add_recipe_to_list",
            description="Parse a recipe markdown file and add ingredients to the shopping list. Use this tool whenever the user asks to add all ingredients from a recipe file to their shopping list.",
            inputSchema={
                "type": "object",
                "properties": {
                    "recipe_filename": {"type": "string", "description": "Full path to the recipe markdown file"}
                },
                "required": ["recipe_filename"]
            }
        ),
        types.Tool(
            name="resolve_recipe",
            description="Resolve all ingredients in a recipe using LLM extraction and product id resolution. Use this tool whenever the user asks to resolve, check, or look up products for all ingredients in a recipe without modifying the file. Prompts for one ambiguous ingredient at a time.",
            inputSchema={
                "type": "object",
                "properties": {
                    "recipe_filename": {
                        "type": "string",
                        "description": "Full path to the recipe markdown file"
                    },
                    "recipe_content": {
                        "type": "string",
                        "description": "Direct markdown content of the recipe (optional if recipe_filename is provided)"
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Pagination offset if user chooses 'Other' for the current ambiguous ingredient (default: 0)"
                    }
                }
            }
        ),
        types.Tool(
            name="annotate_recipe_with_productids",
            description="Extract and resolve all ingredients in a recipe markdown file to product ids and append or update a '## Resolved Products' section at the end of the file (format: '- <ingredient> [productId=<id>]'). Use this tool whenever the user asks to annotate, add, or append resolved product IDs to a recipe markdown file. Only writes to the file when 100% of ingredients are resolved; if ingredients are ambiguous or unmapped, returns progress and options to prompt the user.",
            inputSchema={
                "type": "object",
                "properties": {
                    "recipe_filename": {
                        "type": "string",
                        "description": "Full path to the recipe markdown file"
                    },
                    "offset": {
                        "type": "integer",
                        "description": "Pagination offset if user chooses 'Other' for the current ambiguous ingredient (default: 0)"
                    }
                },
                "required": ["recipe_filename"]
            }
        ),
        types.Tool(
            name="store_resolved_product",
            description="Store a resolved product mapping for an ingredient in the local SQLite database after a user selection. Use this tool whenever the user asks to store, save, remember, or map a product selection for an ingredient.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ingredient": {"type": "string", "description": "Ingredient string (e.g. from resolve_ingredient or recipe)"},
                    "product_id": {"type": "string", "description": "Selected Colruyt product ID"},
                    "name": {"type": "string", "description": "Product name"},
                    "brand": {"type": "string", "description": "Product brand (optional)"},
                    "top_category_name": {"type": "string", "description": "Product top category name (optional)"}
                },
                "required": ["ingredient", "product_id", "name"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
    client = get_client()
    if not client or not client.session_id:
        return [types.TextContent(
            type="text",
            text="Error: Colruyt client not properly initialized. "
                 "Please set the CLPBFF_SESSION environment variable or pass --session-id at server startup."
        )]

    try:
        if name == "resolve_ingredient":
            ingredient = arguments["ingredient"]
            offset = arguments.get("offset", 0)
            query, resolved = await resolve_ingredient(ingredient, client)

            if isinstance(resolved, Product):
                info_lines = [
                    f"Product Resolved:",
                    f"- Normalized Ingredient: {query}",
                    f"- Name: {resolved.name}",
                    f"- Product ID: {resolved.product_id}",
                    f"- Brand: {resolved.brand or 'N/A'}",
                    f"- Content: {resolved.content or 'N/A'}",
                    f"- Description: {resolved.description or 'N/A'}",
                    f"- Conservation: {resolved.conservation_info or 'N/A'}",
                    f"- Usage Info: {resolved.usage_info or 'N/A'}"
                ]
                return [types.TextContent(type="text", text="\n".join(info_lines))]
            elif isinstance(resolved, list) and resolved:
                page_size = 5
                batch = resolved[offset : offset + page_size]
                options = [f"{i+1}. {p.name} ({p.product_id})" for i, p in enumerate(batch)]
                if (offset + len(batch)) < len(resolved):
                    options.append(f"{len(batch)+1}. Other")
                return [types.TextContent(type="text", text=f"Ambiguous ingredient '{ingredient}' (normalized: '{query}'). Options:\n" + "\n".join(options))]
            else:
                return [types.TextContent(type="text", text=f"No product found for '{ingredient}' (normalized: '{query}').")]

        elif name == "add_items_to_list":
            ids = arguments["product_ids"]
            dummy_products = [Product(name=f"Product {id}", product_id=id) for id in ids]
            updated_list = await client.add_items_to_list(dummy_products)
            return [types.TextContent(type="text", text=f"Added {len(ids)} items. Current list has {len(updated_list)} items.")]

        elif name == "add_recipe_to_list":
            path = arguments["recipe_filename"]
            if not os.path.exists(path):
                return [types.TextContent(type="text", text=f"Error: File '{path}' not found.")]

            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

            error, result = await resolve_recipe_ingredients(content, client)
            if error or result is None:
                return [types.TextContent(type="text", text=f"Error: {error}")]

            to_add = [prod for _, prod in result.resolved]
            if to_add:
                await client.add_items_to_list(to_add)

            results_lines = []
            for ing, prod in result.resolved:
                results_lines.append(f"✅ {format_ingredient_label(ing)} -> {prod.name}")
            for ing, _, _ in result.ambiguous:
                results_lines.append(f"❓ {format_ingredient_label(ing)} (Ambiguous)")
            for ing, _ in result.not_found:
                results_lines.append(f"❌ {format_ingredient_label(ing)} (Not found)")

            response_text = "Recipe processing results:\n" + "\n".join(results_lines)
            if result.ambiguous:
                response_text += "\n\nSome ingredients are ambiguous. Please choose from the following:\n"
                for ing, _, options in result.ambiguous:
                    label = format_ingredient_label(ing)
                    response_text += f"\nFor '{label}':\n"
                    page_size = 5
                    batch = options[:page_size]
                    for i, opt in enumerate(batch):
                        response_text += f"  {i+1}. {opt.name} ({opt.product_id})\n"
                    if len(options) > page_size:
                        response_text += f"  {len(batch)+1}. Other\n"

            return [types.TextContent(type="text", text=response_text)]

        elif name == "resolve_recipe":
            content = arguments.get("recipe_content")
            filename = arguments.get("recipe_filename")
            offset = arguments.get("offset", 0)

            if not content and filename:
                if not os.path.exists(filename):
                    return [types.TextContent(type="text", text=f"Error: Recipe file '{filename}' not found.")]
                with open(filename, "r", encoding="utf-8") as f:
                    content = f.read()

            if not content:
                return [types.TextContent(type="text", text="Error: Either recipe_filename or recipe_content must be provided.")]

            error, result = await resolve_recipe_ingredients(content, client)
            if error or result is None:
                return [types.TextContent(type="text", text=f"Error: {error}")]

            return [types.TextContent(type="text", text=format_resolution_progress(result, offset))]

        elif name == "annotate_recipe_with_productids":
            filename = arguments["recipe_filename"]
            offset = arguments.get("offset", 0)

            if not os.path.exists(filename):
                return [types.TextContent(type="text", text=f"Error: Recipe file '{filename}' not found.")]

            with open(filename, "r", encoding="utf-8") as f:
                content = f.read()

            error, result = await resolve_recipe_ingredients(content, client)
            if error or result is None:
                return [types.TextContent(type="text", text=f"Error: {error}")]

            if not result.is_complete:
                progress_text = format_resolution_progress(result, offset)
                return [types.TextContent(
                    type="text",
                    text=f"Cannot annotate recipe: not all ingredients are resolved ({result.resolved_count}/{result.total_count} resolved).\n\n{progress_text}"
                )]

            products_list_md = format_resolved_products_list(result.resolved)
            updated_content = append_or_update_recipe_section(content, "Resolved Products", products_list_md)

            with open(filename, "w", encoding="utf-8") as f:
                f.write(updated_content)

            return [types.TextContent(
                type="text",
                text=f"Successfully annotated recipe '{filename}' with {len(result.resolved)} resolved products in '## Resolved Products' section:\n\n{products_list_md}"
            )]

        elif name == "store_resolved_product":
            ingredient = arguments.get("ingredient")
            product_id = arguments["product_id"]
            name_arg = arguments["name"]
            brand_arg = arguments.get("brand")
            top_category_name_arg = arguments.get("top_category_name")
            stored = await store_resolved_product(
                ingredient=ingredient,
                product_id=product_id,
                name=name_arg,
                brand=brand_arg,
                client=client,
                top_category_name=top_category_name_arg
            )
            return [types.TextContent(
                type="text",
                text=f"Stored resolved product: '{ingredient}' -> {stored.name} ({stored.product_id})"
            )]

        else:
            return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]

async def main():
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
    
    client = ColruytClient(session_id=session_id, api_key=api_key, place_id=place_id)

    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="colruyt-xtra",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={}
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())
