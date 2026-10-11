# Colruyt Xtra MCP Server & Catalog Toolkit

A modular Python toolkit and MCP server for the Colruyt Xtra supermarket service:
- **`xtra/sdk`**: Clean Supermarket API client layer (Colruyt BFF endpoints).
- **`xtra/catalog`**: Local SQLite product database, interactive ingredient lookup CLI (`xtra-ingest`), and deterministic recipe annotator (`xtra-annotate`).
- **`xtra/mcp`**: FastMCP server providing explicit shopping list management tools for AI agents.

---

## Architecture Overview

```
xtra/
├── sdk/                # Generic client interface & Colruyt API implementation
│   ├── client.py       # SupermarketClient abstract class
│   ├── colruyt.py      # ColruytClient (includes add_recipe method)
│   └── models.py       # Domain models (Product, ListItem, ExtractedIngredient)
├── catalog/            # Recipe annotation & local DB management
│   ├── db.py           # SQLite database persistence (resources/colruyt_products.db)
│   ├── extractor.py    # Markdown parsing for ## Ingredients & ## Resolved Products
│   ├── ingest.py       # Interactive CLI to map ingredients to Colruyt products in DB
│   └── annotate.py     # CLI to look up DB and annotate recipes in-place with product IDs
└── mcp/                # Focused MCP server for AI agents
    └── server.py       # FastMCP tools: lookup_products, add_items, remove_items, get_shopping_list
```

---

## MCP Server Tools

1. **`lookup_products_in_database(names: List[str])`**:
   Look up product names in the local SQLite database. Returns matched product IDs and warnings for unresolved names.
2. **`add_items_to_list(product_ids: List[str])`**:
   Add items directly to the Colruyt shopping cart by their product IDs.
3. **`get_shopping_list(limit: int = 255, offset: int = 0)`**:
   Retrieve active items on the Colruyt shopping list with item UUIDs and completion status.
4. **`remove_items_from_list(item_ids: List[str])`**:
   Remove items from the Colruyt shopping list by their item UUIDs.

---

## CLI Tools

### 1. Ingest Recipe Ingredients (`xtra-ingest`)
Interactively resolve ingredients from recipes against the Colruyt API and store confirmed mappings in SQLite (`resources/colruyt_products.db`). Does **not** modify recipe files.

```bash
# Ingest from a single recipe
uv run xtra-ingest --file "recipes/Vol-au-vent.md"

# Ingest from a directory of recipes
uv run xtra-ingest --dir "recipes/"
```

### 2. Annotate Recipes In-Place (`xtra-annotate`)
Reads recipe ingredients, matches against local SQLite DB, emits warnings for missing items, and writes `## Resolved Products` with `[productId=...]` directly into the recipe markdown.

```bash
# Annotate a single recipe
uv run xtra-annotate --file "recipes/Vol-au-vent.md"

# Annotate all recipes in a folder
uv run xtra-annotate --dir "recipes/"
```

---

## Python SDK: Deterministic Recipe Cart Addition

To add an annotated recipe directly to your Colruyt shopping cart without LLM disambiguation:

```python
import asyncio
from xtra.sdk.colruyt import ColruytClient

async def main():
    client = ColruytClient()
    added_items = await client.add_recipe("recipes/Vol-au-vent.md")
    print(f"Added {len(added_items)} items to cart.")

asyncio.run(main())
```

---

## Environment Variables

| Variable | Description | Default |
| --- | --- | --- |
| `CLPBFF_SESSION` | Colruyt Xtra session cookie ID (`clpbff_session`) | None |
| `X_CG_APIKEY` | Colruyt API key (`x-cg-apikey`) | Colruyt default |
| `COLRUYT_PLACE_ID` | Store ID (`placeId`) | `2643` |

---

## Running the MCP Server

```bash
uv run --no-dev xtra-mcp
```
