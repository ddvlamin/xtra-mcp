Project-specific instructions for future interactions to interact with this code base. 

**Always use caveman skill**

## 1. Project Purpose
Toolkit and MCP server for Colruyt Supermarket integration: SDK client layer (`xtra/sdk`), local SQLite product catalog & recipe annotator (`xtra/catalog`), and focused MCP server (`xtra/mcp`).

## 2. Key Systems & Services: Colruyt Xtra MCP Server
Always use the `colruyt-xtra` MCP tools for agent supermarket interactions.

Primary MCP Tools:
- `lookup_products_in_database(names=[...])`: Check local SQLite database for product matches; returns matches and warnings for missing items.
- `add_items_to_list(product_ids=[...])`: Add items to Colruyt cart using validated product IDs.
- `get_shopping_list()`: Retrieve active shopping list items with item UUIDs and product details.
- `remove_items_from_list(item_ids=[...])`: Remove items from cart by list item UUID.

Recipe & Catalog CLIs:
- `xtra-ingest` (`xtra/catalog/ingest.py`): Interactive CLI tool to query Colruyt API for recipe ingredients and store user-confirmed products in SQLite DB. Does not modify recipe files.
- `xtra-annotate` (`xtra/catalog/annotate.py`): In-place recipe annotator. Resolves ingredients from SQLite DB, warns on missing items, and writes `## Resolved Products` with `[productId=...]`.
- `client.add_recipe(recipe_path)`: Deterministic SDK method on `ColruytClient` to add all resolved product IDs from an annotated recipe file directly to cart.

## 3. Behavioral guidelines to reduce common LLM coding mistakes.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

### 1. Think Before Coding
**Don't assume. Don't hide confusion. Surface tradeoffs.**
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First
**Minimum code that solves the problem. Nothing speculative.**
- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.

### 3. Surgical Changes
**Touch only what you must. Clean up only your own mess.**
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution
**Define success criteria. Loop until verified.**
Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

### Shell Command Rules
- Double quote all file paths containing spaces: `"path/to/My File.txt"`
- Never use backslash-escaped whitespace: `path/to/My\ File.txt`
- Always validate Bash scripts with ShellCheck.