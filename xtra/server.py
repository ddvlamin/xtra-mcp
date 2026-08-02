import os
import sys
import argparse
import asyncio
from typing import List, Optional, Dict, Any
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.types as types
import mcp.server.stdio
from xtra.client import SupermarketClient
from xtra.colruyt import ColruytClient
from xtra.models import Product
from xtra.logic import (
    extract_ingredients,
    resolve_ingredient,
    store_resolved_product
)

# Initialize server
server = Server("colruyt-xtra")

# Global client (initialized at startup)
client: Optional[SupermarketClient] = None

@server.list_tools()
async def handle_list_tools() -> List[types.Tool]:
    return [
        types.Tool(
            name="resolve_ingredient",
            description="Resolve an ingredient string to a Colruyt product using local SQLite fuzzy matching, search API, and most bought history.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ingredient": {"type": "string", "description": "Ingredient string to resolve"}
                },
                "required": ["ingredient"]
            }
        ),
        types.Tool(
            name="add_items_to_list",
            description="Add products to the user's Colruyt shopping list.",
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
            description="Parse a recipe markdown file and add ingredients to the shopping list.",
            inputSchema={
                "type": "object",
                "properties": {
                    "recipe_filename": {"type": "string", "description": "Filename in recipes/ folder"}
                },
                "required": ["recipe_filename"]
            }
        ),
        types.Tool(
            name="store_resolved_product",
            description="Store a resolved product mapping for a normalized ingredient in the local SQLite database after a user selection.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ingredient": {"type": "string", "description": "Normalized ingredient string (e.g. from resolve_ingredient)"},
                    "product_id": {"type": "string", "description": "Selected Colruyt product ID"},
                    "name": {"type": "string", "description": "Product name"},
                    "brand": {"type": "string", "description": "Product brand (optional)"}
                },
                "required": ["ingredient", "product_id", "name"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
    global client
    if not client or not client.session_id:
        return [types.TextContent(
            type="text",
            text="Error: Colruyt client not properly initialized. "
                 "Please set the CLPBFF_SESSION environment variable or pass --session-id at server startup."
        )]

    try:
        if name == "resolve_ingredient":
            ingredient = arguments["ingredient"]
            most_bought = await client.get_most_bought_products()
            query, resolved = await resolve_ingredient(ingredient, client, most_bought)

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
                options = [f"- {p.name} ({p.product_id})" for p in resolved]
                return [types.TextContent(type="text", text=f"Ambiguous ingredient '{ingredient}' (normalized: '{query}'). Options:\n" + "\n".join(options))]
            else:
                return [types.TextContent(type="text", text=f"No product found for '{ingredient}' (normalized: '{query}').")]

        elif name == "add_items_to_list":
            ids = arguments["product_ids"]
            dummy_products = [Product(name=f"Product {id}", product_id=id) for id in ids]
            updated_list = await client.add_items_to_list(dummy_products)
            return [types.TextContent(type="text", text=f"Added {len(ids)} items. Current list has {len(updated_list)} items.")]

        elif name == "add_recipe_to_list":
            filename = arguments["recipe_filename"]
            path = os.path.join("recipes", filename)
            if not os.path.exists(path):
                return [types.TextContent(type="text", text=f"Error: File {path} not found.")]

            with open(path, "r") as f:
                content = f.read()

            ingredients = extract_ingredients(content)
            most_bought = await client.get_most_bought_products()
            
            results = []
            to_add = []
            ambiguous = []
            
            for ing in ingredients:
                query, resolved = await resolve_ingredient(ing, client, most_bought)
                if isinstance(resolved, Product):
                    to_add.append(resolved)
                    results.append(f"✅ {ing} -> {resolved.name}")
                elif isinstance(resolved, list) and resolved:
                    ambiguous.append((ing, resolved))
                    results.append(f"❓ {ing} (Ambiguous)")
                else:
                    results.append(f"❌ {ing} (Not found)")

            if to_add:
                await client.add_items_to_list(to_add)
            
            response_text = "Recipe processing results:\n" + "\n".join(results)
            if ambiguous:
                response_text += "\n\nSome ingredients are ambiguous. Please choose from the following:\n"
                for ing, options in ambiguous:
                    response_text += f"\nFor '{ing}':\n"
                    for i, opt in enumerate(options):
                        response_text += f"  {i+1}. {opt.name} ({opt.product_id})\n"
            
            return [types.TextContent(type="text", text=response_text)]

        elif name == "store_resolved_product":
            ingredient = arguments.get("normalized_ingredient") or arguments["ingredient"]
            product_id = arguments["product_id"]
            name_arg = arguments["name"]
            brand_arg = arguments.get("brand")
            stored = await store_resolved_product(
                ingredient=ingredient,
                product_id=product_id,
                name=name_arg,
                brand=brand_arg,
                client=client
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
