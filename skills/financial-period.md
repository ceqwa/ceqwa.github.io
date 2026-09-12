# Add a Financial Period

Use this skill when adding a new monthly or quarterly Sources and Uses of
Funds Statement.

## Files to Update

- `financials/<period>.pdf` - original published statement
- `financials/<period>.md` - machine-readable companion
- `data/metadata.json` - published statement metadata in the `financials` array
- `data/finances/finances.json` - individual transactions and opening balance
- `data/financials-dashboard.json` - main dashboard period arrays and breakdowns

`data/finances/finances.json` is the single canonical transaction dataset. Do
not create or maintain a second unexplained financial dataset.

## Procedure

1. Inspect the PDF and transcribe every source and use line exactly.
2. Create a Markdown companion with YAML front matter containing:
   `title`, `organization`, `currency`, `statement_date`, `period_label`,
   `period_from`, `period_to`, `source_pdf`, `total_income`,
   `total_expenses`, and `closing_balance`.
3. Use plain numeric amounts in Markdown tables. Do not put currency symbols
   or thousands separators inside numeric cells.
4. Add the PDF and Markdown paths to one entry in the `financials` array in
   `data/metadata.json`.
5. Add one transaction object for every individual line item. Preserve the
   original `raw_category` and `raw_description`, assign a deterministic stable
   `transaction_id`, and use an evidenced ISO `date` or `null`.
6. Add the statement's carried-forward opening balance as a transaction with
   the `opening_balance` tag, `accounting_class: "opening_balance"`, and
   `recurrence: "not_applicable"`.
7. Use exactly one flow tag, a recurrence value of `recurring`, `one_off`, or
   `not_applicable`, and an accounting class of `income`, `opex`, or `capex`.
8. Extend every period-indexed array in `data/financials-dashboard.json` in the
   same order as `periods`.
9. Update recurring and one-off dashboard breakdowns so their totals still
   equal the corresponding series totals. Use meaningful categories and group
   only small items when individual slices would be unreadable.
10. Run `python scripts/validate_finances.py`,
    `python scripts/test_financial_fixtures.py`, and
    `python scripts/validate_site.py`.

## Reconciliation

For each statement:

```text
total sources = opening balance + income
closing balance = opening balance + income - expenses
```

The dashboard income series excludes opening balances. The published
statement total includes opening balances.

## UI Behavior

The Finances table reads the `financials` array from `data/metadata.json`.

The Monthly Data and Monthly Dashboard selectors discover periods from the
`financials` array in `data/metadata.json`; transactions are only associated with
those published periods after discovery. No HTML option needs to be added manually.

Metadata periods are ordered chronologically by `start_date`, then end date,
period ID, and source file. Unknown metadata fields and duplicate period IDs,
period values, or source files are rejected.

The main Dashboard reads `data/financials-dashboard.json`, so its period arrays and
breakdowns must be updated for every new period.
