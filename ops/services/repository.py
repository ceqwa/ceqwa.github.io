"""Repository confinement, atomic writes, snapshots, and local audit logging."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from ..config import Settings
from ..errors import CeqwaError, require
from .metadata import validate_metadata


class Repository:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
        self.settings.ensure_runtime()

    @property
    def root(self) -> Path:
        return self.settings.repo_root

    def resolve_repo_path(self, path: str | Path, *, allow_incoming: bool = False) -> Path:
        """Resolve a user path while rejecting traversal, absolute, and symlink escapes."""
        raw = str(path)
        supplied = Path(raw)
        if supplied.is_absolute() or supplied.drive or raw.startswith(("\\\\", "/")):
            raise CeqwaError("INVALID_PATH", "Absolute and UNC paths are not allowed", {"path": raw})
        roots = [self.root]
        if allow_incoming:
            self.settings.incoming_root.mkdir(parents=True, exist_ok=True)
            roots.append(self.settings.incoming_root)
        # Check lexical traversal before resolving so the error is deterministic.
        if any(part == ".." for part in supplied.parts):
            raise CeqwaError("INVALID_PATH", "Parent traversal is not allowed", {"path": raw})
        candidates = []
        if allow_incoming and supplied.parts and supplied.parts[0].lower() == "incoming":
            candidates.append((self.settings.incoming_root / Path(*supplied.parts[1:])).resolve(strict=False))
        candidates.append((self.root / supplied).resolve(strict=False))
        for resolved in candidates:
            for root in roots:
                try:
                    resolved.relative_to(root.resolve())
                    return resolved
                except ValueError:
                    continue
        raise CeqwaError("INVALID_PATH", "Path escapes the configured repository roots", {"path": raw})

    def load_json(self, path: str | Path) -> object:
        target = self.resolve_repo_path(path)
        try:
            return json.loads(target.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise CeqwaError("FILE_NOT_FOUND", f"File does not exist: {path}") from exc
        except json.JSONDecodeError as exc:
            raise CeqwaError("INVALID_SCHEMA", f"Invalid JSON in {path}", {"line": exc.lineno}) from exc

    def load_metadata(self) -> dict:
        metadata = self.load_json("data/metadata.json")
        return validate_metadata(metadata, self.root)

    def atomic_write(self, path: str | Path, content: str | bytes) -> None:
        target = self.resolve_repo_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        data = content.encode("utf-8") if isinstance(content, str) else content
        fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=str(target.parent))
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, target)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    def write_json(self, path: str | Path, value: object) -> None:
        self.atomic_write(path, json.dumps(value, indent=2, ensure_ascii=False) + "\n")

    def copy_incoming(self, source: str, destination: str) -> None:
        source_path = self.resolve_repo_path(source, allow_incoming=True)
        destination_path = self.resolve_repo_path(destination)
        require(source_path.is_file(), "FILE_NOT_FOUND", f"Source file does not exist: {source}")
        if source_path == destination_path:
            return
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, destination_path)

    @contextmanager
    def mutation(self, paths: Iterable[str | Path]):
        """Snapshot exactly the affected files and restore them on failure."""
        unique = {str(self.resolve_repo_path(path)) for path in paths}
        snapshot: dict[Path, bytes | None] = {}
        for raw in unique:
            path = Path(raw)
            snapshot[path] = path.read_bytes() if path.is_file() else None
        try:
            yield
        except Exception:
            for path, content in snapshot.items():
                if content is None:
                    if path.exists():
                        path.unlink()
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(content)
            raise

    @contextmanager
    def lock(self):
        lock_path = self.settings.runtime_root / "locks" / "repository.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        handle = lock_path.open("a+", encoding="utf-8")
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            yield
        finally:
            try:
                if os.name == "nt":
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                handle.close()

    def audit(self, event: str, **fields: object) -> None:
        self.settings.ensure_runtime()
        record = {"timestamp": datetime.now(timezone.utc).isoformat(), "event": event, **fields}
        with (self.settings.runtime_root / "logs" / "audit.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
