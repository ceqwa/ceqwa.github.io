# Add a Document

Use this skill when adding an official document, report, notice, or financial
publication to the static website.

## Official Documents

1. Put the file under `docs/`.
2. Add one object to `data/documents.json` with:
   `title`, `category`, `date`, and `file`.
3. Keep the path relative, for example `docs/constitution.pdf`.
4. Confirm the file exists and the Documents table can load it.

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
