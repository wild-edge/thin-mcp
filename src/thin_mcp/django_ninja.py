import logging
import math
from typing import Any

from django.http import HttpRequest, HttpResponse
from ninja import NinjaAPI
from ninja.errors import (
    AuthenticationError,
    AuthorizationError,
    HttpError,
    Throttled,
    ValidationError,
)

from thin_mcp.error_codes import JsonRpcErrorCode
from thin_mcp.responses import McpHttpResult

logger = logging.getLogger(__name__)


def exception_instance[ExceptionT: Exception](
    exc: ExceptionT | type[ExceptionT],
) -> ExceptionT:
    if isinstance(exc, type):
        raise TypeError("Django Ninja passed an exception type instead of an instance.")
    return exc


class McpAPI(NinjaAPI):
    """Ninja API with MCP error envelopes and exact transport responses."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.add_exception_handler(AuthenticationError, self.authentication_error)
        self.add_exception_handler(AuthorizationError, self.authorization_error)
        self.add_exception_handler(ValidationError, self.validation_error)
        self.add_exception_handler(Throttled, self.throttled_error)
        self.add_exception_handler(HttpError, self.http_error)
        self.add_exception_handler(Exception, self.internal_error)

    def error_response(
        self,
        request: HttpRequest,
        *,
        status: int,
        code: int,
        message: str,
    ) -> HttpResponse:
        result = McpHttpResult.error(None, code, message, status=status)
        if result.body is None:  # pragma: no cover - error always has a body
            raise RuntimeError("MCP error response has no body.")
        return self.create_response(
            request,
            result.body.model_dump(mode="json", by_alias=True),
            status=status,
        )

    def authentication_error(
        self,
        request: HttpRequest,
        exc: AuthenticationError | type[AuthenticationError],
    ) -> HttpResponse:
        error = exception_instance(exc)
        response = self.error_response(
            request,
            status=error.status_code,
            code=JsonRpcErrorCode.SERVER_ERROR,
            message="Authentication required.",
        )
        response["WWW-Authenticate"] = "Bearer"
        return response

    def authorization_error(
        self,
        request: HttpRequest,
        exc: AuthorizationError | type[AuthorizationError],
    ) -> HttpResponse:
        error = exception_instance(exc)
        return self.error_response(
            request,
            status=error.status_code,
            code=JsonRpcErrorCode.SERVER_ERROR,
            message=str(error),
        )

    def validation_error(
        self,
        request: HttpRequest,
        exc: ValidationError | type[ValidationError],
    ) -> HttpResponse:
        exception_instance(exc)
        return self.error_response(
            request,
            status=400,
            code=JsonRpcErrorCode.INVALID_REQUEST,
            message="Invalid Request.",
        )

    def http_error(
        self,
        request: HttpRequest,
        exc: HttpError | type[HttpError],
    ) -> HttpResponse:
        error = exception_instance(exc)
        return self.error_response(
            request,
            status=error.status_code,
            code=JsonRpcErrorCode.SERVER_ERROR,
            message=str(error),
        )

    def throttled_error(
        self,
        request: HttpRequest,
        exc: Throttled | type[Throttled],
    ) -> HttpResponse:
        error = exception_instance(exc)
        response = self.error_response(
            request,
            status=error.status_code,
            code=JsonRpcErrorCode.SERVER_ERROR,
            message=str(error),
        )
        if error.wait is not None:
            response["Retry-After"] = str(max(math.ceil(error.wait), 1))
        return response

    def internal_error(
        self,
        request: HttpRequest,
        exc: Exception | type[Exception],
    ) -> HttpResponse:
        error = exception_instance(exc)
        logger.error("Unhandled MCP request error", exc_info=error)
        return self.error_response(
            request,
            status=500,
            code=JsonRpcErrorCode.INTERNAL_ERROR,
            message="Internal error.",
        )

    def on_exception(
        self,
        request: HttpRequest,
        exc: Exception | type[Exception],
    ) -> HttpResponse:
        error = exception_instance(exc)
        if (
            isinstance(error, HttpError)
            and error.status_code == 400
            and error.__cause__ is not None
        ):
            response = render_mcp_result(
                McpHttpResult.error(
                    None,
                    JsonRpcErrorCode.PARSE_ERROR,
                    "Parse error.",
                    status=400,
                )
            )
        else:
            response = super().on_exception(request, error)
        if hasattr(request, "request_id"):
            response["X-Request-ID"] = request.request_id
        return response


def render_mcp_result(result: McpHttpResult) -> HttpResponse:
    if result.body is None:
        response = HttpResponse(status=result.status)
    else:
        response = HttpResponse(
            result.body.model_dump_json(by_alias=True),
            content_type="application/json",
            status=result.status,
        )
    response["Cache-Control"] = "no-store"
    return response
