"""Validate the published financial data and dashboard aggregates."""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TOLERANCE = 0.01


def load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"{path}: {error}")


def fail(message):
    ERRORS.append(message)


def close(left, right):
    return abs(float(left) - float(right)) <= TOLERANCE


def parse_amount(value):
    if isinstance(value, (int, float)):
        return float(value)
    matches = re.findall(r"\d[\d,]*(?:\.\d+)?", str(value))
    if not matches:
        raise ValueError(f"invalid amount: {value}")
    return float(matches[-1].replace(",", ""))


def front_matter(path):
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not match:
        fail(f"{path}: missing YAML front matter")
        return {}
    values = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip().strip('"')
        try:
            values[key.strip()] = float(value) if re.fullmatch(r"\d+(?:\.\d+)?", value) else value
        except ValueError:
            values[key.strip()] = value
    return values


def main():
    financials = load_json(ROOT / "data" / "financials.json")
    dashboard = load_json(ROOT / "data" / "financials-dashboard.json")
    raw = load_json(ROOT / "data" / "finances" / "finances.json")
    rows = raw.get("transactions", [])
    allowed_tags = {tag for tags in raw.get("tagging_system", {}).get("tag_groups", {}).values() for tag in tags}
    by_source = defaultdict(list)
    for row in rows:
        source = row.get("source_file")
        by_source[source].append(row)
        if not source or not row.get("raw_category") or not row.get("raw_description"):
            fail(f"transaction has missing source/category/description: {row}")
        if not isinstance(row.get("amount"), (int, float)) or row["amount"] < 0:
            fail(f"{source}: invalid transaction amount")
        if not row.get("tags"):
            fail(f"{source}: transaction has no tags")
        unknown = set(row.get("tags", [])) - allowed_tags
        if unknown:
            fail(f"{source}: unknown tags: {sorted(unknown)}")

    periods = dashboard.get("periods", [])
    array_names = ["income_recurring", "income_one_off", "expense_recurring", "expense_one_off", "closing_balance"]
    for name in array_names:
        if len(dashboard.get(name, [])) != len(periods):
            fail(f"dashboard {name} length does not match periods")

    dashboard_by_period = {period: index for index, period in enumerate(periods)}
    for entry in financials:
        pdf = ROOT / entry.get("file", "")
        markdown = ROOT / entry.get("markdown", "")
        if not pdf.is_file():
            fail(f"missing PDF: {entry.get('file')}")
        if not markdown.is_file():
            fail(f"missing Markdown companion: {entry.get('markdown')}")
        period = entry.get("period")
        if period not in dashboard_by_period:
            fail(f"{entry.get('file')}: period is missing from dashboard")
            continue
        source = Path(entry.get("file", "")).name
        source_rows = by_source.get(source, [])
        index = dashboard_by_period[period]
        income = sum(row["amount"] for row in source_rows if "income" in row.get("tags", []))
        expenses = sum(row["amount"] for row in source_rows if "expense" in row.get("tags", []))
        opening = sum(row["amount"] for row in source_rows if "opening_balance" in row.get("tags", []))
        recurring_income = sum(row["amount"] for row in source_rows if "income" in row.get("tags", []) and row.get("recurrence") == "recurring")
        one_off_income = sum(row["amount"] for row in source_rows if "income" in row.get("tags", []) and row.get("recurrence") == "one_off")
        recurring_expenses = sum(row["amount"] for row in source_rows if "expense" in row.get("tags", []) and row.get("recurrence") == "recurring")
        one_off_expenses = sum(row["amount"] for row in source_rows if "expense" in row.get("tags", []) and row.get("recurrence") == "one_off")
        expected = {
            "income_recurring": recurring_income,
            "income_one_off": one_off_income,
            "expense_recurring": recurring_expenses,
            "expense_one_off": one_off_expenses,
            "closing_balance": opening + income - expenses,
        }
        for name, value in expected.items():
            if not close(dashboard[name][index], value):
                fail(f"{period}: dashboard {name}={dashboard[name][index]} but raw data gives {value}")
        if not close(parse_amount(entry.get("amount", "0")), opening + income):
            fail(f"{period}: financials.json amount does not match opening balance plus income")
        metadata = front_matter(markdown)
        metadata_expected = {"total_income": opening + income, "total_expenses": expenses, "closing_balance": opening + income - expenses}
        for name, value in metadata_expected.items():
            if not close(metadata.get(name, -1), value):
                fail(f"{markdown}: {name} does not match raw data")

    recurring_breakdown = sum(item.get("amount", 0) for item in dashboard.get("expense_recurring_breakdown", []))
    one_off_breakdown = sum(item.get("amount", 0) for item in dashboard.get("expense_one_off_breakdown", []))
    if not close(recurring_breakdown, sum(dashboard.get("expense_recurring", []))):
        fail("recurring expense breakdown does not match dashboard series")
    if not close(one_off_breakdown, sum(dashboard.get("expense_one_off", []))):
        fail("one-off expense breakdown does not match dashboard series")

    if ERRORS:
        print("Financial validation failed:")
        for error in ERRORS:
            print(f"- {error}")
        return 1
    print(f"Financial validation passed: {len(financials)} periods, {len(rows)} transactions")
    return 0


ERRORS = []
if __name__ == "__main__":
    sys.exit(main())
