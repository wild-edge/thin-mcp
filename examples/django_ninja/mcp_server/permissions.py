"""Host-owned tool permissions; replace with your application access policy."""

from django.conf import settings
from pydantic import BaseModel

from thin_mcp import ToolContext, ToolPermissionDenied


class EchoEnabledPermission:
    """Allow echo calls only when the host enables this capability."""

    def check(self, context: ToolContext, arguments: BaseModel) -> None:
        if not settings.MCP_ECHO_ENABLED:
            raise ToolPermissionDenied("The echo tool is disabled by the host.")
