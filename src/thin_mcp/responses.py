from dataclasses import dataclass

from pydantic import BaseModel

from thin_mcp.schemas import (
    JsonRpcError,
    JsonRpcErrorResponse,
    JsonRpcResultResponse,
    McpRequestId,
    ToolResult,
)


@dataclass(frozen=True)
class McpHttpResult:
    """A protocol response together with its HTTP transport status."""

    status: int = 200
    body: JsonRpcErrorResponse | JsonRpcResultResponse | None = None

    @classmethod
    def success(
        cls,
        request_id: McpRequestId | None,
        result: BaseModel,
    ) -> "McpHttpResult":
        return cls(body=JsonRpcResultResponse(id=request_id, result=result))

    @classmethod
    def error(
        cls,
        request_id: McpRequestId | None,
        code: int,
        message: str,
        *,
        status: int = 200,
        data: BaseModel | None = None,
    ) -> "McpHttpResult":
        return cls(
            status=status,
            body=JsonRpcErrorResponse(
                id=request_id,
                error=JsonRpcError(code=code, message=message, data=data),
            ),
        )

    @classmethod
    def accepted(cls) -> "McpHttpResult":
        return cls(status=202)

    @property
    def is_error(self) -> bool:
        return (
            self.status >= 400
            or isinstance(self.body, JsonRpcErrorResponse)
            or (
                isinstance(self.body, JsonRpcResultResponse)
                and isinstance(self.body.result, ToolResult)
                and self.body.result.is_error
            )
        )
