"""Reusable adapters around the repository's existing validators."""

from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

from ..errors import CeqwaError


def _load_validator(root: Path, name: str):
    scripts = str(root / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    module = __import__(name)
    return module


def run_financial_validation(root: Path) -> dict:
    module = _load_validator(root, "validate_finances")
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = module.main(root)
    return {"status": "pass" if code == 0 else "fail", "exit_code": code, "output": output.getvalue().strip()}


def run_site_validation(root: Path) -> dict:
    module = _load_validator(root, "validate_site")
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = module.main(root)
    return {"status": "pass" if code == 0 else "fail", "exit_code": code, "output": output.getvalue().strip()}


def require_valid(result: dict, code: str = "VALIDATION_FAILED") -> None:
    if result.get("status") != "pass":
        raise CeqwaError(code, "Repository validation failed", result)
