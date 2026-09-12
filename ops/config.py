"""Configuration and safe repository-root discovery."""

from __future__ import annotations

import os
from pathlib import Path

from .errors import CeqwaError


def find_repo_root(start: str | Path | None = None) -> Path:
    candidate = Path(start or Path(__file__).resolve().parent.parent).resolve()
    for path in (candidate, *candidate.parents):
        if (path / ".git").exists() and (path / "data" / "finances" / "finances.json").is_file():
            return path
    raise CeqwaError("REPOSITORY_NOT_FOUND", "Could not locate the CEQWA Git repository")


class Settings:
    def __init__(self, repo_root: str | Path | None = None):
        self.repo_root = find_repo_root(repo_root)
        configured = os.environ.get("CEQWA_MCP_INCOMING")
        self.incoming_root = (Path(configured).expanduser() if configured else self.repo_root / "incoming").resolve()
        self.runtime_root = self.repo_root / ".ceqwa-mcp"
        self.approval_ttl_seconds = int(os.environ.get("CEQWA_MCP_APPROVAL_TTL", "1800"))
        self.proposal_ttl_seconds = int(os.environ.get("CEQWA_MCP_PROPOSAL_TTL", "3600"))

    def ensure_runtime(self) -> None:
        for name in ("proposals", "locks", "logs"):
            (self.runtime_root / name).mkdir(parents=True, exist_ok=True)
