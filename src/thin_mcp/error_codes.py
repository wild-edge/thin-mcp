from enum import IntEnum


class JsonRpcErrorCode(IntEnum):
    """JSON-RPC 2.0 error codes used by the MCP server.

    See https://www.jsonrpc.org/specification#error_object.
    """

    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    SERVER_ERROR = -32000
