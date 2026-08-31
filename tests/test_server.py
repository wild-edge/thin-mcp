import pytest
from pydantic import BaseModel, ValidationError

from thin_mcp import McpRequest, McpServer, ToolContext, ToolRegistry
from thin_mcp.error_codes import JsonRpcErrorCode
from thin_mcp.schemas import (
    InitializeResult,
    JsonRpcErrorResponse,
    JsonRpcResultResponse,
    ToolResult,
    ToolsListResult,
)


class EchoArguments(BaseModel):
    text: str


class EchoResult(BaseModel):
    text: str


def make_server() -> McpServer:
    registry = ToolRegistry()

    @registry.register(
        name="echo",
        description="Echo typed text.",
        arguments_model=EchoArguments,
        result_model=EchoResult,
    )
    def echo(context: ToolContext, arguments: EchoArguments) -> EchoResult:
        return EchoResult(text=arguments.text)

    return McpServer(
        name="test-server",
        version="1.2.3",
        protocol_versions=("2025-03-26", "2025-11-25"),
        tools=registry,
    )


def make_request(
    method: str,
    *,
    request_id: str | int | None = 1,
    params: dict[str, object] | None = None,
) -> McpRequest:
    data: dict[str, object] = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params or {},
    }
    if request_id is not None:
        data["id"] = request_id
    return McpRequest.model_validate(data)


def test_initialize_negotiates_a_supported_protocol_version() -> None:
    server = make_server()
    request = make_request(
        "initialize",
        params={
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0"},
        },
    )

    response = server.dispatch_request(user=None, request=request)

    assert isinstance(response.body, JsonRpcResultResponse)
    assert isinstance(response.body.result, InitializeResult)
    assert response.body.result.protocol_version == "2025-03-26"
    assert response.body.result.server_info.name == "test-server"


def test_initialize_falls_back_to_latest_protocol_version() -> None:
    server = make_server()
    request = make_request(
        "initialize",
        params={
            "protocolVersion": "unsupported",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0"},
        },
    )

    response = server.initialize(request)

    assert isinstance(response.body, JsonRpcResultResponse)
    assert isinstance(response.body.result, InitializeResult)
    assert response.body.result.protocol_version == "2025-11-25"


def test_list_and_call_use_the_same_registered_tool() -> None:
    server = make_server()

    listed = server.list_tools(make_request("tools/list"))
    called = server.call_tool(
        user=None,
        request=make_request(
            "tools/call",
            params={"name": "echo", "arguments": {"text": "hello"}},
        ),
    )

    assert isinstance(listed.body, JsonRpcResultResponse)
    assert isinstance(listed.body.result, ToolsListResult)
    assert listed.body.result.tools[0].name == "echo"
    assert listed.body.result.tools[0].input_schema["required"] == ["text"]
    assert isinstance(called.body, JsonRpcResultResponse)
    assert isinstance(called.body.result, ToolResult)
    assert called.body.result.structured_content == EchoResult(text="hello")


def test_invalid_tool_call_params_return_invalid_params() -> None:
    response = make_server().call_tool(
        user=None,
        request=make_request("tools/call", params={"name": "echo"}),
    )

    assert isinstance(response.body, JsonRpcResultResponse)
    assert isinstance(response.body.result, ToolResult)
    assert response.body.result.is_error is True


def test_unknown_method_returns_json_rpc_error() -> None:
    response = make_server().dispatch_request(
        user=None,
        request=make_request("prompts/list"),
    )

    assert isinstance(response.body, JsonRpcErrorResponse)
    assert response.body.error.code == JsonRpcErrorCode.METHOD_NOT_FOUND


def test_notification_is_accepted_without_a_response_body() -> None:
    request = McpRequest.model_validate(
        {"jsonrpc": "2.0", "method": "notifications/initialized"}
    )

    response = make_server().dispatch_request(user=None, request=request)

    assert request.is_notification is True
    assert response.status == 202
    assert response.body is None


@pytest.mark.parametrize("request_id", [None, True])
def test_explicit_invalid_request_id_is_rejected(request_id: object) -> None:
    with pytest.raises(ValidationError):
        McpRequest.model_validate(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "ping",
            }
        )
