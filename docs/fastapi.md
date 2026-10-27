# FastAPI example

[examples/fastapi_app.py](../examples/fastapi_app.py) is a complete, runnable
host application with a typed `echo` tool and a `POST /mcp` endpoint. It uses
the core `thin-mcp` package. FastAPI remains a host dependency; there is no
FastAPI extra or framework adapter inside `thin_mcp`.

## Run it

From the repository root with Python 3.12 or newer:

```bash
uv run --with fastapi --with uvicorn uvicorn examples.fastapi_app:app --reload
```

For a separate host project, install the published package and your HTTP stack:

```bash
pip install thin-mcp fastapi uvicorn
```

Copy the example into your application and use its module path when starting
Uvicorn. The example exposes an unauthenticated echo tool for local use.

## Try the endpoint

Initialize a legacy client:

```bash
curl http://127.0.0.1:8000/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"example-client","version":"1.0.0"}}}'
```

List tools and call `echo`, passing the negotiated version on subsequent requests:

```bash
curl http://127.0.0.1:8000/mcp \
  -H 'Content-Type: application/json' \
  -H 'MCP-Protocol-Version: 2025-11-25' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'

curl http://127.0.0.1:8000/mcp \
  -H 'Content-Type: application/json' \
  -H 'MCP-Protocol-Version: 2025-11-25' \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"echo","arguments":{"text":"hello"}}}'
```

The tool response includes `result.structuredContent` with `{"text":"hello"}`
and the JSON-RPC request ID. Notifications omit `id` and receive an empty
HTTP 202 response.

The example also supports the modern `2026-07-28` flow. Send matching HTTP
headers and request metadata; `tools/call` additionally requires `Mcp-Name`:

```bash
curl http://127.0.0.1:8000/mcp \
  -H 'Content-Type: application/json' \
  -H 'MCP-Protocol-Version: 2026-07-28' \
  -H 'Mcp-Method: tools/call' \
  -H 'Mcp-Name: echo' \
  -d '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"echo","arguments":{"text":"hello"},"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientCapabilities":{}}}}'
```

## How the HTTP boundary works

FastAPI validates the body into `McpRequest`. The route builds
`McpRequestHeaders`, returns any result from `server.validate_http_request`,
and then calls `server.dispatch_request`. Validation runs before dispatch,
including for notifications.

The route uses synchronous `def` because tool execution is synchronous. FastAPI
runs it in its thread pool, so a blocking host service does not run on the
event loop. See [FastAPI concurrency](https://fastapi.tiangolo.com/async/).

The two `async def` exception handlers only format error responses. Tool
handlers and dispatch remain synchronous; this example does not add support
for coroutine tool handlers.

`render_mcp_result` returns a
[FastAPI Response directly](https://fastapi.tiangolo.com/advanced/response-directly/)
to preserve the dispatcher status, Pydantic JSON aliases such as
`structuredContent`, and bodyless notification responses. Responses disable
caching with `Cache-Control: no-store`.

The dedicated example app maps malformed JSON to JSON-RPC parse errors and
invalid request envelopes to invalid-request errors, using HTTP 400 instead
of FastAPI's default 422 response. Unexpected exceptions are logged and return
a generic HTTP 500 JSON-RPC error. These app-wide handlers should be scoped to
a dedicated MCP sub-application if your host also serves ordinary REST routes.

For a real host, resolve authentication through your own FastAPI dependency
and pass that identity as `user` to `dispatch_request`. Supply request-scoped
services through its `resources` tuple, and declare object authorization using
tool permissions. Authentication, origin validation, throttling, and auditing
belong in the host. The example implements the library's JSON-response subset;
it does not add streaming, sessions, or server-initiated notifications.

As your tool set grows, split the registry, server configuration, HTTP route,
and domain tools into a host-owned `mcp_server/` package. Explicitly import tool
modules in stable order, following the [integration guide](../GUIDE.md).

## Verify it

From the repository root:

```bash
uv sync --extra django --group dev
uv run --with fastapi --with httpx pytest examples/test_fastapi_app.py --no-cov
```

The tests use [FastAPI's TestClient](https://fastapi.tiangolo.com/tutorial/testing/)
to cover initialization, listing and calling tools, notifications, malformed
requests, modern protocol headers, and safe handling of unexpected exceptions.
