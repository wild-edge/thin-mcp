from collections.abc import Iterator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from examples.fastapi.app import app
from examples.fastapi.dependencies import get_tool_access
from examples.fastapi.permissions import ToolAccess


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def test_initialize(client: TestClient) -> None:
    response = client.post(
        "/mcp",
        json={
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


def test_listing_and_calling_typed_tool(client: TestClient) -> None:
    headers = {"MCP-Protocol-Version": "2025-11-25"}
    listing = client.post(
        "/mcp",
        headers=headers,
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    )
    assert listing.status_code == 200
    tool = listing.json()["result"]["tools"][0]
    assert tool["name"] == "echo"
    assert tool["inputSchema"]["additionalProperties"] is False
    assert tool["annotations"]["readOnlyHint"] is True
    response = client.post(
        "/mcp",
        headers=headers,
        json={
            "jsonrpc": "2.0",
            "id": "call-1",
            "method": "tools/call",
            "params": {"name": "echo", "arguments": {"text": "hello"}},
        },
    )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["id"] == "call-1"
    assert response.json()["result"]["structuredContent"] == {"text": "hello"}
    assert response.json()["result"]["isError"] is False


def test_notification_has_empty_response(client: TestClient) -> None:
    response = client.post(
        "/mcp",
        headers={"MCP-Protocol-Version": "2025-11-25"},
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
    )
    assert response.status_code == 202
    assert response.content == b""
    assert response.headers["cache-control"] == "no-store"


def test_disabled_tool_is_denied_before_domain_execution(client: TestClient) -> None:
    def disabled_access() -> ToolAccess:
        return ToolAccess(echo_enabled=False)

    app.dependency_overrides[get_tool_access] = disabled_access
    try:
        with patch("examples.fastapi.mcp_server.tools.echoes.core.echo") as echo:
            response = client.post(
                "/mcp",
                headers={"MCP-Protocol-Version": "2025-11-25"},
                json={
                    "jsonrpc": "2.0",
                    "id": "denied-call",
                    "method": "tools/call",
                    "params": {"name": "echo", "arguments": {"text": "hello"}},
                },
            )
            echo.assert_not_called()
    finally:
        del app.dependency_overrides[get_tool_access]
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
def test_invalid_requests(client: TestClient, body: str, code: int) -> None:
    response = client.post(
        "/mcp", content=body, headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == code


def test_modern_headers_are_validated(client: TestClient) -> None:
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
    invalid = client.post("/mcp", json=payload)
    assert invalid.status_code == 400
    response = client.post(
        "/mcp",
        json=payload,
        headers={"MCP-Protocol-Version": "2026-07-28", "Mcp-Method": "tools/list"},
    )
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["resultType"] == "complete"
    assert result["ttlMs"] == 0
    assert result["_meta"]["io.modelcontextprotocol/serverInfo"]["name"] == (
        "fastapi-example"
    )


def test_unexpected_errors_are_logged_and_redacted(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with patch(
        "examples.fastapi.mcp_server.tools.echoes.core.echo",
        side_effect=RuntimeError("private details"),
    ):
        response = client.post(
            "/mcp",
            headers={"MCP-Protocol-Version": "2025-11-25"},
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "echo", "arguments": {"text": "hello"}},
            },
        )
    assert response.status_code == 500
    assert response.json()["error"] == {"code": -32603, "message": "Internal error."}
    assert "private details" not in response.text
    assert "Unhandled MCP request error" in caplog.text
