# Colruyt Xtra MCP Server

An MCP server for the Colruyt Xtra app, allowing AI assistants to manage your shopping list and process recipes.

## Features

- **get_most_bought_products**: Fetch your frequently purchased items.
- **search_products**: Search the Colruyt catalog.
- **add_items_to_list**: Add products directly to your list.
- **add_recipe_to_list**: Parse markdown recipes and add ingredients with intelligent disambiguation.

## Setup

1. Clone the repository.
2. Install dependencies using `uv`:
   ```bash
   uv sync
   ```
3. Set your environment variables (see `.env.example`):
   ```bash
   export CLPBFF_SESSION=your_session_id
   ```

## Running the Server

```bash
python src/server.py
```

## Recipe Integration

Place your markdown recipes in the `recipes/` folder. The server expects ingredients to be listed under a `## 🛒 Ingrediënten` header.

Example:
```markdown
## 🛒 Ingrediënten
* **Eiwit:** 3 kipfilets
* **Groenten:** 1 rode paprika
```

## Intelligent Disambiguation

When adding a recipe, the server:
1. Searches for the ingredient.
2. If multiple products match, it cross-references them with your "most bought" list.
3. If it find a match you've bought before, it selects it automatically.
4. Otherwise, it returns the options for the AI to ask you for confirmation.
