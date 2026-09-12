"""Exercise the financial validator with non-destructive malformed fixtures."""

import copy
import json
import shutil
import tempfile
from pathlib import Path

import validate_finances


ROOT = Path(__file__).resolve().parent.parent


def expect_failure(name, mutate):
    with tempfile.TemporaryDirectory(prefix="ceqwa-finance-test-") as directory:
        fixture = Path(directory) / "site"
        shutil.copytree(ROOT, fixture, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        path = fixture / "data" / "finances" / "finances.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        mutate(payload)
        path.write_text(json.dumps(payload), encoding="utf-8")
        if validate_finances.main(fixture) == 0:
            raise AssertionError(f"fixture should fail: {name}")


def main():
    expect_failure("duplicate transaction ID", lambda data: data["transactions"].__setitem__(1, copy.deepcopy(data["transactions"][0])))
    expect_failure("missing transaction ID", lambda data: data["transactions"][0].pop("transaction_id"))
    expect_failure("invalid date", lambda data: data["transactions"][0].__setitem__("date", "2026-99-99"))
    expect_failure("opening balance marked recurring", lambda data: data["transactions"][0].__setitem__("recurrence", "recurring"))
    expect_failure("changed amount", lambda data: data["transactions"][2].__setitem__("amount", 4901))
    print("Financial fixture tests passed: malformed data is rejected")


if __name__ == "__main__":
    main()
