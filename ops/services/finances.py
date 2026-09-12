"""Canonical CEQWA financial queries, previews, imports, and rebuilds."""

from __future__ import annotations

import copy
import hashlib
import json
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from ..errors import CeqwaError, require
from .metadata import ordered_financials
from .repository import Repository
from .validation import require_valid, run_financial_validation, run_site_validation


def money(value: object) -> Decimal:
    if isinstance(value, bool):
        raise ValueError("boolean is not an amount")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"invalid amount: {value}") from exc
    if amount < 0:
        raise ValueError("amount cannot be negative")
    return amount


def number(value: Decimal) -> int | float:
    return int(value) if value == value.to_integral() else float(value)


class FinanceService:
    def __init__(self, repo: Repository):
        self.repo = repo

    def _raw(self) -> dict:
        return self.repo.load_json("data/finances/finances.json")

    def _index(self) -> list[dict]:
        return ordered_financials(self.repo.load_metadata()["financials"])

    def _dashboard(self) -> dict:
        return self.repo.load_json("data/financials-dashboard.json")

    def periods(self) -> dict:
        return {"success": True, "periods": self._index()}

    def summary(self, period_id: str | None = None, start_date: str | None = None, end_date: str | None = None) -> dict:
        raw = self._raw()
        index = self._index()
        selected = {p["period_id"]: p for p in index}
        if period_id:
            require(period_id in selected, "UNKNOWN_PERIOD", f"Unknown financial period: {period_id}")
            selected = {period_id: selected[period_id]}
        start = date.fromisoformat(start_date) if start_date else None
        end = date.fromisoformat(end_date) if end_date else None
        rows = []
        for row in raw["transactions"]:
            period = next((p for p in selected.values() if Path(p["file"]).name == row.get("source_file")), None)
            if not period:
                continue
            if start and row.get("date") and date.fromisoformat(row["date"]) < start:
                continue
            if end and row.get("date") and date.fromisoformat(row["date"]) > end:
                continue
            rows.append(row)
        return {"success": True, **self._aggregate(rows), "periods": list(selected.values())}

    def _aggregate(self, rows: list[dict]) -> dict:
        def total(predicate):
            return number(sum((money(r["amount"]) for r in rows if predicate(r)), Decimal(0)))
        income = total(lambda r: "income" in r.get("tags", []))
        expenses = total(lambda r: "expense" in r.get("tags", []))
        opening = total(lambda r: "opening_balance" in r.get("tags", []))
        categories = defaultdict(Decimal)
        for row in rows:
            categories[row.get("raw_category", "unknown")] += money(row["amount"])
        return {"transaction_count": len(rows), "opening": opening, "income": income, "expenses": expenses,
                "closing": number(Decimal(str(opening)) + Decimal(str(income)) - Decimal(str(expenses))),
                "CAPEX": total(lambda r: r.get("accounting_class") == "capex"),
                "OPEX": total(lambda r: r.get("accounting_class") == "opex"),
                "recurring_income": total(lambda r: "income" in r.get("tags", []) and r.get("recurrence") == "recurring"),
                "one_off_income": total(lambda r: "income" in r.get("tags", []) and r.get("recurrence") == "one_off"),
                "quarterly_income": total(lambda r: "income" in r.get("tags", []) and "monthly_quarterly_contribution" in r.get("tags", [])),
                "one_off_expenses": total(lambda r: "expense" in r.get("tags", []) and r.get("recurrence") == "one_off"),
                "category_totals": {k: number(v) for k, v in sorted(categories.items())}}

    def find(self, **filters) -> dict:
        rows = self._raw().get("transactions", [])
        result = []
        for row in rows:
            if filters.get("transaction_id") and row.get("transaction_id") != filters["transaction_id"]:
                continue
            if filters.get("period_id") and not row.get("source_file", "").startswith(filters["period_id"].replace("-source", "")):
                # Match by index below for non-monthly filenames.
                period = next((p for p in self._index() if p["period_id"] == filters["period_id"]), None)
                if not period or Path(period["file"]).name != row.get("source_file"):
                    continue
            if filters.get("source_document") and row.get("source_file") != Path(filters["source_document"]).name:
                continue
            if filters.get("flow") and filters["flow"] not in row.get("tags", []):
                continue
            if filters.get("category") and row.get("raw_category") != filters["category"]:
                continue
            if filters.get("accounting_class") and row.get("accounting_class") != filters["accounting_class"]:
                continue
            if filters.get("recurrence") and row.get("recurrence") != filters["recurrence"]:
                continue
            if filters.get("tag") and filters["tag"] not in row.get("tags", []):
                continue
            if filters.get("date") is not None and row.get("date") != filters["date"]:
                continue
            if filters.get("start_date") and row.get("date") and row["date"] < filters["start_date"]:
                continue
            if filters.get("end_date") and row.get("date") and row["date"] > filters["end_date"]:
                continue
            text = filters.get("text", "").lower()
            if text and text not in json.dumps(row, ensure_ascii=False).lower():
                continue
            result.append(row)
        return {"success": True, "transactions": result, "count": len(result)}

    def _validate_input(self, payload: dict) -> tuple[dict, list[dict], dict, list[str]]:
        require(isinstance(payload, dict), "INVALID_SCHEMA", "Financial import must be an object")
        allowed_import_fields = {"source_document", "period", "opening_balance", "transactions", "reported_closing_balance"}
        unknown_import_fields = sorted(set(payload) - allowed_import_fields)
        require(not unknown_import_fields, "INVALID_SCHEMA", "Financial import contains unknown fields", {"fields": unknown_import_fields})
        period = payload.get("period")
        require(isinstance(period, dict), "INVALID_SCHEMA", "period metadata is required")
        allowed_period_fields = {"description", "period", "period_id", "display_label", "source_label", "period_type", "start_date", "end_date", "allowed_out_of_period_dates", "period_note"}
        unknown_period_fields = sorted(set(period) - allowed_period_fields)
        require(not unknown_period_fields, "INVALID_SCHEMA", "period contains unknown fields", {"fields": unknown_period_fields})
        for key in ("period_id", "display_label", "period_type", "start_date", "end_date"):
            require(period.get(key), "INVALID_SCHEMA", f"period.{key} is required")
        try:
            start, end = date.fromisoformat(period["start_date"]), date.fromisoformat(period["end_date"])
        except ValueError as exc:
            raise CeqwaError("INVALID_SCHEMA", "Period dates must be ISO dates") from exc
        require(start <= end, "INVALID_SCHEMA", "Period start_date must not be after end_date")
        source = payload.get("source_document")
        require(isinstance(source, str), "INVALID_SCHEMA", "source_document is required")
        source_path = self.repo.resolve_repo_path(source, allow_incoming=True)
        require(source_path.is_file(), "FILE_NOT_FOUND", f"Source file does not exist: {source}")
        current = self._raw()
        index = self._index()
        require(not any(p.get("period_id") == period["period_id"] for p in index), "DUPLICATE_PERIOD",
                "A financial period with this period_id already exists", {"period_id": period["period_id"]})
        destination_candidate = self.repo.resolve_repo_path(f"financials/{source_path.name}")
        require(not destination_candidate.exists(), "DUPLICATE_DOCUMENT", "A financial source file with this name already exists", {"file": str(destination_candidate.relative_to(self.repo.root)).replace("\\", "/")})
        allowed_tags = {tag for group in current.get("tagging_system", {}).get("tag_groups", {}).values() for tag in group}
        candidate_rows = []
        confirmed, possible = [], []
        existing_ids = {row.get("transaction_id") for row in current.get("transactions", [])}
        allowed_transaction_fields = {"transaction_id", "date", "description", "source_description", "amount", "flow", "category", "accounting_class", "recurrence", "tags", "tag_confidence", "normalized_description", "source_page", "capex_status", "capex_reason"}
        for item in payload.get("transactions", []):
            require(isinstance(item, dict), "INVALID_SCHEMA", "Each transaction must be an object")
            unknown_transaction_fields = sorted(set(item) - allowed_transaction_fields)
            require(not unknown_transaction_fields, "INVALID_SCHEMA", "Transaction contains unknown fields", {"fields": unknown_transaction_fields})
            for key in ("description", "amount", "flow", "accounting_class", "recurrence"):
                require(key in item, "INVALID_SCHEMA", f"transaction.{key} is required")
            try:
                amount = money(item["amount"])
            except ValueError as exc:
                raise CeqwaError("INVALID_SCHEMA", str(exc)) from exc
            tx_date = item.get("date")
            if tx_date is not None:
                try:
                    date.fromisoformat(tx_date)
                except ValueError as exc:
                    raise CeqwaError("INVALID_SCHEMA", f"Invalid transaction date: {tx_date}") from exc
            flow = item["flow"]
            require(flow in {"income", "expense", "opening_balance"}, "INVALID_SCHEMA", f"Invalid flow: {flow}")
            if flow == "expense":
                require(item["accounting_class"] in {"opex", "capex"}, "INVALID_SCHEMA", "Expenses must be CAPEX or OPEX")
            if flow == "income":
                require(item["accounting_class"] == "income", "INVALID_SCHEMA", "Income must use accounting_class income")
            if flow == "opening_balance":
                require(item["accounting_class"] == "opening_balance", "INVALID_SCHEMA", "Opening balance classification is invalid")
            tags = list(dict.fromkeys(item.get("tags", [])))
            tags.insert(0, flow) if flow not in tags else None
            if flow == "expense" and item["accounting_class"] not in tags:
                tags.append(item["accounting_class"])
            unknown = sorted(set(tags) - allowed_tags)
            require(not unknown, "INVALID_SCHEMA", "Unknown transaction tags", {"tags": unknown})
            stable = item.get("transaction_id") or self._candidate_id(period["period_id"], item)
            source_description = item.get("source_description", item["description"])
            row = {"transaction_id": stable, "date": tx_date, "source_file": Path(source).name,
                   "raw_category": item.get("category", "Unknown"), "raw_description": source_description,
                   "amount": number(amount), "tags": tags, "tag_confidence": item.get("tag_confidence", "medium"),
                   "recurrence": item["recurrence"], "accounting_class": item["accounting_class"]}
            if item["description"] != source_description:
                row["normalized_description"] = item["description"]
            for optional in ("normalized_description", "source_page", "capex_status", "capex_reason"):
                if optional in item:
                    row[optional] = item[optional]
            if stable in existing_ids:
                confirmed.append({"transaction_id": stable, "reason": "transaction_id already exists"})
            elif any(row["raw_description"] == old.get("raw_description") and row["amount"] == old.get("amount") and row["source_file"] == old.get("source_file") for old in current["transactions"]):
                possible.append({"transaction_id": stable, "reason": "same description, amount, and source"})
            candidate_rows.append(row)
        supplied_opening = money(payload.get("opening_balance", 0))
        if supplied_opening and not any("opening_balance" in r["tags"] for r in candidate_rows):
            candidate_rows.insert(0, {"transaction_id": f"{period['period_id']}-opening", "date": None,
                "source_file": Path(source).name, "raw_category": "Opening Balances",
                "raw_description": f"Opening balance for {period['display_label']}", "amount": number(supplied_opening),
                "tags": ["opening_balance"], "tag_confidence": "source", "recurrence": "not_applicable",
                "accounting_class": "opening_balance"})
        require(not confirmed, "DUPLICATE_TRANSACTION", "Import contains existing transaction IDs", {"confirmed_duplicates": confirmed})
        if any("opening_balance" in r["tags"] for r in candidate_rows):
            opening = sum((money(r["amount"]) for r in candidate_rows if "opening_balance" in r["tags"]), Decimal(0))
            require(opening == money(payload.get("opening_balance", opening)), "INVALID_SCHEMA", "Opening balance does not match transaction rows")
        opening = money(payload.get("opening_balance", 0))
        income = sum((money(r["amount"]) for r in candidate_rows if "income" in r["tags"]), Decimal(0))
        expenses = sum((money(r["amount"]) for r in candidate_rows if "expense" in r["tags"]), Decimal(0))
        calculated = opening + income - expenses
        reported = payload.get("reported_closing_balance")
        require(reported is not None, "INVALID_SCHEMA", "reported_closing_balance is required")
        difference = calculated - money(reported)
        require(difference == 0, "FINANCIAL_RECONCILIATION_FAILED", "Opening + income - expenses does not equal reported closing", {"calculated_closing": number(calculated), "reported_closing": number(money(reported)), "difference": number(difference)})
        prior_periods = [candidate for candidate in index if candidate["start_date"] < period["start_date"]]
        prior = max(prior_periods, key=lambda candidate: (candidate["start_date"], candidate["end_date"])) if prior_periods else None
        for prior in ([prior] if prior else []):
            prior_rows = [r for r in current["transactions"] if r.get("source_file") == Path(prior["file"]).name]
            prior_close = self._aggregate(prior_rows)["closing"]
            if opening != money(prior_close):
                raise CeqwaError("PERIOD_CONTINUITY_FAILED", "Opening balance does not equal previous closing balance", {"previous_closing": prior_close, "opening_balance": number(opening)})
        effect = {"transactions_added": len(candidate_rows), "transactions_modified": 0, "transactions_removed": 0,
                  "opening_balance": number(opening), "income": number(income), "expenses": number(expenses),
                  "calculated_closing": number(calculated), "reported_closing": number(money(reported)), "difference": number(difference),
                  "capex": number(sum((money(r["amount"]) for r in candidate_rows if r["accounting_class"] == "capex"), Decimal(0))),
                  "opex": number(sum((money(r["amount"]) for r in candidate_rows if r["accounting_class"] == "opex"), Decimal(0)))}
        return period, candidate_rows, effect, possible

    @staticmethod
    def _candidate_id(period_id: str, item: dict) -> str:
        seed = f"{period_id}|{item.get('date')}|{item.get('description')}|{item.get('amount')}|{item.get('flow')}"
        return f"{period_id}-{hashlib.sha256(seed.encode()).hexdigest()[:8]}"

    def propose_import(self, payload: dict) -> dict:
        period, rows, effect, possible = self._validate_input(payload)
        source = payload["source_document"]
        filename = Path(source).name
        destination = f"financials/{filename}"
        markdown = f"financials/{Path(filename).stem}.md"
        summary = (f"Import {period['display_label']} with {len(rows)} transactions. "
                   f"Opening ₹{effect['opening_balance']}; income ₹{effect['income']}; expenses ₹{effect['expenses']}; "
                   f"closing ₹{effect['calculated_closing']}. Reconciliation PASS.")
        proposal_payload = {"kind": "financial_import", "source_document": source, "destination": destination,
                            "markdown_destination": markdown, "period": period, "transactions": rows,
                            "reported_closing_balance": payload["reported_closing_balance"]}
        return proposal_payload, effect, possible, summary

    def execute_import(self, payload: dict) -> dict:
        # Re-validate at execution time, then apply the complete batch under rollback.
        extracted_rows = []
        for row in payload["transactions"]:
            extracted_rows.append({"transaction_id": row.get("transaction_id"), "date": row.get("date"),
                "description": row["raw_description"], "amount": row["amount"],
                "flow": next((flow for flow in ("income", "expense", "opening_balance") if flow in row.get("tags", [])), ""),
                "category": row.get("raw_category"), "accounting_class": row["accounting_class"],
                "recurrence": row["recurrence"], "tags": row.get("tags", []),
                "tag_confidence": row.get("tag_confidence", "medium")})
        input_payload = {"source_document": payload["source_document"], "period": payload["period"],
                         "transactions": extracted_rows, "opening_balance": next((r["amount"] for r in payload["transactions"] if "opening_balance" in r["tags"]), 0),
                         "reported_closing_balance": payload["reported_closing_balance"]}
        self._validate_input(input_payload)
        affected = ["data/finances/finances.json", "data/metadata.json", "data/financials-dashboard.json",
                    payload["destination"], payload["markdown_destination"]]
        with self.repo.mutation(affected):
            self.repo.copy_incoming(payload["source_document"], payload["destination"])
            raw = self._raw()
            raw["transactions"].extend(copy.deepcopy(payload["transactions"]))
            self.repo.write_json("data/finances/finances.json", raw)
            metadata = self.repo.load_metadata(); index = ordered_financials(metadata["financials"])
            period = payload["period"]
            opening_amount = sum((money(r["amount"]) for r in payload["transactions"] if "opening_balance" in r["tags"]), Decimal(0))
            income_amount = sum((money(r["amount"]) for r in payload["transactions"] if "income" in r["tags"]), Decimal(0))
            entry = {"description": period.get("description", f"Sources and Uses of Funds Statement - {period['display_label']}"),
                     "period": period.get("period", period["display_label"]), "period_id": period["period_id"],
                     "period_label": period["display_label"], "source_label": period.get("source_label", period["display_label"]),
                     "period_type": period["period_type"], "start_date": period["start_date"], "end_date": period["end_date"],
                     "amount": f"Rs. {number(opening_amount + income_amount):,}",
                     "file": payload["destination"], "markdown": payload["markdown_destination"]}
            for field in ("allowed_out_of_period_dates", "period_note"):
                if field in period:
                    entry[field] = period[field]
            metadata["financials"] = ordered_financials(index + [entry])
            self.repo.write_json("data/metadata.json", metadata)
            self.repo.write_json("data/financials-dashboard.json", self.rebuild_dashboard(raw, metadata["financials"]))
            self.repo.atomic_write(payload["markdown_destination"], self.markdown_for(entry, payload["transactions"], payload["reported_closing_balance"]))
            require_valid(run_financial_validation(self.repo.root))
            require_valid(run_site_validation(self.repo.root))
        return {"operation": "financial_import", "files_changed": affected,
                "financial_validation": "pass", "site_validation": "pass"}

    def markdown_for(self, period: dict, rows: list[dict], closing: object) -> str:
        income = sum((money(r["amount"]) for r in rows if "income" in r["tags"]), Decimal(0))
        expenses = sum((money(r["amount"]) for r in rows if "expense" in r["tags"]), Decimal(0))
        opening = sum((money(r["amount"]) for r in rows if "opening_balance" in r["tags"]), Decimal(0))
        lines = ["---", f"title: {period['period_label']}", f"period_id: {period['period_id']}", f"total_income: {number(opening + income)}", f"total_expenses: {number(expenses)}", f"closing_balance: {number(money(closing))}", "---", "", f"# {period['period_label']}", "", "| Date | Description | Amount | Flow | Classification |", "| --- | --- | ---: | --- | --- |"]
        for row in rows:
            lines.append(f"| {row.get('date') or 'Unknown'} | {row['raw_description']} | {row['amount']} | {next((x for x in ('income', 'expense', 'opening_balance') if x in row['tags']), '')} | {row['accounting_class']} |")
        return "\n".join(lines) + "\n"

    def rebuild_dashboard(self, raw: dict | None = None, index: list[dict] | None = None) -> dict:
        raw = raw or self._raw(); index = index or self._index()
        series = {"periods": [], "period_labels": [], "period_types": [], "income_recurring": [], "income_one_off": [], "expense_recurring": [], "expense_one_off": [], "expense_capex": [], "expense_opex": [], "closing_balance": []}
        recurring_breakdown, oneoff_breakdown = defaultdict(Decimal), defaultdict(Decimal)
        for entry in index:
            rows = [r for r in raw["transactions"] if r.get("source_file") == Path(entry["file"]).name]
            agg = self._aggregate(rows)
            series["periods"].append(entry["period"]); series["period_labels"].append(entry["period_label"]); series["period_types"].append(entry["period_type"])
            for key, predicate in {"income_recurring": lambda r: "income" in r["tags"] and r["recurrence"] == "recurring", "income_one_off": lambda r: "income" in r["tags"] and r["recurrence"] == "one_off", "expense_recurring": lambda r: "expense" in r["tags"] and r["recurrence"] == "recurring", "expense_one_off": lambda r: "expense" in r["tags"] and r["recurrence"] == "one_off", "expense_capex": lambda r: r["accounting_class"] == "capex", "expense_opex": lambda r: r["accounting_class"] == "opex"}.items():
                series[key].append(number(sum((money(r["amount"]) for r in rows if predicate(r)), Decimal(0))))
            series["closing_balance"].append(agg["closing"])
            for r in rows:
                if "expense" in r["tags"]:
                    (recurring_breakdown if r["recurrence"] == "recurring" else oneoff_breakdown)[r.get("raw_category", "Other")] += money(r["amount"])
        series["expense_recurring_breakdown"] = [{"category": k, "amount": number(v), "tags": ["expense", "recurring"]} for k, v in sorted(recurring_breakdown.items())]
        series["expense_one_off_breakdown"] = [{"category": k, "amount": number(v), "tags": ["expense", "one_off"]} for k, v in sorted(oneoff_breakdown.items())]
        return series

    def propose_update(self, transaction_id: str, changes: dict) -> tuple[dict, str]:
        raw = self._raw(); rows = raw["transactions"]
        row = next((r for r in rows if r.get("transaction_id") == transaction_id), None)
        require(row is not None, "UNKNOWN_TRANSACTION", f"Unknown transaction: {transaction_id}")
        before = copy.deepcopy(row); after = copy.deepcopy(row); after.update(changes)
        require(after.get("amount", 0) >= 0, "INVALID_SCHEMA", "Amount cannot be negative")
        if after.get("date") is not None:
            date.fromisoformat(after["date"])
        return {"kind": "transaction_update", "transaction_id": transaction_id, "before": before, "after": after}, f"Update transaction {transaction_id}: ₹{before['amount']} → ₹{after['amount']}"

    def execute_update(self, payload: dict) -> dict:
        raw = self._raw(); row = next((r for r in raw["transactions"] if r["transaction_id"] == payload["transaction_id"]), None)
        require(row is not None, "UNKNOWN_TRANSACTION", "Transaction no longer exists")
        affected = ["data/finances/finances.json", "data/financials-dashboard.json"]
        with self.repo.mutation(affected):
            row.clear(); row.update(copy.deepcopy(payload["after"]))
            self.repo.write_json("data/finances/finances.json", raw)
            self.repo.write_json("data/financials-dashboard.json", self.rebuild_dashboard(raw, self._index()))
            require_valid(run_financial_validation(self.repo.root))
        return {"operation": "transaction_update", "files_changed": affected, "financial_validation": "pass"}

    def propose_delete(self, transaction_id: str) -> tuple[dict, str]:
        raw = self._raw(); row = next((r for r in raw["transactions"] if r["transaction_id"] == transaction_id), None)
        require(row is not None, "UNKNOWN_TRANSACTION", f"Unknown transaction: {transaction_id}")
        return {"kind": "transaction_delete", "transaction_id": transaction_id, "before": copy.deepcopy(row)}, f"Delete transaction {transaction_id} ({row['raw_description']}, ₹{row['amount']})"

    def execute_delete(self, payload: dict) -> dict:
        raw = self._raw(); before = len(raw["transactions"]); raw["transactions"] = [r for r in raw["transactions"] if r["transaction_id"] != payload["transaction_id"]]
        require(len(raw["transactions"]) == before - 1, "UNKNOWN_TRANSACTION", "Transaction no longer exists")
        affected = ["data/finances/finances.json", "data/financials-dashboard.json"]
        with self.repo.mutation(affected):
            self.repo.write_json("data/finances/finances.json", raw); self.repo.write_json("data/financials-dashboard.json", self.rebuild_dashboard(raw, self._index())); require_valid(run_financial_validation(self.repo.root))
        return {"operation": "transaction_delete", "files_changed": affected, "financial_validation": "pass"}
