# Integration examples

These runnable examples show how a host application connects its domain
functions to thin-mcp. They use the same typed `echo` tool and package layout,
with HTTP handling and access policy expressed through each framework.

| Framework | HTTP entry point | Guide |
| --- | --- | --- |
| Django Ninja | [django_ninja/api.py](django_ninja/api.py) | [Setup, requests, and tests](../docs/django-ninja.md) |
| FastAPI | [fastapi/app.py](fastapi/app.py) | [Setup, requests, and tests](../docs/fastapi.md) |

## Run an example

Run these commands from the repository root with Python 3.12 or newer.

For Django Ninja:

```bash
uv sync --extra django --group dev
uv run python -m django runserver --settings=examples.django_ninja.settings
```

For FastAPI:

```bash
uv run --with fastapi --with uvicorn uvicorn examples.fastapi.app:app --reload
```

Run one server at a time with these defaults. Both expose `POST /mcp` at
`http://127.0.0.1:8000/mcp`. The guides include requests to initialize, list
tools, and call `echo`.

## Read the code

Start with `echoes/core.py` for the plain application function, then
`mcp_server/tools/echoes.py` for its typed MCP wrapper, and finally the HTTP
entry point. `mcp_server/tools/__init__.py` explicitly imports tool modules in
registration order; there is no automatic discovery.

These are structured host integration examples. The separate modules show
where domain logic, MCP schemas, registration, and host permissions belong
as an application grows. Django reads its capability policy from settings;
FastAPI injects a request-scoped policy with `Depends`.

Both examples provide an unauthenticated echo tool for local use and implement
the library's JSON-response subset without streaming or sessions. When adapting
them, supply your host's authentication and access policy. The
[integration guide](../GUIDE.md) shows a larger host application.
