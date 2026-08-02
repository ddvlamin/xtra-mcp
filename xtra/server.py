import os
import asyncio
from typing import List, Optional, Dict, Any
from mcp.server import Server
from mcp.server.models import InitializationOptions
import mcp.types as types
import mcp.server.stdio
from xtra.client import ColruytClient
from xtra.models import Product
from xtra.logic import (
    extract_ingredients,
    resolve_ingredient,
    save_product_mapping_logic
)

# Initialize server
server = Server("colruyt-xtra")

# Global client (initialized at startup)
client: Optional[ColruytClient] = None

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
            name="save_product_mapping",
            description="Save or update a mapping between a cleaned ingredient name and a Colruyt product ID into persistent SQLite storage, automatically scraping rich product metadata.",
            inputSchema={
                "type": "object",
                "properties": {
                    "cleaned_ingredient": {"type": "string", "description": "Cleaned ingredient name (e.g. 'kipfilet')"},
                    "product_id": {"type": "string", "description": "Colruyt technicalArticleNumber"},
                    "product_name": {"type": "string", "description": "Product display name"},
                    "product_brand": {"type": "string", "description": "Optional brand name"}
                },
                "required": ["cleaned_ingredient", "product_id", "product_name"]
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
    if not client:
        return [types.TextContent(type="text", text="Error: Client not initialized. Please provide session_id.")]

    try:
        if name == "resolve_ingredient":
            ingredient = arguments["ingredient"]
            most_bought = await client.get_most_bought_products()
            resolved = await resolve_ingredient(ingredient, client, most_bought)

            if isinstance(resolved, Product):
                info_lines = [
                    f"Product Resolved:",
                    f"- Name: {resolved.name}",
                    f"- Product ID: {resolved.technicalArticleNumber}",
                    f"- Brand: {resolved.brand or 'N/A'}",
                    f"- Content: {resolved.content or 'N/A'}",
                    f"- Description: {resolved.description or 'N/A'}",
                    f"- Conservation: {resolved.conservation_info or 'N/A'}",
                    f"- Usage Info: {resolved.usage_info or 'N/A'}"
                ]
                return [types.TextContent(type="text", text="\n".join(info_lines))]
            elif isinstance(resolved, list) and resolved:
                options = [f"- {p.name} ({p.technicalArticleNumber})" for p in resolved]
                return [types.TextContent(type="text", text=f"Ambiguous ingredient '{ingredient}'. Options:\n" + "\n".join(options))]
            else:
                return [types.TextContent(type="text", text=f"No product found for '{ingredient}'.")]

        elif name == "save_product_mapping":
            cleaned_ingredient = arguments["cleaned_ingredient"]
            product_id = arguments["product_id"]
            product_name = arguments["product_name"]
            product_brand = arguments.get("product_brand")
            
            mapping = await save_product_mapping_logic(
                cleaned_ingredient=cleaned_ingredient,
                product_id=product_id,
                product_name=product_name,
                product_brand=product_brand
            )
            return [types.TextContent(type="text", text=(
                f"Saved product mapping successfully:\n"
                f"- Cleaned Ingredient: {mapping.cleaned_ingredient}\n"
                f"- Product ID: {mapping.product_id}\n"
                f"- Product Name: {mapping.product_name}\n"
                f"- Brand: {mapping.product_brand or 'N/A'}\n"
                f"- Content: {mapping.content or 'N/A'}\n"
                f"- Description: {mapping.product_description or 'N/A'}\n"
                f"- Conservation: {mapping.conservation_info or 'N/A'}\n"
                f"- Usage Info: {mapping.usage_info or 'N/A'}"
            ))]

        elif name == "add_items_to_list":
            ids = arguments["product_ids"]
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
    session_id = os.environ.get("CLPBFF_SESSION")
    api_key = os.environ.get("X_CG_APIKEY")
    place_id = os.environ.get("COLRUYT_PLACE_ID")

    if not session_id:
        print("Warning: CLPBFF_SESSION environment variable not set.")
    
    client = ColruytClient(session_id=session_id, api_key=api_key, place_id=place_id)

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
