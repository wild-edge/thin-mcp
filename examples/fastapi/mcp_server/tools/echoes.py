"""MCP tool adapters for echoes application functions."""

# This module corresponds to the echoes/ domain package and its core module.
# Register that domain's MCP tools here; this is the recommended place to wrap
# domain functions with @registry.register while keeping business logic in echoes/.

from examples.fastapi.echoes import core
from examples.fastapi.mcp_server import registry
from examples.fastapi.mcp_server.schemas import EchoArguments, EchoResult
from thin_mcp import ToolAnnotations, ToolContext


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
    return EchoResult(text=core.echo(arguments.text))
