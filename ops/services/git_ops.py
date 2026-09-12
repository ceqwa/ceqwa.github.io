"""Read-only and approval-gated Git operations."""

from __future__ import annotations

import subprocess
import re

from ..errors import CeqwaError, require
from .repository import Repository
from .validation import require_valid, run_financial_validation, run_site_validation


class GitService:
    def __init__(self, repo: Repository):
        self.repo = repo

    def run(self, *args: str) -> str:
        result = subprocess.run(["git", *args], cwd=self.repo.root, text=True, capture_output=True, check=False)
        if result.returncode:
            raise CeqwaError("GIT_ERROR", result.stderr.strip() or "Git operation failed", {"args": args, "exit_code": result.returncode})
        return result.stdout

    def status(self) -> dict:
        porcelain = self.run("status", "--short")
        return {"success": True, "branch": self.run("branch", "--show-current").strip(), "dirty": bool(porcelain.strip()),
                "modified_files": [line[3:] for line in porcelain.splitlines() if line and line[0] in "MADRCU"],
                "untracked_files": [line[3:] for line in porcelain.splitlines() if line.startswith("??")], "porcelain": porcelain}

    def diff(self) -> dict:
        return {"success": True, "diff": self.run("diff", "--no-ext-diff"), "stat": self.run("diff", "--stat")}

    def propose_commit(self, message: str, paths: list[str] | None = None) -> tuple[dict, str, list[str]]:
        require(isinstance(message, str) and message.strip(), "INVALID_SCHEMA", "Commit message is required")
        for path in paths or []:
            self.repo.resolve_repo_path(path)
        require(all(not path.startswith("-") for path in (paths or [])), "INVALID_PATH", "Git path options are not allowed")
        status = self.status(); diff = self.diff()
        return {"kind": "commit", "message": message, "paths": paths or [], "status": status, "diff": diff}, f"Commit CEQWA changes: {message}", [], []

    def execute_commit(self, payload: dict) -> dict:
        require_valid(run_financial_validation(self.repo.root)); require_valid(run_site_validation(self.repo.root))
        args = ["add", "--"] + (payload["paths"] or ["."])
        self.run(*args); self.run("commit", "-m", payload["message"])
        return {"operation": "commit", "commit": self.run("rev-parse", "HEAD").strip(), "financial_validation": "pass", "site_validation": "pass"}

    def propose_publish(self, remote: str = "origin", branch: str | None = None) -> tuple[dict, str, list[str], list[str]]:
        branch = branch or self.status()["branch"]
        require(branch, "GIT_ERROR", "A current branch is required")
        require(re.match(r"^[A-Za-z0-9._/-]+$", remote) is not None and not remote.startswith("-"), "INVALID_SCHEMA", "Invalid Git remote")
        require(re.match(r"^[A-Za-z0-9._/-]+$", branch) is not None and not branch.startswith("-"), "INVALID_SCHEMA", "Invalid Git branch")
        return {"kind": "publish", "remote": remote, "branch": branch, "commits": self.run("log", "-1", "--oneline").strip(), "financial_validation": run_financial_validation(self.repo.root), "site_validation": run_site_validation(self.repo.root)}, f"Publish branch {branch} to {remote}", [], []

    def execute_publish(self, payload: dict) -> dict:
        require_valid(run_financial_validation(self.repo.root), "PUBLISH_VALIDATION_FAILED"); require_valid(run_site_validation(self.repo.root), "PUBLISH_VALIDATION_FAILED")
        output = self.run("push", payload["remote"], payload["branch"])
        return {"operation": "publish", "remote": payload["remote"], "branch": payload["branch"], "output": output, "financial_validation": "pass", "site_validation": "pass"}
