"""Non-destructive tests for approval, path, and financial safety boundaries."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from pathlib import Path

from ops.api import CeqwaAPI
from ops.errors import CeqwaError


ROOT = Path(__file__).resolve().parents[2]


class FixtureCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="ceqwa-mcp-test-")
        self.site = Path(self.temp.name) / "site"
        shutil.copytree(ROOT, self.site, ignore=shutil.ignore_patterns(".ceqwa-mcp", "__pycache__", ".git"))
        shutil.copytree(ROOT / ".git", self.site / ".git")
        (self.site / "incoming").mkdir(exist_ok=True)
        shutil.copyfile(ROOT / "financials" / "08.2026.pdf", self.site / "incoming" / "09.2026.pdf")
        self.api = CeqwaAPI(self.site)

    def tearDown(self):
        self.temp.cleanup()

    def test_path_sandbox(self):
        repo = self.api.repository
        for bad in ("../secret", "../../secret", "/etc/passwd", r"C:\outside\file", r"C:/outside/file", r"\\server\share\x", r"safe\..\outside"):
            with self.assertRaises(CeqwaError) as error:
                repo.resolve_repo_path(bad)
            self.assertEqual(error.exception.code, "INVALID_PATH")

    def test_document_add_without_markdown_uses_documents_directory(self):
        source = self.site / "incoming" / "constitution.pdf"
        source.write_bytes(b"test document")
        proposal = self.api.propose_document_add({
            "source_document": "incoming/constitution.pdf",
            "title": "CEQWA Constitution",
            "category": "Governance",
            "date": "2026-09-12",
        })
        self.assertEqual(proposal["payload"]["destination"], "documents/constitution.pdf")
        self.assertNotIn("markdown", proposal["payload"]["entry"])
        approval = self.api.approvals.approve(proposal["proposal_id"])
        result = self.api.execute(proposal["proposal_id"], approval["approval_token"])
        self.assertTrue(result["success"])
        metadata = json.loads((self.site / "data" / "metadata.json").read_text(encoding="utf-8"))
        saved = metadata["documents"]
        self.assertEqual(saved[0]["file"], "documents/constitution.pdf")
        self.assertNotIn("markdown", saved[0])
        self.assertTrue((self.site / "documents" / "constitution.pdf").is_file())
        self.assertFalse((self.site / "documents" / "constitution.md").exists())

    def test_document_list_update_and_delete_use_metadata(self):
        source = self.site / "incoming" / "notice.pdf"
        source.write_bytes(b"test notice")
        financials_before = json.loads((self.site / "data" / "metadata.json").read_text(encoding="utf-8"))["financials"]
        proposal = self.api.propose_document_add({"source_document": "incoming/notice.pdf"})
        approval = self.api.approvals.approve(proposal["proposal_id"])
        self.api.execute(proposal["proposal_id"], approval["approval_token"])
        listed = self.api.documents.list()
        self.assertEqual(listed["documents"][0]["file"], "documents/notice.pdf")
        self.assertEqual(json.loads((self.site / "data" / "metadata.json").read_text(encoding="utf-8"))["financials"], financials_before)

        update = self.api.propose_document_update("documents/notice.pdf", {"title": "Updated Notice"})
        approval = self.api.approvals.approve(update["proposal_id"])
        self.api.execute(update["proposal_id"], approval["approval_token"])
        self.assertEqual(self.api.documents.list()["documents"][0]["title"], "Updated Notice")

        delete = self.api.propose_document_delete("documents/notice.pdf", delete_source=False)
        approval = self.api.approvals.approve(delete["proposal_id"])
        self.api.execute(delete["proposal_id"], approval["approval_token"])
        self.assertEqual(self.api.documents.list()["documents"], [])
        self.assertTrue((self.site / "documents" / "notice.pdf").is_file())

    def test_metadata_schema_is_strict(self):
        path = self.site / "data" / "metadata.json"
        before = path.read_bytes()
        cases = [
            [],
            {},
            {"documents": []},
            {"financials": []},
            {"documents": {}, "financials": []},
            {"documents": [], "financials": "invalid"},
        ]
        try:
            for value in cases:
                path.write_text(json.dumps(value), encoding="utf-8")
                self.assertEqual(self.api.validate_site()["status"], "fail")
                self.assertEqual(self.api.validate_finances()["status"], "fail")
                with self.assertRaises(CeqwaError) as error:
                    self.api.documents.list()
                self.assertEqual(error.exception.code, "INVALID_SCHEMA")
        finally:
            path.write_bytes(before)

    def test_unknown_metadata_fields_are_rejected(self):
        source = self.site / "incoming" / "unknown.pdf"
        source.write_bytes(b"test")
        with self.assertRaises(CeqwaError) as error:
            self.api.propose_document_add({"source_document": "incoming/unknown.pdf", "unexpected": True})
        self.assertEqual(error.exception.code, "INVALID_SCHEMA")
        with self.assertRaises(CeqwaError) as error:
            self.api.propose_financial_import({"period": {"period_id": "x", "unexpected": True}})
        self.assertEqual(error.exception.code, "INVALID_SCHEMA")

    def test_document_metadata_integrity_rejects_missing_and_duplicate_files(self):
        documents_dir = self.site / "documents"
        documents_dir.mkdir(exist_ok=True)
        (documents_dir / "a.pdf").write_bytes(b"a")
        (documents_dir / "b.pdf").write_bytes(b"b")
        path = self.site / "data" / "metadata.json"
        metadata = json.loads(path.read_text(encoding="utf-8"))
        metadata["documents"] = [
            {"title": "A", "category": "Public", "date": None, "file": "documents/a.pdf"},
            {"title": "B", "category": "Public", "date": None, "file": "documents/b.pdf"},
        ]
        path.write_text(json.dumps(metadata), encoding="utf-8")
        with self.assertRaises(CeqwaError) as error:
            self.api.propose_document_update("documents/a.pdf", {"file": "documents/b.pdf"})
        self.assertEqual(error.exception.code, "INVALID_SCHEMA")

        metadata["documents"][1]["file"] = "documents/missing.pdf"
        path.write_text(json.dumps(metadata), encoding="utf-8")
        self.assertEqual(self.api.validate_site()["status"], "fail")

    def test_financial_metadata_integrity_rejects_duplicate_ids(self):
        path = self.site / "data" / "metadata.json"
        original = json.loads(path.read_text(encoding="utf-8"))
        for field in ("period_id", "period", "file"):
            metadata = json.loads(json.dumps(original))
            metadata["financials"][1][field] = metadata["financials"][0][field]
            path.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(self.api.validate_finances()["status"], "fail")
            with self.assertRaises(CeqwaError) as error:
                self.api.finances.periods()
            self.assertEqual(error.exception.code, "INVALID_SCHEMA")

        metadata = json.loads(json.dumps(original))
        metadata["financials"][0]["file"] = None
        path.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")
        self.assertEqual(self.api.validate_finances()["status"], "fail")
        with self.assertRaises(CeqwaError) as error:
            self.api.finances.periods()
        self.assertEqual(error.exception.code, "INVALID_SCHEMA")

    def test_out_of_order_financial_metadata_is_exposed_chronologically(self):
        path = self.site / "data" / "metadata.json"
        metadata = json.loads(path.read_text(encoding="utf-8"))
        metadata["financials"] = list(reversed(metadata["financials"]))
        path.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")
        self.assertEqual(
            [entry["period_id"] for entry in self.api.finances.periods()["periods"]],
            ["2026-05-source", "2026-06", "2026-07", "2026-08-source"],
        )
        self.assertEqual(
            [entry["period_id"] for entry in self.api.finances.summary()["periods"]],
            ["2026-05-source", "2026-06", "2026-07", "2026-08-source"],
        )
        self.assertEqual(self.api.validate_finances()["status"], "pass")

    def test_legacy_metadata_files_are_dead_inputs(self):
        paths = [self.site / "data" / "documents.json", self.site / "data" / "financials.json"]
        before = [path.read_bytes() for path in paths]
        try:
            for path in paths:
                path.write_text("{ invalid legacy JSON", encoding="utf-8")
            self.assertEqual(self.api.validate_site()["status"], "pass")
            self.assertEqual(self.api.validate_finances()["status"], "pass")
            self.assertEqual(self.api.documents.list()["documents"], [])
            self.assertEqual(len(self.api.finances.periods()["periods"]), 4)
            for path in paths:
                path.unlink()
            self.assertEqual(self.api.validate_site()["status"], "pass")
            self.assertEqual(self.api.documents.list()["documents"], [])
            self.assertEqual(len(self.api.finances.periods()["periods"]), 4)
        finally:
            for path, content in zip(paths, before):
                path.write_bytes(content)

    def test_no_approval_and_single_use(self):
        proposal = self.api.propose_financial_rebuild()
        with self.assertRaises(CeqwaError) as error:
            self.api.execute(proposal["proposal_id"], "not-approved")
        self.assertEqual(error.exception.code, "APPROVAL_REQUIRED")
        approval = self.api.approvals.approve(proposal["proposal_id"])
        try:
            result = self.api.execute(proposal["proposal_id"], approval["approval_token"])
        except CeqwaError as exc:
            self.fail(f"{exc.code}: {exc.details}")
        self.assertTrue(result["success"])
        with self.assertRaises(CeqwaError) as error:
            self.api.execute(proposal["proposal_id"], approval["approval_token"])
        self.assertEqual(error.exception.code, "APPROVAL_ALREADY_USED")

    def test_payload_tampering_is_blocked(self):
        proposal = self.api.propose_financial_rebuild()
        approval = self.api.approvals.approve(proposal["proposal_id"])
        path = self.site / ".ceqwa-mcp" / "proposals" / f"{proposal['proposal_id']}.json"
        saved = json.loads(path.read_text())
        saved["payload"]["tampered"] = True
        path.write_text(json.dumps(saved), encoding="utf-8")
        with self.assertRaises(CeqwaError) as error:
            self.api.execute(proposal["proposal_id"], approval["approval_token"])
        self.assertEqual(error.exception.code, "PROPOSAL_CHANGED")

    def test_wrong_proposal_token_and_expiry_are_blocked(self):
        first = self.api.propose_financial_rebuild(); second = self.api.propose_financial_rebuild()
        approval = self.api.approvals.approve(first["proposal_id"]); self.api.approvals.approve(second["proposal_id"])
        with self.assertRaises(CeqwaError) as error:
            self.api.execute(second["proposal_id"], approval["approval_token"])
        self.assertEqual(error.exception.code, "APPROVAL_INVALID")
        path = self.site / ".ceqwa-mcp" / "proposals" / f"{first['proposal_id']}.json"
        saved = json.loads(path.read_text()); saved["approval_expires_at"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(); path.write_text(json.dumps(saved), encoding="utf-8")
        with self.assertRaises(CeqwaError) as error:
            self.api.execute(first["proposal_id"], approval["approval_token"])
        self.assertEqual(error.exception.code, "APPROVAL_EXPIRED")

    def test_reconciliation_failure_cannot_be_proposed(self):
        with self.assertRaises(CeqwaError) as error:
            self.api.propose_financial_import({
                "source_document": "incoming/09.2026.pdf",
                "period": {"period_id": "bad-2026-09", "display_label": "Bad", "period_type": "calendar_month", "start_date": "2026-09-01", "end_date": "2026-09-30"},
                "opening_balance": 51763, "transactions": [], "reported_closing_balance": 51762,
            })
        self.assertEqual(error.exception.code, "FINANCIAL_RECONCILIATION_FAILED")

    def test_valid_import_is_atomic_and_validated(self):
        preserved = {"title": "Preserved", "category": "Public", "date": None, "file": "documents/preserved.pdf"}
        (self.site / "documents").mkdir(exist_ok=True)
        (self.site / "documents" / "preserved.pdf").write_bytes(b"preserved")
        metadata_path = self.site / "data" / "metadata.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["documents"] = [preserved]
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")
        proposal = self.api.propose_financial_import({
            "source_document": "incoming/09.2026.pdf",
            "period": {"period_id": "2026-09-test", "display_label": "September 2026", "source_label": "September 2026", "period_type": "calendar_month", "start_date": "2026-09-01", "end_date": "2026-09-30"},
            "opening_balance": 51763,
            "transactions": [{"date": "2026-09-03", "description": "Member contribution", "amount": 500, "flow": "income", "category": "Monthly/Quarterly Contributions", "accounting_class": "income", "recurrence": "recurring", "tags": ["monthly_quarterly_contribution"]}],
            "reported_closing_balance": 52263,
        })
        approval = self.api.approvals.approve(proposal["proposal_id"])
        try:
            result = self.api.execute(proposal["proposal_id"], approval["approval_token"])
        except CeqwaError as exc:
            self.fail(f"{exc.code}: {exc.details}")
        self.assertEqual(result["financial_validation"], "pass")
        self.assertEqual(len(self.api.finances._raw()["transactions"]), 75)
        self.assertTrue((self.site / "financials" / "09.2026.pdf").is_file())
        self.assertTrue((self.site / "financials" / "09.2026.md").is_file())
        metadata = json.loads((self.site / "data" / "metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(metadata["documents"], [preserved])
        self.assertEqual(metadata["financials"][-1]["period_id"], "2026-09-test")
        self.assertEqual(metadata["financials"][-1]["markdown"], "financials/09.2026.md")

    def test_failed_post_write_validation_rolls_back(self):
        before = {name: (self.site / name).read_bytes() for name in ("data/finances/finances.json", "data/metadata.json", "data/financials-dashboard.json")}
        proposal = self.api.propose_financial_import({
            "source_document": "incoming/09.2026.pdf",
            "period": {"period_id": "2026-09-rollback", "display_label": "September 2026", "period_type": "calendar_month", "start_date": "2026-09-01", "end_date": "2026-09-30"},
            "opening_balance": 51763, "transactions": [], "reported_closing_balance": 51763,
        })
        approval = self.api.approvals.approve(proposal["proposal_id"])
        with patch("ops.services.finances.require_valid", side_effect=CeqwaError("VALIDATION_FAILED", "injected")):
            with self.assertRaises(CeqwaError):
                self.api.execute(proposal["proposal_id"], approval["approval_token"])
        for name, content in before.items():
            self.assertEqual((self.site / name).read_bytes(), content)
        self.assertFalse((self.site / "financials" / "09.2026.pdf").exists())


if __name__ == "__main__":
    unittest.main()
