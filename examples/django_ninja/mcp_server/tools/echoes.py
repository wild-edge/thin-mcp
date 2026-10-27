"""MCP tool adapters for echoes application functions."""

# This module corresponds to the echoes/ domain package and its core module.
# Register that domain's MCP tools here; this is the recommended place to wrap
# domain functions with @registry.register while keeping business logic in echoes/.

from examples.django_ninja.echoes.core import echo
from examples.django_ninja.mcp_server import registry
from examples.django_ninja.mcp_server.schemas import EchoArguments, EchoResult
from examples.django_ninja.permissions import EchoEnabledPermission
from thin_mcp import ToolAnnotations, ToolContext


@registry.register(
    name="echo",
    description="Echo typed text.",
    arguments_model=EchoArguments,
    result_model=EchoResult,
    permissions=(EchoEnabledPermission(),),
    annotations=ToolAnnotations(
        read_only_hint=True,
        destructive_hint=False,
        idempotent_hint=True,
        open_world_hint=False,
    ),
)
def echo_tool(context: ToolContext, arguments: EchoArguments) -> EchoResult:
    return EchoResult(text=echo(arguments.text))
