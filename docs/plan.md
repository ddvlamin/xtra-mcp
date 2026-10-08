# Plan: Architecture Refactoring & Recipe Separation

Split codebase into three distinct directories under `xtra/`:
1. `xtra/sdk/`: Supermarket client interface & Colruyt API implementation.
2. `xtra/catalog/`: Local SQLite product DB, interactive CLI ingestion script, and recipe annotation script.
3. `xtra/mcp/`: Focused MCP server for AI agent to lookup products in DB, add/remove items by ID, and view shopping list.

---

## Directory Structure Target

```
xtra/
├── sdk/
│   ├── __init__.py
│   ├── client.py           # SupermarketClient abstract base class / protocol
│   ├── colruyt.py          # ColruytClient implementation (includes add_recipe method)
│   └── models.py           # Product, ListItem, ExtractedIngredient domain models
├── catalog/
│   ├── __init__.py
│   ├── db.py               # SQLite database access (resources/colruyt_products.db)
│   ├── extractor.py        # Markdown parser for ## Ingredients & ## Resolved Products
│   ├── ingest.py           # Interactive CLI to search Colruyt API and populate DB (no recipe edit)
│   └── annotate.py         # CLI to lookup DB and annotate recipe files in-place with product IDs
└── mcp/
    ├── __init__.py
    └── server.py           # FastMCP server exposing lookup_products, add_items, remove_items, get_shopping_list
```

---

## Detailed Steps & Verification

### Step 1: Supermarket SDK Layer (`xtra/sdk`)
- In [xtra/sdk/client.py](file:///workspace/xtra/sdk/client.py):
  - Define `SupermarketClient` interface.
  - Abstract methods:
    - `search_products(query, place_id=None)`
    - `get_most_bought_products(place_id=None)`
    - `get_product_info(product_id, gtin=None)`
    - `add_items_to_list(products)`
    - `get_shopping_list()`
    - `remove_item_from_list(item_id: str)`
    - `add_recipe(recipe_path: str)`
- In [xtra/sdk/colruyt.py](file:///workspace/xtra/sdk/colruyt.py):
  - Implement `get_shopping_list()` calling `GET /gateway/emec.colruyt.bffsvc/cg/latest-shopping-list`.
  - Implement `remove_item_from_list(item_id: str)` calling `DELETE /gateway/emec.colruyt.bffsvc/cg/remove-item-from-list/{item_id}`.
  - Implement `add_recipe(recipe_path: str)`:
    - Parse `[productId=...]` from the annotated recipe markdown file.
    - Check that resolved products exist; warn if empty or incomplete.
    - Call `self.add_items_to_list(...)` with the extracted product IDs.
- In [xtra/sdk/models.py](file:///workspace/xtra/sdk/models.py):
  - Unified `Product`, `ListItem`, `ExtractedIngredient`, and shopping list DTOs.
- **Verify**: Unit tests with mock responses for `get_shopping_list`, `remove_item_from_list`, and `add_recipe` pass in `tests/test_client.py`.

### Step 2: Recipe Annotation & Catalog Layer (`xtra/catalog`)
- In [xtra/catalog/db.py](file:///workspace/xtra/catalog/db.py):
  - Retain SQLite persistence against [resources/colruyt_products.db](file:///workspace/resources/colruyt_products.db).
  - Provide `store_product(product)`, `get_product(query)`, `find_product(query, threshold=80)`, `get_all_products()`.
- In [xtra/catalog/extractor.py](file:///workspace/xtra/catalog/extractor.py):
  - Ingredient parsing from `## Ingredients`.
  - Parse existing `## Resolved Products` (`- <name> (<quantity>) [productId=<id>]`).
  - Helper to update/append `## Resolved Products` section in markdown in-place.
- In [xtra/catalog/ingest.py](file:///workspace/xtra/catalog/ingest.py) (Interactive DB Ingestion CLI):
  - Accepts `--file <path>` or `--dir <path>`.
  - Extracts ingredients from recipe(s).
  - For each ingredient:
    - Check if already exists in DB (`db.find_product`). If found, report and continue.
    - If not in DB, search Colruyt API via `client.search_products(query)`.
    - Interactively prompt user in terminal with top candidate products (numbered options, custom query, or skip).
    - On confirmation, store selected product in SQLite DB.
    - **Important**: Does NOT modify the recipe markdown files.
- In [xtra/catalog/annotate.py](file:///workspace/xtra/catalog/annotate.py) (Recipe Annotation CLI):
  - Accepts `--file <path>` or `--dir <path>`.
  - For each recipe file:
    - Extract ingredients from `## Ingredients`.
    - Look up each ingredient strictly in SQLite DB.
    - For ingredients found: record mapped `productId`.
    - For ingredients not found: emit terminal warning `[WARNING] Ingredient '<name>' not found in database. Run ingest first.`
    - Annotate recipe file in-place, adding/updating `## Resolved Products` section matching format:
      `- <ingredient> (<quantity>) [productId=<id>]`.
- **Verify**: Unit tests for:
  - `ingest.py` candidate confirmation and DB storage.
  - `annotate.py` in-place file updates and missing item warnings.

### Step 3: Focused MCP Server (`xtra/mcp`)
- In [xtra/mcp/server.py](file:///workspace/xtra/mcp/server.py):
  - FastMCP server exposing 4 explicit agent tools:
    1. `lookup_products_in_database(names: List[str])`:
       - Queries local SQLite DB (`Database.find_product`) for each name.
       - Returns list of matched products (query, product_id, name, brand) and list of unresolved names.
       - Allows the agent to inspect matches and warn user about missing items *before* mutating the list.
    2. `add_items_to_list(product_ids: List[str])`:
       - Accepts explicit `product_ids` (obtained from lookup or recipe).
       - Calls `client.add_items_to_list` to push products to Colruyt cart.
       - Returns added items and updated shopping list count.
    3. `get_shopping_list()`:
       - Calls `client.get_shopping_list()`.
       - Returns current active shopping list items (item UUID `id`, description, product ID, completion status).
    4. `remove_items_from_list(item_ids: List[str])`:
       - Accepts list item UUIDs (obtained from `get_shopping_list`).
       - Calls `client.remove_item_from_list(item_id)` for each UUID.
       - Returns removed items confirmation.
  - Remove deprecated interactive session tools from MCP server.
- **Verify**: MCP tools test suite verifies DB lookup, product ID addition, list retrieval, and item deletion by ID.

### Step 4: Cleanup & Entrypoints
- Clean up root `xtra/` legacy files (`session.py`, `formatting.py`, `logic.py`).
- Update `pyproject.toml` console scripts / entrypoints:
  - `xtra-mcp` -> `xtra.mcp.server:main`
  - `xtra-ingest` -> `xtra.catalog.ingest:main`
  - `xtra-annotate` -> `xtra.catalog.annotate:main`
- Update [README.md](file:///workspace/README.md) and [AGENTS.md](file:///workspace/AGENTS.md) with new structure and usage guidelines.
- Run complete test suite (`pytest tests/`) to ensure all tests pass.