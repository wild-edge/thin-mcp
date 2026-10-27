"""Populate the registry through explicit imports in stable order.

Import each domain module (or its decorated tool functions) here so its
registration decorators run. No filesystem scanning or automatic discovery is
performed. ``registered_tool_domains`` retains the imported module references;
it does not discover or register tools itself.
"""


from examples.django_ninja.mcp_server import registry

# Import order determines tools/list order. Add new domain modules here.
from examples.django_ninja.mcp_server.tools import echoes

registered_tool_domains = (echoes,)

__all__ = ("registry",)
