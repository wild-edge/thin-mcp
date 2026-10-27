"""FastAPI dependencies that resolve host policy for the current request."""

from examples.fastapi.permissions import ToolAccess


def get_tool_access() -> ToolAccess:
    # Local demo policy. A real host resolves this from its configuration and
    # authenticated caller; never trust a client-supplied permission flag.
    return ToolAccess(echo_enabled=True)
