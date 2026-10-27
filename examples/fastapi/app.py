"""Run from the repository root; see docs/fastapi.md."""

import logging
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import Response

from examples.fastapi.dependencies import get_tool_access
from examples.fastapi.mcp_server.tools import registry
from examples.fastapi.permissions import ToolAccess
from thin_mcp import (
    JsonRpcErrorCode,
    McpHttpResult,
    McpRequest,
    McpRequestHeaders,
    McpServer,
)

logger = logging.getLogger(__name__)
app = FastAPI(title="thin-mcp FastAPI example")
server = McpServer(
    name="fastapi-example",
    version="1.0.0",
    protocol_versions=("2025-11-25", "2026-07-28"),
    tools=registry,
)

def render_mcp_result(result: McpHttpResult) -> Response:
    return Response(
        content=(
            result.body.model_dump_json(by_alias=True)
            if result.body is not None
            else None
        ),
        status_code=result.status,
        media_type="application/json" if result.body is not None else None,
        headers={"Cache-Control": "no-store"},
    )


# These handlers apply to this entire dedicated MCP app. In a host with REST
# routes, mount it as a separate MCP sub-application to preserve REST errors.
@app.exception_handler(RequestValidationError)
def invalid_request(request: Request, exc: RequestValidationError) -> Response:
    parse_error = any(error["type"] == "json_invalid" for error in exc.errors())
    return render_mcp_result(
        McpHttpResult.error(
            None,
            JsonRpcErrorCode.PARSE_ERROR
            if parse_error
            else JsonRpcErrorCode.INVALID_REQUEST,
            "Parse error." if parse_error else "Invalid Request.",
            status=400,
        )
    )


@app.exception_handler(Exception)
def internal_error(request: Request, exc: Exception) -> Response:
    logger.error("Unhandled MCP request error", exc_info=exc)
    return render_mcp_result(
        McpHttpResult.error(
            None,
            JsonRpcErrorCode.INTERNAL_ERROR,
            "Internal error.",
            status=500,
        )
    )


@app.post("/mcp")
def mcp_endpoint(
    request: Request,
    payload: McpRequest,
    access: Annotated[ToolAccess, Depends(get_tool_access)],
) -> Response:
    headers = McpRequestHeaders.from_mapping(request.headers)
    invalid = server.validate_http_request(payload, headers)
    if invalid is not None:
        return render_mcp_result(invalid)

    # Replace None with the identity resolved by your host's authentication.
    # Handle dispatch failures here, where the validated JSON-RPC ID is known.
    try:
        result = server.dispatch_request(user=None, request=payload, resources=(access,))
    except Exception:
        logger.exception("Unhandled MCP request error")
        result = (
            McpHttpResult.accepted()
            if payload.is_notification
            else McpHttpResult.error(
                payload.id,
                JsonRpcErrorCode.INTERNAL_ERROR,
                "Internal error.",
                status=500,
            )
        )
    return render_mcp_result(result)
