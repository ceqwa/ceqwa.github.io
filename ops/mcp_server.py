"""Thin MCP transport for the CEQWA administration facade.

Install the optional ``mcp`` package to run this module.  The domain services
remain usable without it, which keeps validation and unit tests lightweight.
"""

from __future__ import annotations

import json
import sys

from .api import CeqwaAPI
from .errors import CeqwaError

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:  # pragma: no cover - exercised in minimal environments
    FastMCP = None


api = CeqwaAPI()
mcp = FastMCP("CEQWA Administration") if FastMCP else None


def _safe(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except CeqwaError as exc:
        return exc.as_dict()


if mcp:
    @mcp.tool(description="Read CEQWA repository status, validation state, canonical transaction count, and pending proposals. Read-only; no approval required.")
    def ceqwa_repo_status(): return _safe(api.repo_status)

    @mcp.tool(description="Read Git working-tree status. Read-only; no approval required.")
    def ceqwa_git_status(): return _safe(api.git.status)

    @mcp.tool(description="Return the current Git diff. Read-only; no approval required.")
    def ceqwa_git_diff(): return _safe(api.git.diff)

    @mcp.tool(description="List top-level CEQWA site content. Read-only; no approval required.")
    def ceqwa_list_site_content(): return _safe(api.list_site_content)

    @mcp.tool(description="Validate canonical CEQWA financial data. Read-only; no approval required.")
    def ceqwa_validate_finances(): return _safe(api.validate_finances)

    @mcp.tool(description="Validate CEQWA static-site JSON, HTML IDs, and local references. Read-only; no approval required.")
    def ceqwa_validate_site(): return _safe(api.validate_site)

    @mcp.tool(description="Query canonical financial transactions without approval.")
    def ceqwa_find_transactions(text: str = "", transaction_id: str | None = None, period_id: str | None = None, date: str | None = None, start_date: str | None = None, end_date: str | None = None, flow: str | None = None, category: str | None = None, accounting_class: str | None = None, recurrence: str | None = None, tag: str | None = None, source_document: str | None = None):
        return _safe(api.finances.find, text=text, transaction_id=transaction_id, period_id=period_id, date=date, start_date=start_date, end_date=end_date, flow=flow, category=category, accounting_class=accounting_class, recurrence=recurrence, tag=tag, source_document=source_document)

    @mcp.tool(description="Return financial summary and CAPEX/OPEX breakdown. Read-only; no approval required.")
    def ceqwa_financial_summary(period_id: str | None = None, start_date: str | None = None, end_date: str | None = None): return _safe(api.finances.summary, period_id, start_date, end_date)

    @mcp.tool(description="List published financial periods. Read-only; no approval required.")
    def ceqwa_list_financial_periods(): return _safe(api.finances.periods)

    @mcp.tool(description="Get one canonical transaction by stable ID. Read-only; no approval required.")
    def ceqwa_get_transaction(transaction_id: str): return _safe(api.get_transaction, transaction_id)

    @mcp.tool(description="List indexed official documents. Read-only; no approval required.")
    def ceqwa_list_documents(): return _safe(api.documents.list)

    @mcp.tool(description="Extract text from a PDF using an optional parser. Output is evidence for Nanobot and never authoritative financial data. Read-only; no approval required.")
    def ceqwa_extract_pdf_text(source_document: str): return _safe(api.documents.extract_pdf_text, source_document)

    @mcp.tool(description="Render PDF pages using the optional PDF helper dependency. Output is evidence for Nanobot; no repository mutation or approval required.")
    def ceqwa_render_pdf_pages(source_document: str, output_dir: str = "incoming/rendered"): return _safe(api.documents.render_pdf_pages, source_document, output_dir)

    @mcp.tool(description="Optionally OCR an image document. OCR is evidence for Nanobot, never authoritative financial data; MCP does not interpret OCR or infer characters.")
    def ceqwa_ocr_document(source_document: str, language: str = "eng"): return _safe(api.documents.ocr_document, source_document, language)

    @mcp.tool(description="Create a preview for a structured statement extracted by Nanobot. Validates schema, duplicates, reconciliation, continuity, provenance, and derived files. Creates a proposal only; it does not modify the repository. Requires later approval and execution.")
    def ceqwa_propose_financial_import(statement: dict): return _safe(api.propose_financial_import, statement)

    @mcp.tool(description="Create a proposal to rebuild all committed financial dashboard data from the one canonical transaction dataset. Does not modify the repository; requires approval and execution.")
    def ceqwa_propose_financial_rebuild(): return _safe(api.propose_financial_rebuild)

    @mcp.tool(description="Create a before/after proposal for correcting one transaction. Does not modify the repository; requires approval and execution.")
    def ceqwa_propose_transaction_update(transaction_id: str, changes: dict): return _safe(api.propose_transaction_update, transaction_id, changes)

    @mcp.tool(description="Create a destructive proposal to remove one transaction. The source PDF remains preserved. Does not modify the repository; requires approval and execution.")
    def ceqwa_propose_transaction_delete(transaction_id: str): return _safe(api.propose_transaction_delete, transaction_id)

    @mcp.tool(description="Create a proposal to add an official document and optional Markdown companion. Does not modify the repository; requires approval and execution.")
    def ceqwa_propose_document_add(document: dict): return _safe(api.propose_document_add, document)

    @mcp.tool(description="Create a proposal for a safe Markdown companion. Does not modify the repository; requires approval and execution.")
    def ceqwa_propose_markdown_companion(document: dict): return _safe(api.propose_markdown_companion, document)

    @mcp.tool(description="Create a before/after proposal to update indexed document metadata. Does not modify the repository; requires approval and execution.")
    def ceqwa_propose_document_update(document_file: str, changes: dict): return _safe(api.propose_document_update, document_file, changes)

    @mcp.tool(description="Create a destructive proposal to remove an indexed document; it clearly lists whether the source PDF and Markdown are deleted. Requires approval and execution.")
    def ceqwa_propose_document_delete(document_file: str, delete_source: bool = True): return _safe(api.propose_document_delete, document_file, delete_source)

    @mcp.tool(description="Create a proposal for a known CEQWA page/content update. Does not modify the repository; requires approval and execution.")
    def ceqwa_propose_page_section_update(update: dict): return _safe(api.propose_content, "page_section_update", update)

    @mcp.tool(description="Create a proposal for a notice/page content change. Does not modify the repository; requires approval and execution.")
    def ceqwa_propose_notice_add(update: dict): return _safe(api.propose_content, "notice_add", update)

    @mcp.tool(description="Create a proposal for an existing notice/page content change. Does not modify the repository; requires approval and execution.")
    def ceqwa_propose_notice_update(update: dict): return _safe(api.propose_content, "notice_update", update)

    @mcp.tool(description="Create a proposal for contact information content. Does not modify the repository; requires approval and execution.")
    def ceqwa_propose_contact_update(update: dict): return _safe(api.propose_content, "contact_update", update)

    @mcp.tool(description="Create a proposal to commit validated changes. Commit is separate from publishing and requires approval.")
    def ceqwa_propose_commit(message: str, paths: list[str] | None = None): return _safe(api.propose_commit, message, paths)

    @mcp.tool(description="Create a proposal to push a branch to a remote. Requires a fresh approval separate from commit approval; validation must pass.")
    def ceqwa_propose_publish(remote: str = "origin", branch: str | None = None): return _safe(api.propose_publish, remote, branch)

    @mcp.tool(description="Get a complete persisted proposal for Nanobot to explain. Read-only; no approval required.")
    def ceqwa_get_proposal(proposal_id: str): return _safe(api.approvals.get, proposal_id)

    @mcp.tool(description="List pending or approved proposals after an interrupted conversation. Read-only; no approval required.")
    def ceqwa_list_pending_proposals(): return _safe(api.approvals.pending)

    @mcp.tool(description="Record that Nanobot has interpreted the user's conversational response as approval for this exact proposal. Issues a short-lived single-use token; does not mutate the repository.")
    def ceqwa_approve_proposal(proposal_id: str): return _safe(api.approvals.approve, proposal_id)

    @mcp.tool(description="Cancel a proposal and invalidate its approval. Safe administrative action; it does not mutate published site data.")
    def ceqwa_cancel_proposal(proposal_id: str): return _safe(api.approvals.cancel, proposal_id)

    @mcp.tool(description="Execute only an existing, unexpired proposal approved for the exact payload with its token. Cannot alter proposal contents; approval is single-use. Runs atomic rollback and validation.")
    def ceqwa_execute_proposal(proposal_id: str, approval_token: str): return _safe(api.execute, proposal_id, approval_token)


def main() -> None:
    if mcp is None:
        raise SystemExit("The optional MCP SDK is not installed. Install with: pip install -e .")
    mcp.run()


if __name__ == "__main__":
    main()
