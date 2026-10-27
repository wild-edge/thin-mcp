"""Typed input and output models exposed through MCP."""

from pydantic import BaseModel, ConfigDict


class EchoArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    text: str


class EchoResult(BaseModel):
    text: str
