# AGENTS.md

## Project

`thin-mcp` is a reusable, typed Python framework for the tool-serving portion
of the Model Context Protocol. It sits between a validated MCP request and a
host application's typed tool handlers.

The package owns:

- strict Pydantic MCP and JSON-RPC models;
- protocol initialization, ping, tool listing, tool calls, and notifications;
- typed tool registration and deterministic discovery;
- ordered permission execution and request-scoped resources;
- structured tool results and framework-neutral response values; and
- an optional Django Ninja transport adapter.

The consuming application owns authentication, authorization policy, routes,
throttling, auditing, persistence, domain services, and concrete tools.

## Architecture boundary

Keep the dependency direction one-way:

```text
host mcp_server integration -> thin_mcp
host mcp_server integration -> host domain services
```

Never import a host application, its models, settings, or business services
from `src/thin_mcp/`. Do not move product-specific token scopes, roles, tenant
rules, audit behavior, or data access into this library.

The optional `django_ninja.py` module may depend on the `django` extra. All
other modules must remain usable when Django is not installed.

## Source layout

```text
src/thin_mcp/
  schemas.py          MCP and JSON-RPC models
  error_codes.py      JSON-RPC error codes
  responses.py        transport-independent results
  tools.py            registry, permissions, execution, resources
  server.py           protocol dispatch
  django_ninja.py     optional Django Ninja adapter
tests/                independent package tests
docs/                 repository-native diagrams
```

## Engineering rules

- Prefer the smallest change that preserves the library boundary.
- Keep the public API deliberate. Export supported public names from
  `src/thin_mcp/__init__.py`; treat additions as compatibility commitments.
- Use Pydantic models for structured boundaries and type every function and
  method.
- Keep tool listing and execution backed by the same `ToolRegistry` entry.
- Preserve registration order because hosts may depend on stable `tools/list`
  output.
- Expected, client-actionable failures use `ToolExecutionError` or
  `ToolPermissionDenied`. Unexpected errors must remain visible to the host for
  logging and transport-level handling.
- Do not add automatic filesystem or Django app discovery. Host applications
  should explicitly import domain tool modules as described in `GUIDE.md`.
- Keep dependencies minimal. New framework integrations belong in optional
  extras and isolated adapter modules.
- Update `README.md`, `GUIDE.md`, type declarations, and tests when changing a
  public contract.
- Keep SVG diagrams valid XML and readable without external fonts or assets.

## Verification

Run the narrowest affected tests first, then the complete package checks before
finishing:

```bash
uv sync --extra django --group dev
uv run pytest
uv run ruff check .
uv run mypy
uv build
```

For packaging changes, install the built wheel in a clean environment and
confirm that the core wheel does not install Django unless the `django` extra
is requested.

For documentation changes, verify local links, compile every Python example
that is intended to be complete, and validate SVG files with an XML parser.

## Release policy

The project follows Semantic Versioning. During `0.x`, incompatible public API
changes require a minor release and must be called out in `CHANGELOG.md`. After
`1.0.0`, incompatible changes require a major release.
