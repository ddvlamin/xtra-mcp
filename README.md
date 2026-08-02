# Colruyt Xtra MCP Server

An MCP server for the Colruyt Xtra app, allowing AI assistants to manage your shopping list and process recipes.

## Features

- **resolve_ingredient**: Resolve an ingredient string to a Colruyt product using local SQLite fuzzy matching, catalog search API, and purchase history.
- **store_resolved_product**: Save user-selected product mappings to the local SQLite database for future automatic matching.
- **add_items_to_list**: Add products directly to your Colruyt shopping list.
- **add_recipe_to_list**: Parse markdown recipe files and add ingredients with intelligent disambiguation.

## Environment Variables

The server requires the following environment variables (see `.env.example`):

| Variable | Description | Example / Default |
| --- | --- | --- |
| `CLPBFF_SESSION` | Colruyt Xtra session cookie ID | `your_session_id_here` |
| `X_CG_APIKEY` | Colruyt Xtra API key (or `COLRUYT_API_KEY`) | `your_api_key_here` |
| `COLRUYT_PLACE_ID` | Colruyt store / place ID | `2643` |

## Setup

1. Clone the repository.
2. Install dependencies using `uv`:
   ```bash
   uv sync
   ```
3. Set environment variables in your environment or `.env` file:
   ```bash
   export CLPBFF_SESSION="your_session_id"
   export X_CG_APIKEY="your_api_key_here"
   export COLRUYT_PLACE_ID="2643"
   ```

## Running the Server

```bash
python xtra/server.py
```

## AGY CLI MCP Configuration

To install `server.py` as an MCP server in AGY CLI, add `colruyt-xtra` to `mcp_config.json` (located at `~/.gemini/antigravity-cli/mcp_config.json`):

```json
{
  "mcpServers": {
    "colruyt-xtra": {
      "command": "python",
      "args": [
        "-m",
        "xtra.server"
      ],
      "cwd": "/path/to/xtra-mcp",
      "env": {
        "PYTHONPATH": "/path/to/xtra-mcp",
        "CLPBFF_SESSION": "your_session_id",
        "X_CG_APIKEY": "your_api_key_here",
        "COLRUYT_PLACE_ID": "2643"
      }
    }
  }
}
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
