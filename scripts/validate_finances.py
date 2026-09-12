"""Validate the canonical financial data and all published aggregates."""

import json
import re
import sys
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ops.services.metadata import metadata_errors, ordered_financials

ERRORS = []
ALLOWED_RECURRENCE = {"recurring", "one_off", "not_applicable"}
ALLOWED_CLASS = {"income", "opex", "capex", "opening_balance"}
FLOW_TAGS = {"income", "expense", "opening_balance", "closing_balance", "transfer"}
TOLERANCE = Decimal("0.01")


def fail(message):
    ERRORS.append(message)


def load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"{path}: {error}")
        return None


def money(value):
    try:
        if isinstance(value, bool):
            raise InvalidOperation
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"invalid amount: {value}")


def close(left, right):
    try:
        return abs(money(left) - money(right)) <= TOLERANCE
    except ValueError:
        return False


def parse_amount(value):
    matches = re.findall(r"\d[\d,]*(?:\.\d+)?", str(value))
    if not matches:
        raise ValueError(f"invalid amount: {value}")
    return money(matches[-1].replace(",", ""))


def front_matter(path):
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        fail(f"{path}: {error}")
        return {}
    match = re.match(r"\A---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not match:
        fail(f"{path}: missing YAML front matter")
        return {}
    values = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip('"')
    return values


def valid_iso(value, label):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        fail(f"{label}: invalid ISO date {value!r}")
        return None


def main(root=ROOT):
    ERRORS.clear()
    metadata = load_json(root / "data" / "metadata.json")
    metadata_validation_errors = metadata_errors(metadata, root)
    for error in metadata_validation_errors:
        fail(error)
    if not metadata_validation_errors and isinstance(metadata, dict) and isinstance(metadata.get("financials"), list) and all(
        isinstance(entry, dict) and all(field in entry for field in ("start_date", "end_date", "period_id", "file"))
        for entry in metadata["financials"]
    ):
        financials = ordered_financials(metadata["financials"])
    else:
        financials = []
    dashboard = load_json(root / "data" / "financials-dashboard.json")
    if not isinstance(dashboard, dict):
        fail("financials-dashboard.json must be an object")
        dashboard = {}
    raw = load_json(root / "data" / "finances" / "finances.json")
    if not isinstance(raw, dict):
        fail("canonical transactions must be an object")
        raw = {}
    rows = raw.get("transactions", [])
    if not isinstance(rows, list):
        fail("canonical transactions must be an array")
        rows = []

    allowed_tags = {
        tag for tags in raw.get("tagging_system", {}).get("tag_groups", {}).values()
        for tag in tags
    }
    by_source = defaultdict(list)
    ids = set()
    for row in rows:
        source = row.get("source_file")
        by_source[source].append(row)
        transaction_id = row.get("transaction_id")
        if not transaction_id:
            fail(f"{source}: transaction is missing transaction_id")
        elif transaction_id in ids:
            fail(f"duplicate transaction_id: {transaction_id}")
        else:
            ids.add(transaction_id)
        if not source or not row.get("raw_category") or not row.get("raw_description"):
            fail(f"transaction has missing source/category/description: {row}")
        try:
            amount = money(row.get("amount"))
            if amount < 0:
                raise ValueError
        except ValueError:
            fail(f"{source}: invalid transaction amount")
        tags = set(row.get("tags", []))
        if not tags:
            fail(f"{source}: transaction has no tags")
        unknown = tags - allowed_tags
        if unknown:
            fail(f"{source}: unknown tags: {sorted(unknown)}")
        flow = tags & FLOW_TAGS
        if len(flow) != 1:
            fail(f"{source}: transaction must have exactly one flow tag: {sorted(flow)}")
        recurrence = row.get("recurrence")
        if recurrence not in ALLOWED_RECURRENCE:
            fail(f"{source}: invalid recurrence {recurrence!r}")
        accounting_class = row.get("accounting_class")
        if accounting_class not in ALLOWED_CLASS:
            fail(f"{source}: invalid accounting_class {accounting_class!r}")
        if "opening_balance" in tags and recurrence == "recurring":
            fail(f"{source}: opening balance cannot be recurring")
        if "opening_balance" in tags and accounting_class != "opening_balance":
            fail(f"{source}: opening balance has wrong accounting_class")
        if "income" in tags and accounting_class != "income":
            fail(f"{source}: income has wrong accounting_class")
        if "expense" in tags and accounting_class not in {"opex", "capex"}:
            fail(f"{source}: expense has wrong accounting_class")
        if row.get("date") is not None:
            valid_iso(row.get("date"), f"{transaction_id or source}")

    periods = dashboard.get("periods", [])
    labels = dashboard.get("period_labels", [])
    if len(set(periods)) != len(periods):
        fail("dashboard periods must be unique")
    if len(labels) != len(periods):
        fail("dashboard period_labels length does not match periods")
    if len(dashboard.get("period_types", [])) != len(periods):
        fail("dashboard period_types length does not match periods")
    array_names = [
        "income_recurring", "income_one_off", "expense_recurring",
        "expense_one_off", "expense_capex", "expense_opex", "closing_balance",
    ]
    for name in array_names:
        if len(dashboard.get(name, [])) != len(periods):
            fail(f"dashboard {name} length does not match periods")

    entries_by_period = {}
    for entry in financials:
        period = entry.get("period")
        if period in entries_by_period:
            fail(f"duplicate financial period: {period}")
        entries_by_period[period] = entry
        if not entry.get("period_id") or not entry.get("period_label"):
            fail(f"{entry.get('file')}: missing period metadata")
        start = valid_iso(entry.get("start_date"), f"{entry.get('file')} start_date")
        end = valid_iso(entry.get("end_date"), f"{entry.get('file')} end_date")
        if start and end and start > end:
            fail(f"{entry.get('file')}: period starts after it ends")
        pdf = root / entry.get("file", "")
        markdown = root / entry.get("markdown", "")
        if not pdf.is_file():
            fail(f"missing PDF: {entry.get('file')}")
        if not markdown.is_file():
            fail(f"missing Markdown companion: {entry.get('markdown')}")
        if period not in periods:
            fail(f"{entry.get('file')}: period is missing from dashboard")
            continue
        index = periods.index(period)
        if labels[index] != entry.get("period_label"):
            fail(f"{period}: dashboard label does not match metadata.json financials")
        source = Path(entry.get("file", "")).name
        source_rows = by_source.get(source, [])
        income = sum((money(row["amount"]) for row in source_rows if "income" in row.get("tags", [])), Decimal(0))
        expenses = sum((money(row["amount"]) for row in source_rows if "expense" in row.get("tags", [])), Decimal(0))
        opening = sum((money(row["amount"]) for row in source_rows if "opening_balance" in row.get("tags", [])), Decimal(0))
        recurring_income = sum((money(row["amount"]) for row in source_rows if "income" in row.get("tags", []) and row.get("recurrence") == "recurring"), Decimal(0))
        one_off_income = sum((money(row["amount"]) for row in source_rows if "income" in row.get("tags", []) and row.get("recurrence") == "one_off"), Decimal(0))
        recurring_expenses = sum((money(row["amount"]) for row in source_rows if "expense" in row.get("tags", []) and row.get("recurrence") == "recurring"), Decimal(0))
        one_off_expenses = sum((money(row["amount"]) for row in source_rows if "expense" in row.get("tags", []) and row.get("recurrence") == "one_off"), Decimal(0))
        capex = sum((money(row["amount"]) for row in source_rows if row.get("accounting_class") == "capex"), Decimal(0))
        opex = sum((money(row["amount"]) for row in source_rows if row.get("accounting_class") == "opex"), Decimal(0))
        expected = {
            "income_recurring": recurring_income,
            "income_one_off": one_off_income,
            "expense_recurring": recurring_expenses,
            "expense_one_off": one_off_expenses,
            "expense_capex": capex,
            "expense_opex": opex,
            "closing_balance": opening + income - expenses,
        }
        for name, value in expected.items():
            if not close(dashboard[name][index], value):
                fail(f"{period}: dashboard {name}={dashboard[name][index]} but raw data gives {value}")
        try:
            if not close(parse_amount(entry.get("amount", "0")), opening + income):
                fail(f"{period}: metadata.json financials amount does not match opening balance plus income")
        except ValueError as error:
            fail(f"{period}: {error}")
        frontmatter = front_matter(markdown)
        metadata_expected = {
            "total_income": opening + income,
            "total_expenses": expenses,
            "closing_balance": opening + income - expenses,
        }
        for name, value in metadata_expected.items():
            if not close(frontmatter.get(name), value):
                fail(f"{markdown}: {name} does not match raw data")
        period_start = start
        period_end = end
        if period_start and period_end:
            for row in source_rows:
                if row.get("date") and "opening_balance" not in row.get("tags", []):
                    try:
                        transaction_date = date.fromisoformat(row["date"])
                    except ValueError:
                        continue
                    allowed_dates = set(entry.get("allowed_out_of_period_dates", []))
                    if not period_start <= transaction_date <= period_end and row["date"] not in allowed_dates:
                        fail(f"{source}: {row['transaction_id']} date is outside declared period")

    for previous, current in zip(financials, financials[1:]):
        previous_close = dashboard["closing_balance"][periods.index(previous["period"])]
        current_open = sum((money(row["amount"]) for row in by_source.get(Path(current.get("file", "")).name, []) if "opening_balance" in row.get("tags", [])), Decimal(0))
        if not close(previous_close, current_open):
            fail(f"{current.get('period')}: opening balance does not equal previous closing balance")

    recurring_breakdown = sum((money(item.get("amount", 0)) for item in dashboard.get("expense_recurring_breakdown", [])), Decimal(0))
    one_off_breakdown = sum((money(item.get("amount", 0)) for item in dashboard.get("expense_one_off_breakdown", [])), Decimal(0))
    if not close(recurring_breakdown, sum((money(x) for x in dashboard.get("expense_recurring", [])), Decimal(0))):
        fail("recurring expense breakdown does not match dashboard series")
    if not close(one_off_breakdown, sum((money(x) for x in dashboard.get("expense_one_off", [])), Decimal(0))):
        fail("one-off expense breakdown does not match dashboard series")
    if not close(sum((money(x) for x in dashboard.get("expense_capex", [])), Decimal(0)), sum((money(row["amount"]) for row in rows if row.get("accounting_class") == "capex"), Decimal(0))):
        fail("CAPEX dashboard total does not match canonical transactions")

    if ERRORS:
        print("Financial validation failed:")
        for error in ERRORS:
            print(f"- {error}")
        return 1
    print(f"Financial validation passed: {len(financials)} periods, {len(rows)} transactions")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT))
