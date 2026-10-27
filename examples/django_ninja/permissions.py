"""Host-owned tool permissions; replace with your application access policy."""

# ToolContext.user is the identity the host passes to dispatch_request(user=...).
# This local example passes None; authenticate the caller before checking user access.

from django.conf import settings
from pydantic import BaseModel

from thin_mcp import ToolContext, ToolPermissionDenied


class EchoEnabledPermission:
    """Allow echo calls only when the host enables this capability."""

    def check(self, context: ToolContext, arguments: BaseModel) -> None:
        if not settings.MCP_ECHO_ENABLED:
            raise ToolPermissionDenied("The echo tool is disabled by the host.")
