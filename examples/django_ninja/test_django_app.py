from collections.abc import Iterator
from unittest.mock import patch

import pytest
from django.test import Client, override_settings


@pytest.fixture
def client() -> Iterator[Client]:
    with override_settings(
        ROOT_URLCONF="examples.django_ninja.urls", MCP_ECHO_ENABLED=True
    ):
        yield Client(raise_request_exception=False)


def test_initialize(client: Client) -> None:
    response = client.post(
        "/mcp",
        content_type="application/json",
        data={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"},
            },
        },
    )
    assert response.status_code == 200
    assert response.json()["result"]["protocolVersion"] == "2025-11-25"


def test_listing_and_calling_typed_tool(client: Client) -> None:
    headers = {"MCP-Protocol-Version": "2025-11-25"}
    listing = client.post(
        "/mcp",
        headers=headers,
        content_type="application/json",
        data={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    )
    assert listing.status_code == 200
    tool = listing.json()["result"]["tools"][0]
    assert tool["name"] == "echo"
    assert tool["inputSchema"]["additionalProperties"] is False
    assert tool["annotations"]["readOnlyHint"] is True
    response = client.post(
        "/mcp",
        headers=headers,
        content_type="application/json",
        data={
            "jsonrpc": "2.0",
            "id": "call-1",
            "method": "tools/call",
            "params": {"name": "echo", "arguments": {"text": "hello"}},
        },
    )
    assert response.status_code == 200
    assert response["Cache-Control"] == "no-store"
    assert response.json()["id"] == "call-1"
    assert response.json()["result"]["structuredContent"] == {"text": "hello"}
    assert response.json()["result"]["isError"] is False


def test_notification_has_empty_response(client: Client) -> None:
    response = client.post(
        "/mcp",
        headers={"MCP-Protocol-Version": "2025-11-25"},
        content_type="application/json",
        data={"jsonrpc": "2.0", "method": "notifications/initialized"},
    )
    assert response.status_code == 202
    assert response.content == b""
    assert response["Cache-Control"] == "no-store"


@pytest.mark.parametrize("arguments", [{"text": 123}, {"text": "hello", "extra": True}])
def test_ninja_schema_rejects_invalid_tool_arguments(
    client: Client, arguments: dict[str, object]
) -> None:
    with patch("examples.django_ninja.mcp_server.tools.echoes.echo") as echo:
        response = client.post(
            "/mcp",
            headers={"MCP-Protocol-Version": "2025-11-25"},
            content_type="application/json",
            data={
                "jsonrpc": "2.0",
                "id": "invalid-call",
                "method": "tools/call",
                "params": {"name": "echo", "arguments": arguments},
            },
        )
        echo.assert_not_called()
    assert response.status_code == 200
    assert response.json()["result"]["isError"] is True


def test_disabled_tool_is_denied_before_domain_execution(client: Client) -> None:
    with (
        override_settings(MCP_ECHO_ENABLED=False),
        patch("examples.django_ninja.mcp_server.tools.echoes.echo") as echo,
    ):
        response = client.post(
            "/mcp",
            headers={"MCP-Protocol-Version": "2025-11-25"},
            content_type="application/json",
            data={
                "jsonrpc": "2.0",
                "id": "denied-call",
                "method": "tools/call",
                "params": {"name": "echo", "arguments": {"text": "hello"}},
            },
        )
        echo.assert_not_called()
    assert response.status_code == 200
    assert response.json()["id"] == "denied-call"
    assert response.json()["result"]["isError"] is True
    assert response.json()["result"]["content"] == [
        {"type": "text", "text": "The echo tool is disabled by the host."}
    ]


@pytest.mark.parametrize(
    ("body", "code"),
    [("{", -32700), ('{"jsonrpc":"2.0","id":1}', -32600), ("[]", -32600)],
)
def test_invalid_requests(client: Client, body: str, code: int) -> None:
    response = client.post("/mcp", data=body, content_type="application/json")
    assert response.status_code == 400
    assert response.json()["error"]["code"] == code
    assert response.json()["id"] is None


def test_modern_headers_are_validated(client: Client) -> None:
    payload = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/list",
        "params": {
            "_meta": {
                "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                "io.modelcontextprotocol/clientCapabilities": {},
            }
        },
    }
    invalid = client.post("/mcp", data=payload, content_type="application/json")
    assert invalid.status_code == 400
    response = client.post(
        "/mcp",
        data=payload,
        content_type="application/json",
        headers={"MCP-Protocol-Version": "2026-07-28", "Mcp-Method": "tools/list"},
    )
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["resultType"] == "complete"
    assert result["ttlMs"] == 0
    assert result["_meta"]["io.modelcontextprotocol/serverInfo"]["name"] == (
        "django-ninja-example"
    )


@pytest.mark.parametrize("request_id", [4, 0, "failed-call"])
def test_unexpected_errors_are_logged_and_redacted(
    request_id: int | str,
    client: Client, caplog: pytest.LogCaptureFixture
) -> None:
    with patch(
        "examples.django_ninja.mcp_server.tools.echoes.echo",
        side_effect=RuntimeError("private details"),
    ):
        response = client.post(
            "/mcp",
            headers={"MCP-Protocol-Version": "2025-11-25"},
            content_type="application/json",
            data={
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tools/call",
                "params": {"name": "echo", "arguments": {"text": "hello"}},
            },
        )
    assert response.status_code == 500
    assert response.json()["id"] == request_id
    assert response.json()["error"] == {"code": -32603, "message": "Internal error."}
    assert "private details" not in response.content.decode()
    assert "Unhandled MCP request error" in caplog.text
