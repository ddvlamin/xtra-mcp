Colruyt Xtra MCP Server Implementation Plan                                                                                                                                      │
│                                                                                                                                                                                  │
│ Background & Motivation                                                                                                                                                          │
│ The user wants to build a Model Context Protocol (MCP) server for the Colruyt Xtra app. This server will enable an AI assistant to fetch their most bought items, search for     │
│ products, and add items to their shopping list. Additionally, the assistant needs a specific skill to read recipes from local markdown files in a recipes/ folder, parse the     │
│ ingredients, and seamlessly add them to the list. When an ingredient search is ambiguous, the tool should cross-reference the search results with the user's most-bought items   │
│ to find the best match, prompting the user for confirmation when needed.                                                                                                         │
│                                                                                                                                                                                  │
│ Scope & Impact                                                                                                                                                                   │
│  - Authentication: The MCP server will accept authentication arguments (e.g., username/password or tokens) upon startup/installation so that all subsequent tools can act on     │
│    behalf of the user.                                                                                                                                                           │
│  - Core MCP Tools:                                                                                                                                                               │
│    - get_most_bought_products: Fetch the user's most bought products.                                                                                                            │
│    - search_products: Search the Colruyt catalog for products by name/keyword.                                                                                                   │
│    - add_items_to_list: Add specified products to the user's Colruyt shopping list.                                                                                              │
│  - AI Skills/Logic:                                                                                                                                                              │
│    - add_recipe_ingredients: Parse markdown files from recipes/, extract ingredients, and add them to the list. It will use a two-step matching process: searching the catalog   │
│      first, and if the match isn't clear, cross-referencing with the user's most-bought list to resolve ambiguity.                                                               │
│                                                                                                                                                                                  │
│ Proposed Solution                                                                                                                                                                │
│  1. Authentication: Implement a login flow in Python that uses the provided startup arguments to authenticate with Colruyt and obtain the x-cg-apikey and session cookies        │
│     (clpbff_session). This ensures the AI can use the tools seamlessly. If necessary, we will discover the specific login API endpoints using network inspection during          │
│     development.                                                                                                                                                                 │
│  2. Server Framework: Initialize a Python-based MCP server using the mcp SDK, configured to accept the necessary arguments.                                                      │
│  3. API Client Integration: Implement HTTP clients (using httpx) for the most-bought-products, search, and add-items-to-list endpoints.                                          │
│  4. Recipe Processing & Search Resolution: Implement a markdown parser for recipes/*.md. For each ingredient:                                                                    │
│      - Call the search_products API.                                                                                                                                             │
│      - If there are multiple ambiguous results, call get_most_bought_products and cross-reference to find a match.                                                               │
│      - If it's still unclear, the tool will return the options so the AI assistant can ask the user for confirmation before calling add_items_to_list.                           │
│                                                                                                                                                                                  │
│ Implementation Plan                                                                                                                                                              │
│  - Phase 1: Authentication & Startup:                                                                                                                                            │
│    - Discover the Colruyt login API endpoints.                                                                                                                                   │
│    - Setup the basic MCP server structure in Python (server.py) that accepts authentication parameters (username/password or tokens) as arguments.                               │
│    - Implement the authentication client that retrieves and stores the necessary headers/cookies.                                                                                │
│  - Phase 2: Core API Tools:                                                                                                                                                      │
│    - Discover the search API endpoint on colruyt.be.                                                                                                                             │
│    - Implement search_products tool.                                                                                                                                             │
│    - Implement get_most_bought_products tool.                                                                                                                                    │
│    - Implement add_items_to_list tool.                                                                                                                                           │
│  - Phase 3: Recipe Logic:                                                                                                                                                        │
│    - Create a directory recipes/ and define a standard markdown structure.                                                                                                       │
│    - Implement the add_recipe_to_list tool that parses the markdown, executes the search + cross-reference logic, and interacts with the AI for confirmation.                    │
│  - Phase 4: Testing & Verification:                                                                                                                                              │
│    - Verify the server starts and authenticates successfully with the provided arguments.                                                                                        │
│    - Test all tools end-to-end to ensure items are added to the list correctly.                                                                                                  │
│                                                                                                                                                                                  │
│ Verification                                                                                                                                                                     │
│  - Verify the server handles authentication arguments correctly at startup.                                                                                                      │
│  - Verify search_products returns accurate results.                                                                                                                              │
│  - Verify get_most_bought_products returns the user's history.                                                                                                                   │
│  - Verify add_items_to_list successfully updates the list on the actual Colruyt account.                                                                                         │
│  - Verify the add_recipe_to_list logic successfully resolves vague ingredients using the most-bought list. 