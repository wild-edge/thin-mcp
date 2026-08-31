import json

import pytest
from django.test import RequestFactory
from ninja.errors import (
    AuthenticationError,
    AuthorizationError,
    HttpError,
    Throttled,
    ValidationError,
)

from thin_mcp import McpHttpResult
from thin_mcp.django_ninja import McpAPI, exception_instance, render_mcp_result
from thin_mcp.schemas import EmptyResult

api = McpAPI(urls_namespace="thin_mcp_tests")


def test_render_mcp_result_serializes_json_and_transport_metadata() -> None:
    result = McpHttpResult.success(7, EmptyResult())

    response = render_mcp_result(result)

    assert response.status_code == 200
    assert response["Cache-Control"] == "no-store"
    assert response["Content-Type"] == "application/json"
    assert json.loads(response.content) == {
        "jsonrpc": "2.0",
        "id": 7,
        "result": {},
    }


def test_render_mcp_result_preserves_empty_accepted_response() -> None:
    response = render_mcp_result(McpHttpResult.accepted())

    assert response.status_code == 202
    assert response["Cache-Control"] == "no-store"
    assert response.content == b""


def test_request_factory_is_available_for_adapter_hosts() -> None:
    request = RequestFactory().post("/mcp")

    assert request.method == "POST"


def test_api_maps_framework_errors_to_mcp_responses() -> None:
    request = RequestFactory().get("/mcp")

    authentication = api.authentication_error(request, AuthenticationError())
    authorization = api.authorization_error(
        request,
        AuthorizationError(message="Not allowed."),
    )
    validation = api.validation_error(request, ValidationError([]))
    http = api.http_error(request, HttpError(418, "Teapot."))
    throttled = api.throttled_error(request, Throttled(0))

    assert authentication.status_code == 401
    assert authentication["WWW-Authenticate"] == "Bearer"
    assert json.loads(authentication.content)["error"]["message"] == (
        "Authentication required."
    )
    assert authorization.status_code == 403
    assert json.loads(authorization.content)["error"]["message"] == "Not allowed."
    assert validation.status_code == 400
    assert http.status_code == 418
    assert throttled.status_code == 429
    assert throttled["Retry-After"] == "1"


def test_api_maps_parse_errors_and_preserves_request_id() -> None:
    request = RequestFactory().post(
        "/mcp",
        data=b"{",
        content_type="application/json",
    )
    request.request_id = "request-123"
    error = HttpError(400, "Cannot parse body.")
    error.__cause__ = ValueError("invalid JSON")

    response = api.on_exception(request, error)

    assert response.status_code == 400
    assert response["X-Request-ID"] == "request-123"
    assert json.loads(response.content)["error"]["code"] == -32700


def test_api_maps_unexpected_errors_without_exposing_details() -> None:
    request = RequestFactory().get("/mcp")

    response = api.internal_error(request, RuntimeError("sensitive"))

    assert response.status_code == 500
    assert json.loads(response.content)["error"]["message"] == "Internal error."


def test_exception_instance_rejects_exception_classes() -> None:
    error = RuntimeError("instance")

    assert exception_instance(error) is error
    with pytest.raises(TypeError, match="exception type"):
        exception_instance(RuntimeError)
