"""Validation and deterministic ordering for canonical site metadata."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from ..errors import CeqwaError


DOCUMENT_FIELDS = {"title", "category", "date", "file", "markdown"}
DOCUMENT_REQUIRED = {"title", "category", "date", "file"}
FINANCIAL_FIELDS = {
    "description", "period", "period_id", "period_label", "source_label",
    "period_type", "start_date", "end_date", "amount", "file", "markdown",
    "allowed_out_of_period_dates", "period_note",
}
FINANCIAL_REQUIRED = {
    "description", "period", "period_id", "period_label", "source_label",
    "period_type", "start_date", "end_date", "amount", "file", "markdown",
}
TOP_LEVEL_FIELDS = {"documents", "financials"}


def _relative_path(root: Path | None, value: object, label: str, errors: list[str], *, required: bool = True) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        if required:
            errors.append(f"{label} must be a non-empty relative path")
        return None
    raw = value.strip()
    if raw.startswith(("/", "\\")) or (len(raw) > 1 and raw[1] == ":") or "\\" in raw:
        errors.append(f"{label} must be a relative site path")
        return None
    path = Path(raw)
    if any(part == ".." for part in path.parts):
        errors.append(f"{label} must not contain parent traversal")
        return None
    if root is None:
        return path
    resolved = (root / path).resolve(strict=False)
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        errors.append(f"{label} escapes the repository")
        return None
    return resolved


def _unknown_fields(entry: dict, allowed: set[str], label: str, errors: list[str]) -> None:
    unknown = sorted(set(entry) - allowed)
    if unknown:
        errors.append(f"{label} contains unknown fields: {', '.join(unknown)}")


def _path_key(value: str) -> str:
    return Path(value).as_posix()


def _non_empty_string(entry: dict, field: str, label: str, errors: list[str]) -> None:
    if not isinstance(entry.get(field), str) or not entry[field].strip():
        errors.append(f"{label}.{field} must be a non-empty string")


def _document_errors(entry: object, index: int, root: Path | None) -> list[str]:
    errors: list[str] = []
    label = f"documents[{index}]"
    if not isinstance(entry, dict):
        return [f"{label} must be an object"]
    _unknown_fields(entry, DOCUMENT_FIELDS, label, errors)
    missing = sorted(DOCUMENT_REQUIRED - set(entry))
    if missing:
        errors.append(f"{label} is missing required fields: {', '.join(missing)}")
    for field in ("title", "category"):
        _non_empty_string(entry, field, label, errors)
    if entry.get("date") is not None and not isinstance(entry.get("date"), str):
        errors.append(f"{label}.date must be a string or null")
    document_path = _relative_path(root, entry.get("file"), f"{label}.file", errors)
    if document_path is not None and root is not None and not document_path.is_file():
        errors.append(f"{label}.file does not exist: {entry.get('file')}")
    if "markdown" in entry:
        markdown_path = _relative_path(root, entry.get("markdown"), f"{label}.markdown", errors)
        if markdown_path is not None and root is not None and not markdown_path.is_file():
            errors.append(f"{label}.markdown does not exist: {entry.get('markdown')}")
    return errors


def _financial_errors(entry: object, index: int, root: Path | None) -> list[str]:
    errors: list[str] = []
    label = f"financials[{index}]"
    if not isinstance(entry, dict):
        return [f"{label} must be an object"]
    _unknown_fields(entry, FINANCIAL_FIELDS, label, errors)
    missing = sorted(FINANCIAL_REQUIRED - set(entry))
    if missing:
        errors.append(f"{label} is missing required fields: {', '.join(missing)}")
    for field in ("description", "period", "period_id", "period_label", "source_label", "period_type"):
        _non_empty_string(entry, field, label, errors)
    for field in ("start_date", "end_date"):
        value = entry.get(field)
        if not isinstance(value, str):
            errors.append(f"{label}.{field} must be an ISO date")
        else:
            try:
                date.fromisoformat(value)
            except ValueError:
                errors.append(f"{label}.{field} must be an ISO date")
    try:
        if isinstance(entry.get("start_date"), str) and isinstance(entry.get("end_date"), str):
            if date.fromisoformat(entry["start_date"]) > date.fromisoformat(entry["end_date"]):
                errors.append(f"{label} starts after it ends")
    except ValueError:
        pass
    amount = entry.get("amount")
    if isinstance(amount, bool) or not isinstance(amount, (str, int, float)) or (isinstance(amount, str) and not amount.strip()):
        errors.append(f"{label}.amount must be a non-empty string or number")
    for field in ("file", "markdown"):
        path = _relative_path(root, entry.get(field), f"{label}.{field}", errors)
        if path is not None and root is not None and not path.is_file():
            errors.append(f"{label}.{field} does not exist: {entry.get(field)}")
    allowed_dates = entry.get("allowed_out_of_period_dates", [])
    if not isinstance(allowed_dates, list) or any(not isinstance(value, str) for value in allowed_dates):
        errors.append(f"{label}.allowed_out_of_period_dates must be an array of ISO dates")
    else:
        for value in allowed_dates:
            try:
                date.fromisoformat(value)
            except ValueError:
                errors.append(f"{label}.allowed_out_of_period_dates contains an invalid ISO date: {value}")
    if "period_note" in entry and not isinstance(entry["period_note"], str):
        errors.append(f"{label}.period_note must be a string")
    return errors


def metadata_errors(metadata: object, root: Path | None = None) -> list[str]:
    """Return all canonical metadata errors without leaking implementation exceptions."""
    errors: list[str] = []
    if not isinstance(metadata, dict):
        return ["metadata.json must be an object"]
    unknown = sorted(set(metadata) - TOP_LEVEL_FIELDS)
    if unknown:
        errors.append(f"metadata.json contains unknown fields: {', '.join(unknown)}")
    for key in TOP_LEVEL_FIELDS:
        if key not in metadata:
            errors.append(f"metadata.json.{key} is required")
        elif not isinstance(metadata[key], list):
            errors.append(f"metadata.json.{key} must be an array")

    documents = metadata.get("documents") if isinstance(metadata.get("documents"), list) else []
    document_files: set[str] = set()
    for index, entry in enumerate(documents):
        errors.extend(_document_errors(entry, index, root))
        if isinstance(entry, dict) and isinstance(entry.get("file"), str):
            key = _path_key(entry["file"])
            if key in document_files:
                errors.append(f"duplicate document file: {entry['file']}")
            document_files.add(key)

    financials = metadata.get("financials") if isinstance(metadata.get("financials"), list) else []
    seen_ids: set[str] = set()
    seen_periods: set[str] = set()
    financial_files: set[str] = set()
    for index, entry in enumerate(financials):
        errors.extend(_financial_errors(entry, index, root))
        if not isinstance(entry, dict):
            continue
        for field, seen, label in (("period_id", seen_ids, "period_id"), ("period", seen_periods, "period"), ("file", financial_files, "source file")):
            value = entry.get(field)
            if isinstance(value, str):
                key = _path_key(value) if field == "file" else value
                if key in seen:
                    errors.append(f"duplicate financial {label}: {value}")
                seen.add(key)
    return errors


def validate_metadata(metadata: object, root: Path | None = None) -> dict:
    errors = metadata_errors(metadata, root)
    if errors:
        raise CeqwaError("INVALID_SCHEMA", "Invalid canonical metadata", {"errors": errors})
    return metadata  # type: ignore[return-value]


def ordered_financials(financials: list[dict]) -> list[dict]:
    """Sort valid periods chronologically with deterministic tie-breakers."""
    return sorted(financials, key=lambda item: (item["start_date"], item["end_date"], item["period_id"], item["file"]))
