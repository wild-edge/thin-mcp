from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from thin_mcp.error_codes import JsonRpcErrorCode
from thin_mcp.responses import McpHttpResult
from thin_mcp.schemas import (
    EmptyResult,
    ImplementationInfo,
    InitializeParams,
    InitializeResult,
    McpRequest,
    ServerCapabilities,
    ToolCallParams,
    ToolDefinition,
    ToolsListResult,
)
from thin_mcp.tools import ToolRegistry


@dataclass(frozen=True)
class McpServer:
    """Configured MCP protocol dispatcher independent of application policy."""

    name: str
    version: str
    protocol_versions: tuple[str, ...]
    tools: ToolRegistry

    def __post_init__(self) -> None:
        if not self.protocol_versions:
            raise ValueError("At least one MCP protocol version is required.")

    @property
    def latest_protocol_version(self) -> str:
        return self.protocol_versions[-1]

    def get_tool_definitions(self) -> list[ToolDefinition]:
        return [tool.definition() for tool in self.tools.all()]

    def request_protocol_is_supported(
        self,
        request: McpRequest,
        protocol_version: str,
    ) -> bool:
        return (
            request.method == "initialize" or protocol_version in self.protocol_versions
        )

    def call_tool(
        self,
        user: Any,
        request: McpRequest,
        *,
        resources: tuple[object, ...] = (),
    ) -> McpHttpResult:
        try:
            tool_call = ToolCallParams.model_validate(request.params)
        except ValidationError:
            return McpHttpResult.error(
                request.id,
                JsonRpcErrorCode.INVALID_PARAMS,
                "Tool name and arguments are required.",
            )

        tool = self.tools.get(tool_call.name)
        if tool is None:
            return McpHttpResult.error(
                request.id,
                JsonRpcErrorCode.INVALID_PARAMS,
                f"Unknown tool: {tool_call.name}",
            )

        result = tool.execute(
            user,
            tool_call.arguments,
            resources=resources,
        )
        return McpHttpResult.success(request.id, result)

    def initialize(self, request: McpRequest) -> McpHttpResult:
        try:
            params = InitializeParams.model_validate(request.params)
        except ValidationError:
            return McpHttpResult.error(
                request.id,
                JsonRpcErrorCode.INVALID_PARAMS,
                "Invalid initialize parameters.",
            )

        protocol_version = (
            params.protocol_version
            if params.protocol_version in self.protocol_versions
            else self.latest_protocol_version
        )
        result = InitializeResult(
            protocolVersion=protocol_version,
            capabilities=ServerCapabilities(),
            serverInfo=ImplementationInfo(name=self.name, version=self.version),
        )
        return McpHttpResult.success(request.id, result)

    def ping(self, request: McpRequest) -> McpHttpResult:
        return McpHttpResult.success(request.id, EmptyResult())

    def list_tools(self, request: McpRequest) -> McpHttpResult:
        result = ToolsListResult(tools=self.get_tool_definitions())
        return McpHttpResult.success(request.id, result)

    def method_not_found(self, request: McpRequest) -> McpHttpResult:
        return McpHttpResult.error(
            request.id,
            JsonRpcErrorCode.METHOD_NOT_FOUND,
            "Method not found.",
        )

    def dispatch_request(
        self,
        user: Any,
        request: McpRequest,
        *,
        resources: tuple[object, ...] = (),
    ) -> McpHttpResult:
        if request.is_notification:
            return McpHttpResult.accepted()

        match request.method:
            case "initialize":
                return self.initialize(request)
            case "ping":
                return self.ping(request)
            case "tools/list":
                return self.list_tools(request)
            case "tools/call":
                return self.call_tool(user, request, resources=resources)
            case _:
                return self.method_not_found(request)
