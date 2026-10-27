from enum import StrEnum


class McpHeaderName(StrEnum):
    PROTOCOL_VERSION = "MCP-Protocol-Version"
    METHOD = "Mcp-Method"
    NAME = "Mcp-Name"


class McpMethodName(StrEnum):
    SERVER_DISCOVER = "server/discover"
    INITIALIZE = "initialize"
    PING = "ping"
    TOOLS_LIST = "tools/list"
    TOOLS_CALL = "tools/call"
    PROMPTS_GET = "prompts/get"
    RESOURCES_READ = "resources/read"
