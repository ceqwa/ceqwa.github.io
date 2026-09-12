"""Safe document and Markdown companion operations."""

from __future__ import annotations

import copy
import re
from pathlib import Path

from ..errors import CeqwaError, require
from .metadata import DOCUMENT_FIELDS, validate_metadata
from .repository import Repository
from .validation import require_valid, run_site_validation


class DocumentService:
    def __init__(self, repo: Repository):
        self.repo = repo

    def list(self) -> dict:
        return {"success": True, "documents": self.repo.load_metadata()["documents"]}

    def _safe_markdown(self, markdown: str) -> None:
        require("<script" not in markdown.lower(), "INVALID_SCHEMA", "Markdown must not contain script elements")
        for link in re.findall(r"!?\[[^]]*\]\(([^)]+)\)", markdown):
            require(not link.startswith(("/", "\\", "http:", "https:", "javascript:", "data:")), "INVALID_PATH", "Markdown links must be relative and local")

    def propose_add(self, payload: dict) -> tuple[dict, str, list[str], list[str]]:
        require(isinstance(payload, dict), "INVALID_SCHEMA", "Document metadata must be an object")
        allowed_input = {"source_document", "destination", "markdown", "markdown_destination", "title", "category", "date"}
        unknown = sorted(set(payload) - allowed_input)
        require(not unknown, "INVALID_SCHEMA", "Document input contains unknown fields", {"fields": unknown})
        source = payload.get("source_document"); require(isinstance(source, str), "INVALID_SCHEMA", "source_document is required")
        source_path = self.repo.resolve_repo_path(source, allow_incoming=True); require(source_path.is_file(), "FILE_NOT_FOUND", "Source document does not exist")
        destination = payload.get("destination") or f"documents/{source_path.name}"
        self.repo.resolve_repo_path(destination)
        require(not self.repo.resolve_repo_path(destination).exists(), "DUPLICATE_DOCUMENT", "Document destination already exists")
        markdown = payload.get("markdown")
        markdown_destination = None
        if markdown is not None:
            markdown_destination = payload.get("markdown_destination") or f"{Path(destination).with_suffix('.md')}"
            self._safe_markdown(markdown)
            self.repo.resolve_repo_path(markdown_destination)
        item = {"title": payload.get("title", source_path.stem), "category": payload.get("category", "Official Documents"),
                "date": payload.get("date"), "file": destination}
        if markdown_destination is not None:
            item["markdown"] = markdown_destination
        proposal = {"kind": "document_add", "source_document": source, "destination": destination,
                    "markdown_destination": markdown_destination, "markdown": markdown, "entry": item}
        return proposal, f"Add document {item['title']} and update the document index", [destination] + ([markdown_destination] if markdown is not None else []), ["data/metadata.json"]

    def execute_add(self, payload: dict) -> dict:
        affected = [payload["destination"], "data/metadata.json"] + ([payload["markdown_destination"]] if payload.get("markdown") is not None else [])
        metadata = self.repo.load_metadata(); documents = metadata["documents"]
        require(not any(d.get("file") == payload["destination"] for d in documents), "DUPLICATE_DOCUMENT", "Document is already indexed")
        with self.repo.mutation(affected):
            self.repo.copy_incoming(payload["source_document"], payload["destination"])
            if payload.get("markdown") is not None:
                self.repo.atomic_write(payload["markdown_destination"], payload["markdown"])
            documents.append(payload["entry"])
            validate_metadata(metadata, self.repo.root)
            self.repo.write_json("data/metadata.json", metadata)
            require_valid(run_site_validation(self.repo.root))
        return {"operation": "document_add", "files_changed": affected, "site_validation": "pass"}

    def propose_markdown(self, payload: dict) -> tuple[dict, str, list[str]]:
        source = payload.get("source_document"); require(isinstance(source, str), "INVALID_SCHEMA", "source_document is required")
        source_path = self.repo.resolve_repo_path(source); require(source_path.is_file(), "FILE_NOT_FOUND", "Source document does not exist")
        markdown = payload.get("markdown"); require(isinstance(markdown, str), "INVALID_SCHEMA", "markdown is required")
        self._safe_markdown(markdown)
        destination = payload.get("destination") or str(Path(source).with_suffix(".md"))
        self.repo.resolve_repo_path(destination)
        return {"kind": "markdown_companion", "source_document": source, "destination": destination, "markdown": markdown, "metadata": payload.get("metadata", {} )}, f"Create Markdown companion {destination}", [destination]

    def execute_markdown(self, payload: dict) -> dict:
        with self.repo.mutation([payload["destination"]]):
            self.repo.atomic_write(payload["destination"], payload["markdown"])
            require_valid(run_site_validation(self.repo.root))
        return {"operation": "markdown_companion", "files_changed": [payload["destination"]], "site_validation": "pass"}

    def propose_update(self, document_file: str, changes: dict) -> tuple[dict, str, list[str]]:
        require(isinstance(changes, dict), "INVALID_SCHEMA", "Document changes must be an object")
        unknown = sorted(set(changes) - DOCUMENT_FIELDS)
        require(not unknown, "INVALID_SCHEMA", "Document changes contain unknown fields", {"fields": unknown})
        metadata = self.repo.load_metadata(); documents = metadata["documents"]
        current = next((item for item in documents if item.get("file") == document_file), None)
        require(current is not None, "FILE_NOT_FOUND", "Document is not indexed")
        after = copy.deepcopy(current); after.update(changes)
        for field in ("file", "markdown"):
            if field in after and after[field]:
                self.repo.resolve_repo_path(after[field])
        candidate = copy.deepcopy(metadata)
        candidate["documents"] = [after if item is current else item for item in documents]
        validate_metadata(candidate, self.repo.root)
        return {"kind": "document_update", "document_file": document_file, "before": current, "after": after}, f"Update document metadata for {current.get('title', document_file)}", ["data/metadata.json"]

    def execute_update(self, payload: dict) -> dict:
        metadata = self.repo.load_metadata(); documents = metadata["documents"]
        current = next((item for item in documents if item.get("file") == payload["document_file"]), None)
        require(current is not None, "FILE_NOT_FOUND", "Document is no longer indexed")
        candidate = copy.deepcopy(metadata)
        candidate["documents"] = [payload["after"] if item is current else item for item in documents]
        validate_metadata(candidate, self.repo.root)
        current.clear(); current.update(payload["after"])
        with self.repo.mutation(["data/metadata.json"]):
            self.repo.write_json("data/metadata.json", metadata); require_valid(run_site_validation(self.repo.root))
        return {"operation": "document_update", "files_changed": ["data/metadata.json"], "site_validation": "pass"}

    def propose_delete(self, document_file: str, delete_source: bool = True) -> tuple[dict, str, list[str], list[str]]:
        metadata = self.repo.load_metadata(); documents = metadata["documents"]
        current = next((item for item in documents if item.get("file") == document_file), None)
        require(current is not None, "FILE_NOT_FOUND", "Document is not indexed")
        self.repo.resolve_repo_path(document_file); require(not delete_source or self.repo.resolve_repo_path(document_file).is_file(), "FILE_NOT_FOUND", "Source file does not exist")
        deletes = [document_file] if delete_source else []
        if delete_source and current.get("markdown") and self.repo.resolve_repo_path(current["markdown"]).is_file():
            deletes.append(current["markdown"])
        return {"kind": "document_delete", "document_file": document_file, "delete_source": delete_source, "before": current}, f"Delete {current.get('title', document_file)}; source files will {'also ' if delete_source else 'not '}be removed", [], ["data/metadata.json"], deletes

    def execute_delete(self, payload: dict) -> dict:
        metadata = self.repo.load_metadata(); documents = metadata["documents"]
        current = next((item for item in documents if item.get("file") == payload["document_file"]), None)
        require(current is not None, "FILE_NOT_FOUND", "Document is no longer indexed")
        affected = ["data/metadata.json"]
        if payload.get("delete_source"):
            affected.append(payload["document_file"])
            if current.get("markdown") and self.repo.resolve_repo_path(current["markdown"]).is_file(): affected.append(current["markdown"])
        with self.repo.mutation(affected):
            documents.remove(current); self.repo.write_json("data/metadata.json", metadata)
            if payload.get("delete_source"):
                self.repo.resolve_repo_path(payload["document_file"]).unlink(missing_ok=True)
                if current.get("markdown"): self.repo.resolve_repo_path(current["markdown"]).unlink(missing_ok=True)
            require_valid(run_site_validation(self.repo.root))
        return {"operation": "document_delete", "files_changed": affected, "site_validation": "pass"}

    def extract_pdf_text(self, source: str) -> dict:
        path = self.repo.resolve_repo_path(source, allow_incoming=True)
        require(path.is_file(), "FILE_NOT_FOUND", "PDF does not exist")
        require(path.suffix.lower() == ".pdf", "INVALID_SCHEMA", "source_document must be a PDF")
        try:
            from pypdf import PdfReader
        except ImportError:
            # This deliberately remains a helper, never an authoritative parser.
            return {"success": True, "text": "", "pages": 0, "warning": "Install the optional pdf extra for PDF text extraction"}
        reader = PdfReader(str(path))
        return {"success": True, "text": "\n\n".join(page.extract_text() or "" for page in reader.pages), "pages": len(reader.pages), "authoritative": False}

    def render_pdf_pages(self, source: str, output_dir: str = "incoming/rendered") -> dict:
        source_path = self.repo.resolve_repo_path(source, allow_incoming=True)
        require(source_path.is_file(), "FILE_NOT_FOUND", "PDF does not exist")
        try:
            import fitz
        except ImportError:
            raise CeqwaError("OPTIONAL_DEPENDENCY_MISSING", "Install the optional pdf extra for PDF rendering")
        output = self.repo.resolve_repo_path(output_dir, allow_incoming=True); output.mkdir(parents=True, exist_ok=True)
        document = fitz.open(str(source_path)); pages = []
        for number, page in enumerate(document):
            target = output / f"{source_path.stem}-page-{number + 1}.png"
            page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False).save(str(target)); pages.append(str(target.relative_to(self.repo.settings.incoming_root if str(target).startswith(str(self.repo.settings.incoming_root)) else self.repo.root)).replace("\\", "/"))
        return {"success": True, "pages": pages, "authoritative": False}

    def ocr_document(self, source: str, language: str = "eng") -> dict:
        """Optional evidence helper; OCR is never treated as canonical accounting data."""
        path = self.repo.resolve_repo_path(source, allow_incoming=True)
        require(path.is_file(), "FILE_NOT_FOUND", "Document does not exist")
        try:
            import pytesseract
            from PIL import Image
        except ImportError:
            raise CeqwaError("OPTIONAL_DEPENDENCY_MISSING", "Install an OCR provider (pytesseract and Pillow) for OCR")
        require(path.suffix.lower() not in {".pdf"}, "OPTIONAL_DEPENDENCY_MISSING", "Render PDF pages first, then OCR the page images")
        return {"success": True, "text": pytesseract.image_to_string(Image.open(path), lang=language), "authoritative": False}
