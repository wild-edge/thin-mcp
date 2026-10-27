"""Typed input and output models exposed through MCP."""

from ninja import Schema
from pydantic import ConfigDict


class EchoArguments(Schema):
    model_config = ConfigDict(extra="forbid", strict=True)

    text: str


class EchoResult(Schema):
    text: str
