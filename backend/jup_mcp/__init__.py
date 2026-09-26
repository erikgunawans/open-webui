"""JUP's own MCP servers (A5, D20), each a thin wrapper over a tested `jup.*` module.

A sibling of `jup` rather than part of it because these import the `mcp` SDK, and `jup` may reach
no further than the standard library and PyYAML. Every rule lives in the wrapped `jup` module.
"""
