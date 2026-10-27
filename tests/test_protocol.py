from typing import Any

import pytest
from pydantic import BaseModel

from thin_mcp import McpRequest, McpRequestHeaders, McpServer, ToolContext, ToolRegistry
from thin_mcp.schemas import JsonRpcErrorResponse, JsonRpcResultResponse


class EchoArguments(BaseModel):
    text: str


class EchoResult(BaseModel):
    text: str


def make_server(versions: tuple[str, ...] = ("2025-11-25", "2026-07-28")) -> McpServer:
    registry = ToolRegistry()

    @registry.register(
        name="echo",
        description="Echo typed text.",
        arguments_model=EchoArguments,
        result_model=EchoResult,
    )
    def echo(context: ToolContext, arguments: EchoArguments) -> EchoResult:
        return EchoResult(text=arguments.text)

    return McpServer(name="test", version="1.0", protocol_versions=versions, tools=registry)


def modern_request(method: str = "server/discover", **params: Any) -> McpRequest:
    return McpRequest(
        jsonrpc="2.0",
        id=1,
        method=method,
        params={
            "_meta": {
                "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                "io.modelcontextprotocol/clientCapabilities": {},
            },
            **params,
        },
    )


def test_modern_discovery_and_tool_calls_include_result_metadata() -> None:
    server = make_server()
    for request in (
        modern_request(),
        modern_request("tools/list"),
        modern_request("tools/call", name="echo", arguments={"text": "hello"}),
    ):
        headers = McpRequestHeaders(
            protocol_version="2026-07-28",
            method=request.method,
            name=request.params.get("name"),
        )
        assert server.validate_http_request(request, headers) is None
        response = server.dispatch_request(None, request)
        assert isinstance(response.body, JsonRpcResultResponse)
        result = response.body.model_dump(by_alias=True)["result"]
        assert result["resultType"] == "complete"
        assert result["_meta"] == {
            "io.modelcontextprotocol/serverInfo": {"name": "test", "version": "1.0"}
        }
        if request.method in {"server/discover", "tools/list"}:
            assert result["ttlMs"] == 0
            assert result["cacheScope"] == "private"
        else:
            assert result["structuredContent"] == {"text": "hello"}


@pytest.mark.parametrize(
    "metadata",
    [
        None,
        [],
        {},
        {"io.modelcontextprotocol/protocolVersion": "2026-07-28"},
        {
            "io.modelcontextprotocol/protocolVersion": 2026,
            "io.modelcontextprotocol/clientCapabilities": {},
        },
        {
            "io.modelcontextprotocol/protocolVersion": "2026-07-28",
            "io.modelcontextprotocol/clientCapabilities": [],
        },
    ],
)
def test_modern_requests_require_valid_metadata(metadata: Any) -> None:
    request = modern_request()
    request.params["_meta"] = metadata
    response = make_server().validate_http_request(
        request, McpRequestHeaders(protocol_version="2026-07-28", method=request.method)
    )
    assert response is not None
    assert response.status == 400
    assert isinstance(response.body, JsonRpcErrorResponse)
    assert response.body.error.code == -32602


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("protocol_version", None),
        ("protocol_version", "2025-11-25"),
        ("method", None),
        ("method", "tools/list"),
        ("name", None),
        ("name", "different"),
        ("name", "echo\r\nforged"),
        ("name", " echo"),
        ("name", "=?base64?!!!?="),
        ("name", "=?base64?/w==?="),
    ],
)
def test_modern_tool_call_rejects_invalid_headers(field: str, value: str | None) -> None:
    request = modern_request("tools/call", name="echo", arguments={"text": "hello"})
    headers = McpRequestHeaders(
        protocol_version="2026-07-28", method=request.method, name="echo"
    ).model_copy(update={field: value})
    response = make_server().validate_http_request(request, headers)
    assert response is not None
    assert response.status == 400
    assert isinstance(response.body, JsonRpcErrorResponse)
    assert response.body.error.code == -32020


def test_header_mapping_is_case_insensitive_and_names_can_be_base64_encoded() -> None:
    request = modern_request("tools/call", name="echo", arguments={"text": "hello"})
    headers = McpRequestHeaders.from_mapping(
        {
            "mCp-PrOtOcOl-VeRsIoN": "2026-07-28",
            "mcp-method": "tools/call",
            "MCP-NAME": "=?base64?ZWNobw==?=",
        }
    )
    assert make_server().validate_http_request(request, headers) is None


def test_unsupported_modern_version_reports_supported_versions() -> None:
    request = modern_request()
    request.params["_meta"]["io.modelcontextprotocol/protocolVersion"] = "2099-01-01"
    response = make_server().validate_http_request(
        request, McpRequestHeaders(protocol_version="2099-01-01", method=request.method)
    )
    assert response is not None
    assert isinstance(response.body, JsonRpcErrorResponse)
    assert response.body.model_dump()["error"] == {
        "code": -32022,
        "message": "Unsupported protocol version.",
        "data": {"supported": ["2026-07-28"], "requested": "2099-01-01"},
    }


def test_legacy_initialization_remains_supported_with_a_modern_server() -> None:
    request = McpRequest(
        jsonrpc="2.0",
        id=1,
        method="initialize",
        params={
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "client", "version": "1"},
        },
    )
    server = make_server()
    assert server.validate_http_request(request, McpRequestHeaders(protocol_version="2026-07-28")) is None
    response = server.dispatch_request(None, request)
    assert isinstance(response.body, JsonRpcResultResponse)
    assert response.body.model_dump(by_alias=True)["result"]["protocolVersion"] == "2025-11-25"


def test_legacy_only_server_rejects_modern_discovery_and_keeps_legacy_envelope() -> None:
    request = modern_request()
    response = make_server(("2025-11-25",)).validate_http_request(
        request, McpRequestHeaders(protocol_version="2026-07-28", method=request.method)
    )
    assert response is not None
    assert response.status == 400

    unknown = McpRequest(jsonrpc="2.0", id=1, method="prompts/list")
    legacy_response = make_server().dispatch_request(None, unknown)
    assert legacy_response.status == 200
    assert isinstance(legacy_response.body, JsonRpcErrorResponse)


def test_unimplemented_modern_methods_return_http_404() -> None:
    response = make_server().dispatch_request(None, modern_request("resources/list"))
    assert response.status == 404
    assert isinstance(response.body, JsonRpcErrorResponse)
    assert response.body.error.code == -32601
