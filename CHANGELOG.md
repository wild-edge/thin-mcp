# Changelog

All notable changes to this project are documented here. The project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Modern MCP `2026-07-28` discovery, metadata, and Streamable HTTP header
  validation while preserving legacy initialization behavior.
- Protocol header and method enums, plus structured unsupported-version errors.

## [0.1.0] - 2026-08-31

### Added

- Typed MCP request, response, initialization, and tool schemas.
- Explicit typed tool registry with permission and request-resource support.
- Transport-independent MCP dispatch for initialization, ping, tool listing,
  tool calls, and notifications.
- Optional Django Ninja HTTP and exception adapter.

[Unreleased]: https://github.com/wild-edge/thin-mcp/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/wild-edge/thin-mcp/releases/tag/v0.1.0
