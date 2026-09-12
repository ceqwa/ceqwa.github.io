"""Public Python facade used by MCP handlers, tests, and future admin UIs."""

from __future__ import annotations

from .errors import CeqwaError
from .config import Settings
from .services.approvals import ApprovalService
from .services.content import ContentService
from .services.documents import DocumentService
from .services.finances import FinanceService
from .services.git_ops import GitService
from .services.repository import Repository
from .services.validation import run_financial_validation, run_site_validation


class CeqwaAPI:
    def __init__(self, repo_root=None):
        self.repository = Repository(Settings(repo_root))
        self.approvals = ApprovalService(self.repository)
        self.finances = FinanceService(self.repository)
        self.documents = DocumentService(self.repository)
        self.content = ContentService(self.repository)
        self.git = GitService(self.repository)

    def _proposal(self, operation, payload, summary, risk, create=None, modify=None, delete=None, effect=None, warnings=None, validation=None):
        return self.approvals.create(operation, payload, summary=summary, risk=risk, files_to_create=create, files_to_modify=modify, files_to_delete=delete, financial_effect=effect, warnings=warnings, validation=validation)

    # Read-only operations.
    def repo_status(self):
        result = self.git.status()
        result.update({"canonical_transactions": len(self.finances._raw().get("transactions", [])),
                       "financial_periods": len(self.finances._index()),
                       "financial_validation": run_financial_validation(self.repository.root),
                       "site_validation": run_site_validation(self.repository.root),
                       "pending_proposals": len(self.approvals.pending())})
        return result

    def list_site_content(self):
        return {"success": True, "files": sorted(str(p.relative_to(self.repository.root)).replace("\\", "/") for p in self.repository.root.iterdir() if p.name not in {".git", ".ceqwa-mcp"})}

    def git_diff(self):
        return self.git.diff()

    def get_transaction(self, transaction_id):
        result = self.finances.find(transaction_id=transaction_id)
        if not result["transactions"]:
            return {"success": False, "error_code": "UNKNOWN_TRANSACTION", "message": "Transaction not found"}
        return {"success": True, "transaction": result["transactions"][0]}

    def validate_finances(self):
        return run_financial_validation(self.repository.root)

    def validate_site(self):
        return run_site_validation(self.repository.root)

    # Proposal creators.
    def propose_financial_import(self, payload):
        normalized, effect, possible, summary = self.finances.propose_import(payload)
        normalized["possible_duplicates"] = possible
        validation = {"status": "pass", "reconciliation": "pass"}
        return self._proposal("financial_import", normalized, summary, "financial", create=[normalized["destination"], normalized["markdown_destination"]], modify=["data/finances/finances.json", "data/metadata.json", "data/financials-dashboard.json"], effect=effect, warnings=["possible duplicates detected"] if possible else [], validation=validation) | {"possible_duplicates": possible}

    def propose_transaction_update(self, transaction_id, changes):
        payload, summary = self.finances.propose_update(transaction_id, changes)
        return self._proposal("transaction_update", payload, summary, "financial", modify=["data/finances/finances.json", "data/financials-dashboard.json"])

    def propose_transaction_delete(self, transaction_id):
        payload, summary = self.finances.propose_delete(transaction_id)
        return self._proposal("transaction_delete", payload, summary, "destructive", modify=["data/finances/finances.json", "data/financials-dashboard.json"])

    def propose_financial_rebuild(self):
        payload = {"kind": "financial_rebuild"}
        return self._proposal("financial_rebuild", payload, "Rebuild financial dashboard data from canonical transactions", "financial", modify=["data/financials-dashboard.json"])

    def propose_document_add(self, payload):
        normalized, summary, creates, modifies = self.documents.propose_add(payload)
        return self._proposal("document_add", normalized, summary, "content", create=creates, modify=modifies)

    def propose_markdown_companion(self, payload):
        normalized, summary, creates = self.documents.propose_markdown(payload)
        return self._proposal("markdown_companion", normalized, summary, "content", create=creates)

    def propose_document_update(self, document_file, changes):
        payload, summary, modifies = self.documents.propose_update(document_file, changes)
        return self._proposal("document_update", payload, summary, "content", modify=modifies)

    def propose_document_delete(self, document_file, delete_source=True):
        payload, summary, creates, modifies, deletes = self.documents.propose_delete(document_file, delete_source)
        return self._proposal("document_delete", payload, summary, "destructive", create=creates, modify=modifies, delete=deletes)

    def propose_content(self, kind, payload):
        normalized, summary, affected = self.content.propose(kind, payload)
        return self._proposal(kind, normalized, summary, "content", modify=affected)

    def propose_commit(self, message, paths=None):
        payload, summary, _, _ = self.git.propose_commit(message, paths)
        return self._proposal("commit", payload, summary, "publish", validation={"financial": run_financial_validation(self.repository.root), "site": run_site_validation(self.repository.root)})

    def propose_publish(self, remote="origin", branch=None):
        payload, summary, _, _ = self.git.propose_publish(remote, branch)
        return self._proposal("publish", payload, summary, "publish", validation={"financial": payload["financial_validation"], "site": payload["site_validation"]})

    def _dispatch(self, operation, payload):
        if operation == "financial_import": return self.finances.execute_import(payload)
        if operation == "transaction_update": return self.finances.execute_update(payload)
        if operation == "transaction_delete": return self.finances.execute_delete(payload)
        if operation == "financial_rebuild":
            with self.repository.mutation(["data/financials-dashboard.json"]):
                self.repository.write_json("data/financials-dashboard.json", self.finances.rebuild_dashboard()); from .services.validation import require_valid; require_valid(run_financial_validation(self.repository.root)); require_valid(run_site_validation(self.repository.root))
            return {"operation": operation, "files_changed": ["data/financials-dashboard.json"], "financial_validation": "pass", "site_validation": "pass"}
        if operation == "document_add": return self.documents.execute_add(payload)
        if operation == "markdown_companion": return self.documents.execute_markdown(payload)
        if operation == "document_update": return self.documents.execute_update(payload)
        if operation == "document_delete": return self.documents.execute_delete(payload)
        if operation in {"notice_add", "notice_update", "contact_update", "page_section_update"}: return self.content.execute(payload)
        if operation == "commit": return self.git.execute_commit(payload)
        if operation == "publish": return self.git.execute_publish(payload)
        raise CeqwaError("INVALID_OPERATION", f"Unsupported operation: {operation}")

    def execute(self, proposal_id, approval_token):
        return self.approvals.execute(proposal_id, approval_token, self._dispatch)

    def result(self, action, fn):
        try:
            return fn()
        except CeqwaError as exc:
            return exc.as_dict()
