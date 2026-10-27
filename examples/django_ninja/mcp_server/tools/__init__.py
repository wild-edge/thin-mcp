"""Import domain tool modules explicitly in stable registration order."""


from examples.django_ninja.mcp_server import registry

# Import order determines tools/list order. Add new domain modules here.
from examples.django_ninja.mcp_server.tools import echoes

registered_tool_domains = (echoes,)

__all__ = ("registry",)
