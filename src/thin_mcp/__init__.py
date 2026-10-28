"""Reusable MCP protocol and tool registration infrastructure."""

from thin_mcp.enums import McpHeaderName, McpMethodName
from thin_mcp.error_codes import JsonRpcErrorCode
from thin_mcp.protocol import McpRequestHeaders
from thin_mcp.responses import McpHttpResult
from thin_mcp.schemas import (
    ContentAnnotations,
    ContentBlock,
    EmptyToolArguments,
    ImageContent,
    McpRequest,
    TextContent,
    ToolAnnotations,
    ToolCallParams,
)
from thin_mcp.server import McpServer
from thin_mcp.tools import (
    ContentBuilder,
    ToolContext,
    ToolExecutionError,
    ToolPermission,
    ToolPermissionDenied,
    ToolRegistry,
)

__all__ = (
    "ContentAnnotations",
    "ContentBlock",
    "ContentBuilder",
    "EmptyToolArguments",
    "ImageContent",
    "JsonRpcErrorCode",
    "McpHeaderName",
    "McpHttpResult",
    "McpMethodName",
    "McpRequest",
    "McpRequestHeaders",
    "McpServer",
    "TextContent",
    "ToolAnnotations",
    "ToolCallParams",
    "ToolContext",
    "ToolExecutionError",
    "ToolPermission",
    "ToolPermissionDenied",
    "ToolRegistry",
)
