"""Run from the repository root; see docs/fastapi.md."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict

from thin_mcp import (
    JsonRpcErrorCode,
    McpHttpResult,
    McpRequest,
    McpRequestHeaders,
    McpServer,
    ToolAnnotations,
    ToolContext,
    ToolRegistry,
)

logger = logging.getLogger(__name__)
app = FastAPI(title="thin-mcp FastAPI example")
registry = ToolRegistry()


class EchoArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    text: str


class EchoResult(BaseModel):
    text: str


@registry.register(
    name="echo",
    description="Echo typed text.",
    arguments_model=EchoArguments,
    result_model=EchoResult,
    annotations=ToolAnnotations(
        read_only_hint=True,
        destructive_hint=False,
        idempotent_hint=True,
        open_world_hint=False,
    ),
)
def echo(context: ToolContext, arguments: EchoArguments) -> EchoResult:
    return EchoResult(text=arguments.text)


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
def mcp_endpoint(request: Request, payload: McpRequest) -> Response:
    headers = McpRequestHeaders.from_mapping(request.headers)
    invalid = server.validate_http_request(payload, headers)
    if invalid is not None:
        return render_mcp_result(invalid)

    # Replace None with the identity resolved by your host's authentication.
    result = server.dispatch_request(user=None, request=payload)
    return render_mcp_result(result)
