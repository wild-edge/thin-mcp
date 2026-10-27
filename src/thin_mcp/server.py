from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from thin_mcp.enums import McpMethodName
from thin_mcp.error_codes import JsonRpcErrorCode
from thin_mcp.protocol import (
    McpRequestHeaders,
    has_protocol_metadata,
    is_modern_version,
    uses_modern_protocol,
    validate_modern_request,
)
from thin_mcp.responses import McpHttpResult
from thin_mcp.schemas import (
    CacheableResult,
    DiscoverResult,
    EmptyResult,
    ImplementationInfo,
    InitializeParams,
    InitializeResult,
    JsonRpcResultResponse,
    McpRequest,
    McpResult,
    ResultMetadata,
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

    @property
    def legacy_protocol_versions(self) -> tuple[str, ...]:
        return tuple(v for v in self.protocol_versions if not is_modern_version(v))

    @property
    def modern_protocol_versions(self) -> tuple[str, ...]:
        return tuple(v for v in self.protocol_versions if is_modern_version(v))

    def get_tool_definitions(self) -> list[ToolDefinition]:
        return [tool.definition() for tool in self.tools.all()]

    def validate_http_request(
        self,
        request: McpRequest,
        headers: McpRequestHeaders,
    ) -> McpHttpResult | None:
        if uses_modern_protocol(request, headers):
            if self.modern_protocol_versions:
                return validate_modern_request(
                    request, headers, self.modern_protocol_versions
                )
            return McpHttpResult.error(
                request.id,
                JsonRpcErrorCode.SERVER_ERROR,
                "Unsupported MCP-Protocol-Version.",
                status=400,
            )
        if request.method == McpMethodName.INITIALIZE and self.legacy_protocol_versions:
            return None
        if (
            headers.protocol_version or "2025-03-26"
        ) not in self.legacy_protocol_versions:
            return McpHttpResult.error(
                request.id,
                JsonRpcErrorCode.SERVER_ERROR,
                "Unsupported MCP-Protocol-Version.",
                status=400,
            )
        return None

    def format_result(
        self, request: McpRequest, result: McpHttpResult
    ) -> McpHttpResult:
        """Add modern metadata to successful results for modern requests."""
        if has_protocol_metadata(request) and isinstance(
            result.body, JsonRpcResultResponse
        ):
            if not isinstance(result.body.result, McpResult):
                raise TypeError("MCP results must inherit McpResult.")
            body = result.body.result.model_copy(
                update={
                    "result_type": "complete",
                    "meta": ResultMetadata(
                        **{
                            "io.modelcontextprotocol/serverInfo": ImplementationInfo(
                                name=self.name, version=self.version
                            )
                        }
                    ),
                }
            )
            if isinstance(body, CacheableResult):
                body = body.model_copy(update={"ttl_ms": 0, "cache_scope": "private"})
            return McpHttpResult(
                status=result.status,
                body=result.body.model_copy(update={"result": body}),
            )
        return result

    def discover(self, request: McpRequest) -> McpHttpResult:
        return McpHttpResult.success(
            request.id,
            DiscoverResult(supportedVersions=list(self.modern_protocol_versions)),
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
        if not self.legacy_protocol_versions:
            return self.method_not_found(request)
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
            if params.protocol_version in self.legacy_protocol_versions
            else self.legacy_protocol_versions[-1]
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
        status = 404 if has_protocol_metadata(request) else 200
        return McpHttpResult.error(
            request.id,
            JsonRpcErrorCode.METHOD_NOT_FOUND,
            "Method not found.",
            status=status,
        )

    def dispatch_request(
        self,
        user: Any,
        request: McpRequest,
        *,
        resources: tuple[object, ...] = (),
    ) -> McpHttpResult:
        return self.format_result(
            request, self.dispatch_method(user, request, resources=resources)
        )

    def dispatch_method(
        self,
        user: Any,
        request: McpRequest,
        *,
        resources: tuple[object, ...] = (),
    ) -> McpHttpResult:
        if request.is_notification:
            return McpHttpResult.accepted()

        handlers: dict[str, Callable[[], McpHttpResult]] = {
            McpMethodName.PING: lambda: self.ping(request),
            McpMethodName.TOOLS_LIST: lambda: self.list_tools(request),
            McpMethodName.TOOLS_CALL: lambda: self.call_tool(
                user, request, resources=resources
            ),
        }
        if has_protocol_metadata(request):
            handlers[McpMethodName.SERVER_DISCOVER] = lambda: self.discover(request)
        else:
            handlers[McpMethodName.INITIALIZE] = lambda: self.initialize(request)

        handler = handlers.get(request.method)
        return handler() if handler is not None else self.method_not_found(request)
