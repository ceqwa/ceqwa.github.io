"""Constrained semantic content changes for known public-site files."""

from __future__ import annotations

import hashlib

from ..errors import CeqwaError, require
from .repository import Repository
from .validation import require_valid, run_site_validation


ALLOWED_CONTENT = {"index.html", "about.html", "contact.html", "documents.html", "financials.html"}


class ContentService:
    def __init__(self, repo: Repository):
        self.repo = repo

    def propose(self, kind: str, payload: dict) -> tuple[dict, str, list[str]]:
        path = payload.get("path")
        require(path in ALLOWED_CONTENT, "INVALID_PATH", "Content updates are limited to known CEQWA pages")
        target = self.repo.resolve_repo_path(path); require(target.is_file(), "FILE_NOT_FOUND", "Page does not exist")
        content = payload.get("content"); require(isinstance(content, str), "INVALID_SCHEMA", "content is required")
        before = target.read_text(encoding="utf-8")
        if payload.get("expected_sha256"):
            require(hashlib.sha256(before.encode()).hexdigest() == payload["expected_sha256"], "PROPOSAL_CHANGED", "Page changed since it was inspected")
        return {"kind": kind, "path": path, "before_sha256": hashlib.sha256(before.encode()).hexdigest(), "content": content}, f"Update {path} content", [path]

    def execute(self, payload: dict) -> dict:
        target = self.repo.resolve_repo_path(payload["path"]); before = target.read_text(encoding="utf-8")
        require(hashlib.sha256(before.encode()).hexdigest() == payload["before_sha256"], "PROPOSAL_CHANGED", "Page changed after proposal creation")
        with self.repo.mutation([payload["path"]]):
            self.repo.atomic_write(payload["path"], payload["content"]); require_valid(run_site_validation(self.repo.root))
        return {"operation": payload["kind"], "files_changed": [payload["path"]], "site_validation": "pass"}
