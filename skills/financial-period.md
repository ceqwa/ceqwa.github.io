# Add a Financial Period

Use this skill when adding a new monthly or quarterly Sources and Uses of
Funds Statement.

## Files to Update

- `financials/<period>.pdf` - original published statement
- `financials/<period>.md` - machine-readable companion
- `data/financials.json` - published statement index
- `data/finances/finances.json` - individual transactions and opening balance
- `data/financials-dashboard.json` - main dashboard period arrays and breakdowns

`data/finances/finances_accrual.json` is an alternative dataset and is not read
by the website. Update it only when the accrual dataset is intentionally being
maintained as well.

## Procedure

1. Inspect the PDF and transcribe every source and use line exactly.
2. Create a Markdown companion with YAML front matter containing:
   `title`, `organization`, `currency`, `statement_date`, `period_label`,
   `period_from`, `period_to`, `source_pdf`, `total_income`,
   `total_expenses`, and `closing_balance`.
3. Use plain numeric amounts in Markdown tables. Do not put currency symbols
   or thousands separators inside numeric cells.
4. Add the PDF and Markdown paths to one entry in `data/financials.json`.
5. Add one raw transaction object for every individual line item. Preserve the
   original `raw_category` and `raw_description`.
6. Add the statement's carried-forward opening balance as a transaction with
   the `opening_balance` tag.
7. Use `income` or `expense` flow tags, a recurrence value of `recurring` or
   `one_off`, and relevant category/function tags.
8. Extend every period-indexed array in `data/financials-dashboard.json` in the
   same order as `periods`.
9. Update recurring and one-off dashboard breakdowns so their totals still
   equal the corresponding series totals. Use meaningful categories and group
   only small items when individual slices would be unreadable.
10. Run `python scripts/validate_finances.py`.

## Reconciliation

For each statement:

```text
total sources = opening balance + income
closing balance = opening balance + income - expenses
```

The dashboard income series excludes opening balances. The published
statement total includes opening balances.

## UI Behavior

The Finances table reads `data/financials.json`.

The Monthly Data and Monthly Dashboard selectors discover periods from
`data/finances/finances.json`; no HTML option needs to be added manually.

The main Dashboard reads `data/financials-dashboard.json`, so its period arrays and
breakdowns must be updated for every new period.
