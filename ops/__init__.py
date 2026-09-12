"""CEQWA administration services.

The package contains deterministic repository operations for an LLM-facing MCP
server.  It deliberately does not contain an LLM or conversational approval
logic; the agent interprets the user's natural-language consent and calls the
approval endpoint.
"""

__all__ = ["api"]
