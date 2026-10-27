"""Host-owned tool access policy and permission checks."""

# ToolContext.user is the identity the host passes to dispatch_request(user=...).
# This local example passes None; authenticate the caller before checking user access.

from pydantic import BaseModel, ConfigDict

from thin_mcp import ToolContext, ToolPermissionDenied


class ToolAccess(BaseModel):
    model_config = ConfigDict(frozen=True)

    echo_enabled: bool


class EchoEnabledPermission:
    """Check the access policy supplied by the HTTP host for this request."""

    def check(self, context: ToolContext, arguments: BaseModel) -> None:
        access = context.require_resource(ToolAccess)
        if not access.echo_enabled:
            raise ToolPermissionDenied("The echo tool is disabled by the host.")
