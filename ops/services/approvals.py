"""Persisted propose/approve/execute infrastructure."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from ..errors import CeqwaError, require
from .repository import Repository


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def payload_hash(value: object) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


class ApprovalService:
    def __init__(self, repository: Repository):
        self.repo = repository

    def _path(self, proposal_id: str) -> Path:
        # IDs are generated UUIDs; reject any caller-supplied path-like value.
        if not proposal_id or any(ch not in "0123456789abcdef-" for ch in proposal_id.lower()):
            raise CeqwaError("PROPOSAL_NOT_FOUND", "Invalid proposal ID")
        return self.repo.settings.runtime_root / "proposals" / f"{proposal_id}.json"

    def _load(self, proposal_id: str) -> dict:
        path = self._path(proposal_id)
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise CeqwaError("PROPOSAL_NOT_FOUND", f"Proposal not found: {proposal_id}") from exc

    def _save(self, proposal: dict) -> None:
        path = self._path(proposal["proposal_id"])
        self.repo.atomic_write(path.relative_to(self.repo.root), json.dumps(proposal, indent=2, ensure_ascii=False) + "\n")

    @staticmethod
    def _expired(value: str) -> bool:
        return datetime.now(timezone.utc) >= datetime.fromisoformat(value)

    def create(self, operation: str, payload: dict, *, summary: str, risk: str,
               files_to_create=None, files_to_modify=None, files_to_delete=None,
               financial_effect=None, warnings=None, validation=None) -> dict:
        import uuid
        now = datetime.now(timezone.utc)
        proposal = {
            "proposal_id": str(uuid.uuid4()),
            "operation": operation,
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(seconds=self.repo.settings.proposal_ttl_seconds)).isoformat(),
            "approval_required": True,
            "status": "pending",
            "summary": summary,
            "human_summary": summary,
            "risk": risk,
            "payload": payload,
            "payload_hash": payload_hash(payload),
            "files_to_create": files_to_create or [],
            "files_to_modify": files_to_modify or [],
            "files_to_delete": files_to_delete or [],
            "financial_effect": financial_effect or {},
            "warnings": warnings or [],
            "validation": validation or {},
        }
        self._save(proposal)
        self.repo.audit("proposal_created", proposal_id=proposal["proposal_id"], operation=operation,
                        files=proposal["files_to_create"] + proposal["files_to_modify"] + proposal["files_to_delete"])
        return self.public(proposal)

    def public(self, proposal: dict) -> dict:
        result = dict(proposal)
        result.pop("approval_token", None)
        return result

    def get(self, proposal_id: str) -> dict:
        return self.public(self._load(proposal_id))

    def pending(self) -> list[dict]:
        result = []
        for path in sorted((self.repo.settings.runtime_root / "proposals").glob("*.json")):
            try:
                item = json.loads(path.read_text(encoding="utf-8"))
                if item.get("status") in {"pending", "approved"} and not self._expired(item["expires_at"]):
                    result.append(self.public(item))
            except (OSError, json.JSONDecodeError, KeyError):
                continue
        return result

    def approve(self, proposal_id: str) -> dict:
        with self.repo.lock():
            proposal = self._load(proposal_id)
            if self._expired(proposal["expires_at"]):
                raise CeqwaError("PROPOSAL_EXPIRED", "Proposal has expired")
            if proposal.get("status") != "pending":
                raise CeqwaError("APPROVAL_INVALID", "Proposal is not awaiting approval", {"status": proposal.get("status")})
            # Agent asserted that the user approved the proposal; MCP binds that assertion to the hash.
            token = secrets.token_urlsafe(32)
            proposal.update({"status": "approved", "approval_token": token,
                             "approved_hash": proposal["payload_hash"],
                             "approval_expires_at": (datetime.now(timezone.utc) + timedelta(seconds=self.repo.settings.approval_ttl_seconds)).isoformat()})
            self._save(proposal)
            self.repo.audit("proposal_approved", proposal_id=proposal_id, operation=proposal["operation"],
                            approval_asserted_by="agent_on_behalf_of_user")
            return {"success": True, "proposal_id": proposal_id, "approval_token": token,
                    "payload_hash": proposal["payload_hash"], "expires_at": proposal["approval_expires_at"]}

    def execute(self, proposal_id: str, token: str, dispatch: Callable[[str, dict], dict]) -> dict:
        with self.repo.lock():
            proposal = self._load(proposal_id)
            if proposal.get("status") == "consumed":
                raise CeqwaError("APPROVAL_ALREADY_USED", "Approval has already been consumed")
            if proposal.get("status") != "approved":
                raise CeqwaError("APPROVAL_REQUIRED", "Proposal has not been approved")
            if self._expired(proposal["expires_at"]) or self._expired(proposal.get("approval_expires_at", proposal["expires_at"])):
                raise CeqwaError("APPROVAL_EXPIRED", "Approval has expired")
            current_hash = payload_hash(proposal.get("payload"))
            if current_hash != proposal.get("payload_hash") or current_hash != proposal.get("approved_hash"):
                raise CeqwaError("PROPOSAL_CHANGED", "The proposal payload changed after approval")
            if not isinstance(token, str) or not hmac.compare_digest(token, proposal.get("approval_token", "")):
                raise CeqwaError("APPROVAL_INVALID", "Approval token is invalid for this proposal")
            try:
                result = dispatch(proposal["operation"], proposal["payload"])
            except CeqwaError:
                proposal["status"] = "failed"
                self._save(proposal)
                self.repo.audit("proposal_failed", proposal_id=proposal_id, operation=proposal["operation"])
                raise
            proposal["status"] = "consumed"
            proposal.pop("approval_token", None)
            self._save(proposal)
            self.repo.audit("proposal_executed", proposal_id=proposal_id, operation=proposal["operation"], result="success")
            return {"success": True, "proposal_id": proposal_id, **result}

    def cancel(self, proposal_id: str) -> dict:
        with self.repo.lock():
            proposal = self._load(proposal_id)
            if proposal.get("status") == "consumed":
                raise CeqwaError("APPROVAL_INVALID", "Executed proposals cannot be cancelled")
            proposal["status"] = "cancelled"
            proposal.pop("approval_token", None)
            self._save(proposal)
            self.repo.audit("proposal_cancelled", proposal_id=proposal_id, operation=proposal["operation"])
            return {"success": True, "proposal_id": proposal_id, "status": "cancelled"}
