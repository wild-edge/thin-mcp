import json

import pytest
from pydantic import BaseModel, ValidationError

from thin_mcp import (
    ContentAnnotations,
    ImageContent,
    McpRequest,
    McpServer,
    TextContent,
    ToolContext,
    ToolExecutionError,
    ToolPermissionDenied,
    ToolRegistry,
)
from thin_mcp.django_ninja import render_mcp_result
from thin_mcp.schemas import ToolResult

PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/aXcAAAAASUVORK5CYII="


class Args(BaseModel):
    value: int


class Result(BaseModel):
    value: int


def request(method: str, params: dict | None = None) -> McpRequest:
    return McpRequest(jsonrpc="2.0", id=1, method=method, params=params or {})


def test_metadata_and_image_through_dispatch_and_http() -> None:
    registry = ToolRegistry()
    metadata = {"example.org/info": {"nested": [1, True, None]}}
    events = []

    def content(context: ToolContext, result: Result) -> list[ImageContent]:
        events.append((context.user, result.value))
        return [ImageContent(data=PNG, mimeType="image/png", annotations=ContentAnnotations(audience=["user"], priority=0.5, lastModified="2025-01-01T00:00:00Z"), meta={"example.org/key": ["value"]})]

    @registry.register(name="image", description="Image", arguments_model=Args, result_model=Result, meta=metadata, content_builder=content)
    def handler(context: ToolContext, arguments: Args) -> Result:
        events.append("handler")
        return Result(value=arguments.value)

    @registry.register(name="plain", description="Plain", arguments_model=Args, result_model=Result)
    def plain(context: ToolContext, arguments: Args) -> Result:
        return Result(value=arguments.value)

    server = McpServer(name="test", version="1", protocol_versions=("2025-06-18",), tools=registry)
    listing = json.loads(render_mcp_result(server.dispatch_request(None, request("tools/list"))).content)["result"]["tools"]
    assert listing[0]["_meta"] == metadata
    assert "_meta" not in listing[1]
    metadata["example.org/info"]["nested"].append("changed")
    assert registry.get("image").definition().meta != metadata
    response = server.dispatch_request("user", request("tools/call", {"name": "image", "arguments": {"value": 7}}))
    result = json.loads(render_mcp_result(response).content)["result"]
    assert events == ["handler", ("user", 7)]
    assert result["structuredContent"] == {"value": 7}
    assert result["content"][0] == {"type": "text", "text": '{"value":7}'}
    assert result["content"][1] == {"type": "image", "data": PNG, "mimeType": "image/png", "annotations": {"audience": ["user"], "priority": 0.5, "lastModified": "2025-01-01T00:00:00Z"}, "_meta": {"example.org/key": ["value"]}}
    parsed = ToolResult.model_validate(result)
    assert isinstance(parsed.content[0], TextContent)
    assert isinstance(parsed.content[1], ImageContent)
    assert [block.model_dump(by_alias=True, exclude_none=True) for block in parsed.content] == result["content"]


def test_invalid_content_and_metadata() -> None:
    for block in ({"type": "audio"}, {"type": "image", "data": PNG}, {"type": "image", "mimeType": "image/png"}):
        with pytest.raises(ValidationError):
            ToolResult.model_validate({"content": [block]})
    registry = ToolRegistry()
    with pytest.raises(ValidationError):
        ImageContent(data=PNG, mimeType="image/png", meta={"x": float("nan")})
    with pytest.raises(ValidationError):
        registry.register(name="bad", description="", arguments_model=Args, result_model=Result, meta={"x": object()})(lambda c, a: Result(value=1))


def test_callback_order_and_failures() -> None:
    events = []
    registry = ToolRegistry()

    class Permission:
        def check(self, context: ToolContext, arguments: BaseModel) -> None:
            events.append("permission")
            if arguments.value == 1:
                raise ToolPermissionDenied("denied")

    def builder(context: ToolContext, result: Result) -> list[TextContent]:
        events.append("builder")
        if result.value == 3:
            raise ToolExecutionError("expected")
        if result.value == 4:
            raise RuntimeError("unexpected")
        return []

    @registry.register(name="test", description="", arguments_model=Args, result_model=Result, permissions=(Permission(),), content_builder=builder)
    def handler(context: ToolContext, arguments: Args) -> Result:
        events.append("handler")
        if arguments.value == 2:
            raise ToolExecutionError("handler error")
        if arguments.value == 5:
            return {"value": "invalid"}  # type: ignore[return-value]
        return Result(value=arguments.value)

    tool = registry.get("test")
    assert tool is not None
    assert tool.execute(None, {}).is_error
    assert events == []
    for value in (1, 2, 5):
        events.clear()
        if value == 5:
            with pytest.raises(ValidationError):
                tool.execute(None, {"value": value})
        else:
            assert tool.execute(None, {"value": value}).is_error
        assert "builder" not in events
    events.clear()
    assert len(tool.execute(None, {"value": 0}).content) == 1
    assert events == ["permission", "handler", "builder"]
    assert tool.execute(None, {"value": 3}).content[0].text == "expected"
    with pytest.raises(RuntimeError, match="unexpected"):
        tool.execute(None, {"value": 4})
