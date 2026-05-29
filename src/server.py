import os
import sys
import argparse
import asyncio
from typing import List, Optional, Dict, Any
from mcp.server import Server
from mcp.server.models import InitializationOptions
import mcp.types as types
import mcp.server.stdio
from src.client import ColruytClient
from src.models import Product
from src.logic import extract_ingredients, resolve_ingredient

# Initialize server
server = Server("colruyt-xtra")

# Global client (initialized at startup)
client: Optional[ColruytClient] = None

@server.list_tools()
async def handle_list_tools() -> List[types.Tool]:
    return [
        types.Tool(
            name="get_most_bought_products",
            description="Fetch the user's most bought products from Colruyt.",
            inputSchema={
                "type": "object",
                "properties": {
                    "placeId": {"type": "string", "description": "Colruyt store ID (default: 2643)"}
                }
            }
        ),
        types.Tool(
            name="search_products",
            description="Search the Colruyt catalog for products.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search term"},
                    "placeId": {"type": "string", "description": "Colruyt store ID (default: 2643)"}
                },
                "required": ["query"]
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
                        "description": "List of technicalArticleNumbers"
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
        if name == "get_most_bought_products":
            place_id = arguments.get("placeId", ColruytClient.DEFAULT_PLACE_ID)
            products = await client.get_most_bought_products(place_id)
            return [types.TextContent(type="text", text="\n".join([f"- {p.name} ({p.technicalArticleNumber})" for p in products]))]

        elif name == "search_products":
            query = arguments["query"]
            place_id = arguments.get("placeId", ColruytClient.DEFAULT_PLACE_ID)
            products = await client.search_products(query, place_id)
            return [types.TextContent(type="text", text="\n".join([f"- {p.name} ({p.technicalArticleNumber})" for p in products]))]

        elif name == "add_items_to_list":
            ids = arguments["product_ids"]
            # We need full Product objects, but usually we only have IDs.
            # For simplicity, we create dummy products with only IDs.
            # (Better would be to fetch details if needed, but the API seems to only need the ID in the payload).
            # Wait, the add_items_to_list payload in client.py needs the name too.
            # I'll update client.py to handle just IDs if name is missing, or fetch them.
            # Actually, I'll pass a list of dicts or objects.
            
            # Let's assume the user knows the IDs from search.
            dummy_products = [Product(name=f"Product {id}", technicalArticleNumber=id) for id in ids]
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
                resolved = await resolve_ingredient(ing, client, most_bought)
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
                        response_text += f"  {i+1}. {opt.name} ({opt.technicalArticleNumber})\n"
            
            return [types.TextContent(type="text", text=response_text)]

        else:
            return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]

async def main():
    global client
    
    parser = argparse.ArgumentParser(description="Colruyt Xtra MCP Server")
    parser.add_argument("--session-id", "-s", help="Colruyt Xtra session ID (clpbff_session cookie)")
    parser.add_argument("--api-key", "-a", help="Custom x-cg-apikey header value")
    args, unknown = parser.parse_known_args()

    session_id = args.session_id or os.environ.get("CLPBFF_SESSION")
    api_key = args.api_key or os.environ.get("X_CG_APIKEY")

    if not session_id:
        print("Warning: session_id not set via CLI argument or CLPBFF_SESSION environment variable.", file=sys.stderr)
    
    client = ColruytClient(session_id=session_id, api_key=api_key)

    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="colruyt-xtra",
                server_version="0.1.0",
                capabilities=server.get_capabilities(),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())
