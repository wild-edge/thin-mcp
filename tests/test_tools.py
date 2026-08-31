from collections.abc import Callable
from dataclasses import dataclass

import pytest
from pydantic import BaseModel, ConfigDict

from thin_mcp import (
    McpServer,
    ToolContext,
    ToolExecutionError,
    ToolPermission,
    ToolPermissionDenied,
    ToolRegistry,
)


class EchoArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str


class EchoResult(BaseModel):
    text: str


@dataclass(frozen=True)
class EchoResource:
    text: str


def echo(context: ToolContext, arguments: EchoArguments) -> EchoResult:
    return EchoResult(text=arguments.text)


def echo_resource(context: ToolContext, arguments: EchoArguments) -> EchoResult:
    resource = context.require_resource(EchoResource)
    return EchoResult(text=resource.text)


def fail(context: ToolContext, arguments: EchoArguments) -> EchoResult:
    raise ToolExecutionError("Expected failure.")


class DeniedPermission:
    def check(self, context: ToolContext, arguments: BaseModel) -> None:
        raise ToolPermissionDenied("Access denied.")


def register_echo_tool(
    registry: ToolRegistry,
    *,
    handler: Callable[[ToolContext, EchoArguments], EchoResult] = echo,
    permissions: tuple[ToolPermission, ...] = (),
) -> None:
    registry.register(
        name="echo",
        description="Echo typed text.",
        arguments_model=EchoArguments,
        result_model=EchoResult,
        permissions=permissions,
    )(handler)


def test_registry_rejects_duplicate_tool_names() -> None:
    registry = ToolRegistry()
    register_echo_tool(registry)

    with pytest.raises(ValueError, match="Duplicate MCP tool name: echo"):
        register_echo_tool(registry)


def test_tool_argument_failure_is_actionable_tool_error() -> None:
    registry = ToolRegistry()
    register_echo_tool(registry)
    tool = registry.get("echo")
    assert tool is not None

    result = tool.execute(user=None, raw_arguments={"unexpected": True})

    assert result.is_error is True
    assert result.structured_content is None
    assert result.content[0].text == "Invalid tool arguments."


def test_tool_context_is_seeded_with_request_resources() -> None:
    registry = ToolRegistry()
    register_echo_tool(registry, handler=echo_resource)
    tool = registry.get("echo")
    assert tool is not None

    result = tool.execute(
        user=None,
        raw_arguments={"text": "ignored"},
        resources=(EchoResource(text="from request"),),
    )

    assert result.is_error is False
    assert result.structured_content == EchoResult(text="from request")


@pytest.mark.parametrize(
    ("handler", "permissions", "message"),
    [
        (fail, (), "Expected failure."),
        (echo, (DeniedPermission(),), "Access denied."),
    ],
)
def test_expected_tool_failures_use_tool_error_results(
    handler: Callable[[ToolContext, EchoArguments], EchoResult],
    permissions: tuple[ToolPermission, ...],
    message: str,
) -> None:
    registry = ToolRegistry()
    register_echo_tool(
        registry,
        handler=handler,
        permissions=permissions,
    )
    tool = registry.get("echo")
    assert tool is not None

    result = tool.execute(user=None, raw_arguments={"text": "hello"})

    assert result.is_error is True
    assert result.structured_content is None
    assert result.content[0].text == message


def test_server_requires_a_protocol_version() -> None:
    with pytest.raises(ValueError, match="At least one MCP protocol version"):
        McpServer(
            name="test",
            version="1.0",
            protocol_versions=(),
            tools=ToolRegistry(),
        )
