"""Django Ninja HTTP boundary; see docs/django-ninja.md."""

import logging

from django.http import HttpRequest, HttpResponse

from examples.django_ninja.mcp_server.tools import registry
from thin_mcp import (
    JsonRpcErrorCode,
    McpHttpResult,
    McpRequest,
    McpRequestHeaders,
    McpServer,
)
from thin_mcp.django_ninja import McpAPI, render_mcp_result

logger = logging.getLogger(__name__)
api = McpAPI(title="thin-mcp Django Ninja example", urls_namespace="example_mcp")
server = McpServer(
    name="django-ninja-example",
    version="1.0.0",
    protocol_versions=("2025-11-25", "2026-07-28"),
    tools=registry,
)


@api.post("")
def mcp_endpoint(request: HttpRequest, payload: McpRequest) -> HttpResponse:
    headers = McpRequestHeaders.from_mapping(request.headers)
    invalid = server.validate_http_request(payload, headers)
    if invalid is not None:
        return render_mcp_result(invalid)

    # Replace None with the identity resolved by your host's authentication.
    # Handle dispatch failures here, where the validated JSON-RPC ID is known.
    try:
        result = server.dispatch_request(user=None, request=payload)
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
