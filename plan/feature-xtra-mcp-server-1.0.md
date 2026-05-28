---
goal: Implement a Python MCP server for Colruyt Xtra with recipe integration.
version: 1.0
date_created: 2025-05-10
owner: ddvlamin
status: 'Planned'
tags: [feature, mcp, colruyt, python]
---

# Introduction

![Status: Planned](https://img.shields.io/badge/status-Planned-blue)

This plan outlines the implementation of a Python-based Model Context Protocol (MCP) server for Colruyt Xtra. The server will provide tools to interact with the Colruyt API (search, most bought, shopping list) and a specialized skill to parse recipes and add ingredients to the shopping list with intelligent disambiguation.

## 1. Requirements & Constraints

- **REQ-001**: Support authentication via `clpbff_session` (cookie) and `x-cg-apikey` (header).
- **REQ-002**: Implement `get_most_bought_products` tool.
- **REQ-003**: Implement `search_products(query)` tool.
- **REQ-004**: Implement `add_items_to_list(products)` tool.
- **REQ-005**: Implement `add_recipe_to_list(recipe_path)` skill.
- **REQ-006**: Skill must parse ingredients from Markdown files in `recipes/`.
- **REQ-007**: Skill must resolve ambiguous search results using the "most bought" list.
- **CON-001**: Use Python 3.12+ and the `mcp` SDK.
- **CON-002**: Use `httpx` for asynchronous HTTP requests.
- **CON-003**: Default `placeId` is `2643`.
- **CON-004**: Static API Key: `a8ylmv13-b285-4788-9e14-0f79b7ed2411`.

## 2. Implementation Steps

### Implementation Phase 1: Environment & Data Models

- GOAL-001: Set up the project structure and define data transfer objects (DTOs).

| Task     | Description                                                                 | Completed | Date |
| -------- | --------------------------------------------------------------------------- | --------- | ---- |
| TASK-001 | Update `pyproject.toml` with `httpx`, `pydantic`, and `python-dotenv`.      |           |      |
| TASK-002 | Create `src/models.py` for API request/response schemas.                    |           |      |
| TASK-003 | Create `.env.example` with placeholders for session and API key.            |           |      |

### Implementation Phase 2: Core API Client

- GOAL-002: Implement the low-level API client for Colruyt services.

| Task     | Description                                                                 | Completed | Date |
| -------- | --------------------------------------------------------------------------- | --------- | ---- |
| TASK-004 | Create `src/client.py` implementing `ColruytClient` class.                  |           |      |
| TASK-005 | Implement `get_most_bought_products` method.                                |           |      |
| TASK-006 | Implement `search_products` method.                                         |           |      |
| TASK-007 | Implement `add_items_to_list` method.                                       |           |      |

### Implementation Phase 3: Recipe Parsing & Logic

- GOAL-003: Implement the business logic for recipe parsing and product matching.

| Task     | Description                                                                 | Completed | Date |
| -------- | --------------------------------------------------------------------------- | --------- | ---- |
| TASK-008 | Create `src/logic.py` for ingredient extraction from Markdown.              |           |      |
| TASK-009 | Implement logic to clean ingredient strings (remove quantities/units).      |           |      |
| TASK-010 | Implement the disambiguation logic using "most bought" cross-referencing.   |           |      |

### Implementation Phase 4: MCP Server Integration

- GOAL-004: Connect the logic to the MCP framework and expose tools.

| Task     | Description                                                                 | Completed | Date |
| -------- | --------------------------------------------------------------------------- | --------- | ---- |
| TASK-011 | Create `src/server.py` and initialize `mcp.Server`.                         |           |      |
| TASK-012 | Register `get_most_bought_products`, `search_products`, `add_items_to_list`.|           |      |
| TASK-013 | Register `add_recipe_to_list` tool.                                         |           |      |
| TASK-014 | Implement error handling and authentication validation at startup.          |           |      |

### Implementation Phase 5: Testing & Verification

- GOAL-005: Ensure the server works as expected with real or mocked data.

| Task     | Description                                                                 | Completed | Date |
| -------- | --------------------------------------------------------------------------- | --------- | ---- |
| TASK-015 | Create unit tests for Markdown parsing and product matching.                |           |      |
| TASK-016 | Create integration tests (mocking API responses) for tool handlers.         |           |      |
| TASK-017 | Verify tool definitions and schemas using `mcp inspect`.                    |           |      |

## 3. Alternatives

- **ALT-001**: Use a specialized Markdown parsing library like `marko`. *Decision*: Stick to regex for simpler dependency management if the format is consistent.
- **ALT-002**: Prompt user for every ambiguous match. *Decision*: First attempt auto-resolution via "most bought" to reduce friction, then fallback to prompting.

## 4. Dependencies

- **DEP-001**: `mcp>=1.27.0` - Model Context Protocol SDK.
- **DEP-002**: `httpx` - Async HTTP client.
- **DEP-003**: `pydantic` - Data validation.
- **DEP-004**: `python-dotenv` - Environment variable management.

## 5. Files

- **FILE-001**: `src/server.py` - Entry point and MCP tool registration.
- **FILE-002**: `src/client.py` - API client for Colruyt Gateway.
- **FILE-003**: `src/models.py` - Pydantic models for API data.
- **FILE-004**: `src/logic.py` - Recipe parsing and matching logic.
- **FILE-005**: `pyproject.toml` - Dependency configuration.

## 6. Testing

- **TEST-001**: Verify `add_recipe_to_list` correctly extracts "kipfilets" from "3 kipfilets".
- **TEST-002**: Mock search results for "kip" and verify it chooses the one present in "most bought".
- **TEST-003**: Verify `add_items_to_list` sends the correct UUID and timestamp format.

## 7. Risks & Assumptions

- **RISK-001**: The `clpbff_session` cookie might expire quickly, requiring re-authentication.
- **ASSUMPTION-001**: The Markdown recipe format is consistent with the provided example (ingredients in a list under a header).
- **ASSUMPTION-002**: `technicalArticleNumber` is stable and used as the primary ID across search and list management.

## 8. Related Specifications / Further Reading

- [MCP Documentation](https://modelcontextprotocol.io/)
- [Colruyt Xtra API Dumps](./docs/api-call-dumps/)
