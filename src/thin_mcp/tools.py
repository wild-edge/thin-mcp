from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel, ConfigDict, JsonValue, TypeAdapter, ValidationError

from thin_mcp.schemas import (
    ContentBlock,
    TextContent,
    ToolAnnotations,
    ToolDefinition,
    ToolResult,
)

ArgumentsT = TypeVar("ArgumentsT", bound=BaseModel)
ResultT = TypeVar("ResultT", bound=BaseModel)
ResourceT = TypeVar("ResourceT")
ToolHandler = Callable[["ToolContext", ArgumentsT], ResultT]
ContentBuilder = Callable[["ToolContext", ResultT], Sequence[ContentBlock]]

_metadata_adapter = TypeAdapter(dict[str, JsonValue], config=ConfigDict(allow_inf_nan=False))


class ToolExecutionError(Exception):
    """Raised for an expected tool failure that a client can act on."""


class ToolPermissionDenied(ToolExecutionError):
    """Raised when a tool permission rejects the authenticated caller."""


@dataclass
class ToolContext:
    user: Any
    resources: dict[type[Any], Any] = field(default_factory=dict)

    def set_resource(self, resource: object) -> None:
        self.resources[type(resource)] = resource

    def require_resource(self, resource_type: type[ResourceT]) -> ResourceT:
        try:
            resource = self.resources[resource_type]
        except KeyError:
            raise RuntimeError(
                f"{resource_type.__name__} permission was not evaluated."
            ) from None
        if not isinstance(resource, resource_type):
            raise TypeError(f"Invalid resource type for {resource_type.__name__}.")
        return resource


class ToolPermission(Protocol):
    def check(self, context: ToolContext, arguments: BaseModel) -> None:
        """Raise ToolPermissionDenied when access should be rejected."""


def tool_result[ResultT: BaseModel](
    data: ResultT,
) -> ToolResult:
    """Format a structured tool result with a concise text fallback."""
    return ToolResult(
        content=[TextContent(text=data.model_dump_json(by_alias=True))],
        structuredContent=data,
    )


def tool_error_result(message: str) -> ToolResult:
    """Format an actionable tool failure without violating its output schema."""
    return ToolResult(
        content=[TextContent(text=message)],
        isError=True,
    )


@dataclass(frozen=True)
class McpTool[ArgumentsT: BaseModel, ResultT: BaseModel]:
    """One typed, permission-checked MCP tool declaration."""

    name: str
    description: str
    arguments_model: type[ArgumentsT]
    result_model: type[ResultT]
    handler: ToolHandler[ArgumentsT, ResultT]
    invalid_arguments_message: str
    permissions: tuple[ToolPermission, ...] = ()
    annotations: ToolAnnotations = field(default_factory=ToolAnnotations)
    meta: dict[str, JsonValue] | None = None
    content_builder: ContentBuilder[ResultT] | None = None

    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name=self.name,
            description=self.description,
            inputSchema=self.arguments_model.model_json_schema(),
            outputSchema=self.result_model.model_json_schema(),
            annotations=self.annotations,
            _meta=self.meta,
        )

    def execute(
        self,
        user: Any,
        raw_arguments: dict[str, Any],
        *,
        resources: tuple[object, ...] = (),
    ) -> ToolResult:
        try:
            arguments = self.arguments_model.model_validate(raw_arguments)
        except ValidationError:
            return tool_error_result(self.invalid_arguments_message)

        context = ToolContext(user=user)
        for resource in resources:
            context.set_resource(resource)
        try:
            for permission in self.permissions:
                permission.check(context, arguments)
            raw_result = self.handler(context, arguments)
        except ToolExecutionError as exc:
            return tool_error_result(str(exc))

        result = self.result_model.model_validate(raw_result)
        try:
            extra_content = (
                self.content_builder(context, result)
                if self.content_builder is not None
                else ()
            )
            response = tool_result(result)
            return ToolResult(
                content=[*response.content, *extra_content],
                structuredContent=result,
            )
        except ToolExecutionError as exc:
            return tool_error_result(str(exc))


class ToolRegistry:
    """Own an explicit, deterministic set of MCP tool declarations."""

    def __init__(self) -> None:
        self.tools: dict[str, McpTool[Any, Any]] = {}

    def register(
        self,
        *,
        name: str,
        description: str,
        arguments_model: type[ArgumentsT],
        result_model: type[ResultT],
        permissions: tuple[ToolPermission, ...] = (),
        invalid_arguments_message: str = "Invalid tool arguments.",
        annotations: ToolAnnotations | None = None,
        meta: dict[str, JsonValue] | None = None,
        content_builder: ContentBuilder[ResultT] | None = None,
    ) -> Callable[[ToolHandler[ArgumentsT, ResultT]], ToolHandler[ArgumentsT, ResultT]]:
        def decorator(
            handler: ToolHandler[ArgumentsT, ResultT],
        ) -> ToolHandler[ArgumentsT, ResultT]:
            if name in self.tools:
                raise ValueError(f"Duplicate MCP tool name: {name}")
            self.tools[name] = McpTool(
                name=name,
                description=description,
                arguments_model=arguments_model,
                result_model=result_model,
                handler=handler,
                invalid_arguments_message=invalid_arguments_message,
                permissions=permissions,
                meta=_metadata_adapter.validate_python(meta) if meta is not None else None,
                content_builder=content_builder,
                annotations=(
                    annotations if annotations is not None else ToolAnnotations()
                ),
            )
            return handler

        return decorator

    def all(self) -> tuple[McpTool[Any, Any], ...]:
        return tuple(self.tools.values())

    def get(self, name: str) -> McpTool[Any, Any] | None:
        return self.tools.get(name)
