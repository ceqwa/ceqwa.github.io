# CEQWA Website

Organization website hosted on GitHub Pages.

## Structure

- `index.html` — home page
- `about.html` — about the organization
- `documents.html` — official documents
- `financials.html` — financial statements
- `contact.html` — contact information
- `css/style.css` — design system (CSS custom properties)
- `js/main.js` — theme toggle, mobile navigation, footer year
- `js/tables.js` — renders tables from JSON
- `data/` — website data JSON files
- `scripts/` — maintenance and validation scripts
- `skills/` — portable AI maintenance instructions
- `docs/` — upload official documents here
- `financials/` — upload financial statements here (PDF plus machine-readable Markdown companion, e.g. `05.2026.pdf` / `05.2026.md`)

## Design system

All visual tokens live as CSS custom properties in `:root` and `[data-theme="dark"]`:

- Colors (`--bg`, `--surface`, `--text`, `--border`, `--primary`, `--accent`, nav colors)
- Spacing (`--space-1` … `--space-8`)
- Radii (`--radius-sm/md/lg`)
- Shadows (`--shadow-sm/md`)
- Type scale (`--fs-xs` … `--fs-3xl`)
- Transitions (`--transition`)

Dark mode is toggled via `data-theme` on `<html>`, persisted in `localStorage`,
and defaults to the user's `prefers-color-scheme`.

## Adding a document

Documents and financials are rendered from JSON files.

1. Drop the file into `docs/` (or `financials/`)
2. Add an entry to `data/documents.json` (or `data/financials.json`)
3. Commit and push to `main` — GitHub Pages updates automatically

### documents.json format

The `#` column is auto-generated.

```json
[
  {
    "title": "Constitution & Bye-laws",
    "category": "Governance",
    "date": "2025",
    "file": "docs/constitution.pdf"
  }
]
```

### financials.json format

```json
[
  {
    "description": "Income & Expenditure",
    "period": "FY 2025-26",
    "amount": "Rs. 1,00,000",
    "file": "financials/income-expenditure.pdf",
    "markdown": "financials/income-expenditure.md"
  }
]
```

Each financial statement is published as both a PDF (human-readable) and a
Markdown file (machine-readable, with YAML front matter and plain-number
tables). The Finances tab shows a `Markdown` link next to `Download` when the
`markdown` field is present.

### Validate financial data

Run the zero-dependency validator before publishing a new statement:

```
python scripts/validate_finances.py
```

It checks JSON structure, statement links, Markdown companions, transaction
tags, dashboard alignment, and opening-balance/income/expense reconciliation.

## Local preview

```
python -m http.server 8000
```

Then visit http://localhost:8000
