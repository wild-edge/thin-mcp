from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    SerializeAsAny,
    StringConstraints,
    model_validator,
)

McpRequestId = str | int
McpMethod = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9_.\-/]+$",
    ),
]
McpToolName = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9_.\-]+$",
    ),
]


class McpRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    jsonrpc: Literal["2.0"]
    id: McpRequestId | None = None
    method: McpMethod
    params: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_request_id(self) -> "McpRequest":
        if "id" in self.model_fields_set and (
            self.id is None or isinstance(self.id, bool)
        ):
            raise ValueError("Request id must be a string or integer.")
        return self

    @property
    def is_notification(self) -> bool:
        return "id" not in self.model_fields_set


class EmptyToolArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ToolCallParams(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: McpToolName
    arguments: dict[str, Any] = Field(default_factory=dict)
    meta: dict[str, Any] = Field(default_factory=dict, alias="_meta")


class ImplementationInfo(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str = Field(min_length=1, max_length=255)
    version: str = Field(min_length=1, max_length=100)


class InitializeParams(BaseModel):
    model_config = ConfigDict(extra="allow")

    protocol_version: str = Field(alias="protocolVersion")
    capabilities: dict[str, Any]
    client_info: ImplementationInfo = Field(alias="clientInfo")


class RequestMetadata(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)

    protocol_version: str = Field(alias="io.modelcontextprotocol/protocolVersion")
    client_capabilities: dict[str, Any] = Field(
        alias="io.modelcontextprotocol/clientCapabilities"
    )
    client_info: ImplementationInfo | None = Field(
        default=None, alias="io.modelcontextprotocol/clientInfo"
    )


class ResultMetadata(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    server_info: ImplementationInfo = Field(alias="io.modelcontextprotocol/serverInfo")


class McpResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    result_type: Literal["complete"] | None = Field(
        default=None, alias="resultType", exclude_if=lambda value: value is None
    )
    meta: ResultMetadata | None = Field(
        default=None, alias="_meta", exclude_if=lambda value: value is None
    )


class CacheableResult(McpResult):
    ttl_ms: int | None = Field(
        default=None, alias="ttlMs", ge=0, exclude_if=lambda value: value is None
    )
    cache_scope: Literal["private", "public"] | None = Field(
        default=None, alias="cacheScope", exclude_if=lambda value: value is None
    )


class ToolAnnotations(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    read_only_hint: bool = Field(default=False, alias="readOnlyHint")
    destructive_hint: bool = Field(default=True, alias="destructiveHint")
    idempotent_hint: bool = Field(default=False, alias="idempotentHint")
    open_world_hint: bool = Field(default=True, alias="openWorldHint")


class ToolDefinition(BaseModel):
    model_config = ConfigDict(populate_by_name=True, allow_inf_nan=False)

    name: McpToolName
    description: str
    input_schema: dict[str, Any] = Field(alias="inputSchema")
    output_schema: dict[str, Any] = Field(alias="outputSchema")
    annotations: ToolAnnotations = Field(default_factory=ToolAnnotations)
    meta: dict[str, JsonValue] | None = Field(
        default=None, alias="_meta", exclude_if=lambda value: value is None
    )


class ToolsListResult(CacheableResult):
    tools: list[ToolDefinition]


class TextContent(BaseModel):
    type: Literal["text"] = "text"
    text: str


class ContentAnnotations(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    audience: list[Literal["user", "assistant"]] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    priority: float | None = Field(
        default=None, ge=0, le=1, exclude_if=lambda value: value is None
    )
    last_modified: str | None = Field(
        default=None, alias="lastModified", exclude_if=lambda value: value is None
    )


class ImageContent(BaseModel):
    model_config = ConfigDict(populate_by_name=True, allow_inf_nan=False)

    type: Literal["image"] = "image"
    data: str
    mime_type: str = Field(alias="mimeType")
    annotations: ContentAnnotations | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    meta: dict[str, JsonValue] | None = Field(
        default=None, alias="_meta", exclude_if=lambda value: value is None
    )


ContentBlock = Annotated[TextContent | ImageContent, Field(discriminator="type")]


class ToolResult(McpResult):
    model_config = ConfigDict(populate_by_name=True)

    content: list[ContentBlock]
    structured_content: SerializeAsAny[BaseModel] | None = Field(
        default=None,
        alias="structuredContent",
        exclude_if=lambda value: value is None,
    )
    is_error: bool = Field(default=False, alias="isError")


class EmptyResult(McpResult):
    model_config = ConfigDict(extra="forbid")


class ToolCapabilities(BaseModel):
    list_changed: bool = Field(default=False, alias="listChanged")


class ServerCapabilities(BaseModel):
    tools: ToolCapabilities = Field(default_factory=ToolCapabilities)


class InitializeResult(McpResult):
    model_config = ConfigDict(populate_by_name=True)

    protocol_version: str = Field(alias="protocolVersion")
    capabilities: ServerCapabilities = Field(default_factory=ServerCapabilities)
    server_info: ImplementationInfo = Field(alias="serverInfo")


class DiscoverResult(CacheableResult):
    supported_versions: list[str] = Field(alias="supportedVersions")
    capabilities: ServerCapabilities = Field(default_factory=ServerCapabilities)


class UnsupportedProtocolVersionData(BaseModel):
    supported: list[str]
    requested: str


class JsonRpcError(BaseModel):
    code: int
    message: str
    data: SerializeAsAny[BaseModel] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )


class JsonRpcErrorResponse(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: McpRequestId | None
    error: JsonRpcError


class JsonRpcResultResponse(BaseModel):
    jsonrpc: Literal["2.0"] = "2.0"
    id: McpRequestId | None
    result: SerializeAsAny[BaseModel]
