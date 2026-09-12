# Add a Document

Use this skill when adding an official document, report, notice, or financial
publication to the static website.

## Official Documents

1. Put the file under `documents/`.
2. Add one object to the `documents` array in `data/metadata.json` with:
   `title`, `category`, `date`, and `file`.
3. Keep the path relative, for example `documents/constitution.pdf`.
4. Confirm the file exists and the Documents table can load it.
5. Use only the documented fields; unknown metadata fields and duplicate `file`
   paths are rejected.

## Financial Publications

Use `skills/financial-period.md` for a Sources and Uses statement. Financial
statements belong under `financials/` and should have both PDF and Markdown
versions.

## Rules

- Do not replace or rename existing published files without an explicit request.
- Use descriptive filenames that match the JSON path exactly.
- Preserve the original document; do not modify a PDF to create a summary.
- Escape or validate any user-visible text if changing rendering code.
- Run `python scripts/validate_finances.py` when the change affects financial files.
- Run `python scripts/validate_site.py` after changing document paths or HTML.

## MCP Uploads

Place the source file in ignored `incoming/` and call
`ceqwa_propose_document_add`. The proposal must be approved and executed before
the file is copied into `documents/` and indexed in `data/metadata.json`.
Markdown is optional; when it is omitted, the metadata entry has no `markdown`
field and the site does not show a broken Markdown link.

Financial statements use `ceqwa_propose_financial_import`, not the general
document tool. That workflow always stores the PDF and generated Markdown under
`financials/`, updates the `financials` array in `data/metadata.json`, updates
the canonical transactions and dashboard data, and validates reconciliation.
Financial `period_id`, `period`, and source `file` values must be unique.
