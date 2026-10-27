# Django Ninja example

[examples/django_ninja/](../examples/django_ninja/) is a runnable Django Ninja
host with the same module structure and typed `echo` tool as the
[FastAPI example](fastapi.md).

```text
examples/django_ninja/
├── echoes/
│   ├── __init__.py
│   └── core.py                 Application functions with ordinary Python types
├── mcp_server/
│   ├── __init__.py              One shared ToolRegistry
│   ├── schemas.py              MCP argument and result models
│   └── tools/
│       ├── __init__.py         Explicit, ordered imports of domain tool modules
│       └── echoes.py      Decorated wrappers calling echoes.core
├── app.py                      McpServer configuration and HTTP handling
├── permissions.py              Host-owned tool permission checks
├── settings.py                 Minimal local Django settings
├── urls.py                     Mounts POST /mcp
├── conftest.py                  Django setup for standalone example tests
└── test_django_app.py
```

[echoes/core.py](../examples/django_ninja/echoes/core.py) defines
`echo(text: str) -> str` independently of the HTTP framework and `thin_mcp`.
Other application entry points can call this function directly.

[mcp_server/tools/echoes.py](../examples/django_ninja/mcp_server/tools/echoes.py)
imports `thin_mcp` and uses `@registry.register` to wrap that function with typed
MCP arguments and results. The application package never imports the MCP
integration package.

[mcp_server/__init__.py](../examples/django_ninja/mcp_server/__init__.py) owns the shared
registry. [tools/__init__.py](../examples/django_ninja/mcp_server/tools/__init__.py) explicitly
imports domain tool modules in registration order.
[app.py](../examples/django_ninja/app.py) imports that populated registry,
constructs `McpServer`, and connects it to HTTP.
All handlers use synchronous `def`.

[permissions.py](../examples/django_ninja/permissions.py) defines
`EchoEnabledPermission`, attached to the tool with
`permissions=(EchoEnabledPermission(),)`. It checks the host's
`MCP_ECHO_ENABLED` setting before the wrapper calls the domain function.
Setting it to `False` returns a tool result with `isError: true` and skips domain
execution. The tool remains listed, so clients can discover it even when calls
are disabled. This demonstrates a host capability check; user authentication
and per-user authorization still belong to your host integration.

To expose another application feature, add a function to `echoes/core.py`
and a typed wrapper to `mcp_server/tools/echoes.py`. For another domain,
add its application package and tool module, then explicitly import that tool
module in `mcp_server/tools/__init__.py`. Keep business logic in application
packages, and protocol adaptation in `mcp_server/`.

## Run it

From the repository root with Python 3.12 or newer:

```bash
uv sync --extra django --group dev
uv run python -m django runserver --settings=examples.django_ninja.settings
```

This uses Django's [development server](https://docs.djangoproject.com/en/5.2/ref/django-admin/#runserver).
The example exposes an unauthenticated echo tool for local use. It needs no
database or migrations. `echoes` is a normal Django application package
listed in `INSTALLED_APPS`.

For a separate host project, install `thin-mcp[django]`, copy the example
packages and HTTP module into your application, update their `examples.django_ninja` imports,
and mount `api.urls` in your own URL configuration. Use your application's
settings and authentication policy in place of the local example settings.

## Try the endpoint

```bash
curl http://127.0.0.1:8000/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"example-client","version":"1.0.0"}}}'

curl http://127.0.0.1:8000/mcp \
  -H 'Content-Type: application/json' \
  -H 'MCP-Protocol-Version: 2025-11-25' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'

curl http://127.0.0.1:8000/mcp \
  -H 'Content-Type: application/json' \
  -H 'MCP-Protocol-Version: 2025-11-25' \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"echo","arguments":{"text":"hello"}}}'
```

The tool response contains `result.structuredContent` with `{"text":"hello"}`.
The same modern protocol requests shown in the [FastAPI guide](fastapi.md)
also work here, including matching protocol, method, and tool-name headers.

## How the HTTP boundary works

Django Ninja validates the body into `McpRequest`. The route builds
`McpRequestHeaders`, returns any protocol validation error, and dispatches the
validated request. `render_mcp_result` preserves the HTTP status, JSON aliases,
and empty HTTP 202 notification responses. `McpAPI` maps malformed requests
and unexpected exceptions into MCP error envelopes and logs internal failures.

Authentication, authorization policy, origin validation, throttling, and
auditing remain host responsibilities. Pass the authenticated identity to
`dispatch_request` and provide request-scoped services through `resources`.
See [GUIDE.md](../GUIDE.md) for a larger Django integration with domain tool
modules and permissions. This example implements the library's JSON-response
subset without streaming or sessions.

## Verify it

```bash
uv run python -m django check --settings=examples.django_ninja.settings
uv run pytest examples/django_ninja --no-cov
```

The endpoint tests cover initialization, tool listing and execution, empty
notifications, malformed requests, modern protocol headers, and logged,
redacted internal errors. They also verify that a denied permission prevents
the domain function from running. CI runs both framework examples.
