# CEQWA Website Skills

These skills are portable instructions for an AI assistant maintaining this
static website. Read the relevant skill before changing files.

## Skills

- `financial-period.md` - add a financial statement period and its data
- `document-upload.md` - add an official document or financial publication
- `verification.md` - validate links, JSON, totals, tags, and dashboard data

## General Rules

1. Inspect the existing files before editing.
2. Preserve the existing PDF files and add Markdown companions where required.
3. Keep `data/finances/finances.json` as the transaction-level source of truth.
4. Use the existing tag vocabulary and keep original document wording in raw
   descriptions.
5. Run `python scripts/validate_finances.py` after financial changes.
6. Never silently invent amounts. If a PDF cannot be read, report the missing
   figures instead of estimating them.
