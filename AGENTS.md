Project-specific instructions for future interactions to interact with this code base. 

**Always use caveman skill**

## 1. Project Purpose
MCP server and toolkit for Colruyt Supermarket integration: ingredient resolution, product search, SQLite mapping persistence, and shopping list management.

## 2. Key Systems & Services: Colruyt Xtra MCP Server
Always use the `colruyt-xtra` MCP tools for supermarket interactions. **NEVER run CLI bash scripts (e.g. `scripts/search.py`) when resolving or searching products.**

Primary MCP Tools:
- `start_recipe_resolution(ingredients=[...])`: Use for searching/resolving single or multiple products/ingredients, or full recipe files.
- `resolve_ingredient_choice(session_id=..., selected_product_id=...)`: Confirm candidate choice and advance.
- `paginate_active_ingredient(session_id=..., offset=...)`: Next page of candidates.
- `add_items_to_list(product_ids=[...])`: Add items to Colruyt cart.
- `add_recipe_to_list(recipe_filename=...)`: Resolve recipe and add to cart.

## 3. Behavioral guidelines to reduce common LLM coding mistakes.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
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
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

## 7. Behavioral guidelines to reduce common LLM coding mistakes.

### Shell Command Rules
- Double quote all file paths containing spaces: `"path/to/My File.txt"`
- Never use backslash-escaped whitespace: `path/to/My\ File.txt`
- Always validate Bash scripts with ShellCheck.