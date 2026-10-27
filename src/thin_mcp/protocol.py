"""Per-request MCP metadata and Streamable HTTP header validation."""

import base64
import re
from collections.abc import Mapping

from pydantic import BaseModel, ValidationError

from thin_mcp.enums import McpHeaderName, McpMethodName
from thin_mcp.error_codes import JsonRpcErrorCode
from thin_mcp.responses import McpHttpResult
from thin_mcp.schemas import (
    McpRequest,
    RequestMetadata,
    UnsupportedProtocolVersionData,
)

MODERN_PROTOCOL_VERSION = "2026-07-28"
PROTOCOL_VERSION_META_KEY = "io.modelcontextprotocol/protocolVersion"


class McpRequestHeaders(BaseModel):
    protocol_version: str | None = None
    method: str | None = None
    name: str | None = None

    @classmethod
    def from_mapping(cls, headers: Mapping[str, str]) -> "McpRequestHeaders":
        normalized = {key.lower(): value for key, value in headers.items()}
        return cls(
            protocol_version=normalized.get(McpHeaderName.PROTOCOL_VERSION.lower()),
            method=normalized.get(McpHeaderName.METHOD.lower()),
            name=normalized.get(McpHeaderName.NAME.lower()),
        )


def has_protocol_metadata(request: McpRequest) -> bool:
    meta = request.params.get("_meta")
    return isinstance(meta, dict) and PROTOCOL_VERSION_META_KEY in meta


def is_modern_version(version: str | None) -> bool:
    return bool(
        version
        and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", version)
        and version >= MODERN_PROTOCOL_VERSION
    )


def uses_modern_protocol(request: McpRequest, headers: McpRequestHeaders) -> bool:
    if has_protocol_metadata(request):
        return True
    # Initialization proposes a version in its params and negotiates a
    # handshake-era revision even when the HTTP header is newer.
    return request.method != McpMethodName.INITIALIZE and is_modern_version(
        headers.protocol_version
    )


def decode_name_header(value: str) -> str:
    if not re.fullmatch(r"[\x20-\x7e\t]*", value) or value != value.strip():
        raise ValueError("Invalid header characters.")
    if value.startswith("=?base64?") and value.endswith("?="):
        return base64.b64decode(value[9:-2], validate=True).decode("utf-8")
    return value


def validate_modern_request(
    request: McpRequest,
    headers: McpRequestHeaders,
    supported_versions: tuple[str, ...],
) -> McpHttpResult | None:
    try:
        metadata = RequestMetadata.model_validate(request.params.get("_meta"))
    except ValidationError:
        return McpHttpResult.error(
            request.id,
            JsonRpcErrorCode.INVALID_PARAMS,
            "Required protocol metadata is missing or invalid.",
            status=400,
        )

    mismatched_header: McpHeaderName | None = None
    if headers.protocol_version != metadata.protocol_version:
        mismatched_header = McpHeaderName.PROTOCOL_VERSION
    elif headers.method != request.method:
        mismatched_header = McpHeaderName.METHOD
    elif request.method in {
        McpMethodName.TOOLS_CALL,
        McpMethodName.PROMPTS_GET,
        McpMethodName.RESOURCES_READ,
    }:
        source = "uri" if request.method == McpMethodName.RESOURCES_READ else "name"
        try:
            if headers.name is None or decode_name_header(
                headers.name
            ) != request.params.get(source):
                mismatched_header = McpHeaderName.NAME
        except ValueError:
            mismatched_header = McpHeaderName.NAME

    if mismatched_header is not None:
        return McpHttpResult.error(
            request.id,
            JsonRpcErrorCode.HEADER_MISMATCH,
            f"Missing, malformed, or mismatched {mismatched_header} header.",
            status=400,
        )
    if metadata.protocol_version not in supported_versions:
        return McpHttpResult.error(
            request.id,
            JsonRpcErrorCode.UNSUPPORTED_PROTOCOL_VERSION,
            "Unsupported protocol version.",
            status=400,
            data=UnsupportedProtocolVersionData(
                supported=list(supported_versions), requested=metadata.protocol_version
            ),
        )
    return None
