# Verify the Website

Use this skill after changing documents, financial statements, JSON data, or
dashboard code.

## Required Checks

Run from the repository root:

```text
python scripts/validate_finances.py
```

The validator checks:

- JSON parsing
- PDF and Markdown companion paths
- Transaction source, category, description, amount, and tags
- Valid tag vocabulary
- Dashboard array lengths and period alignment
- Recurring and one-off income and expense totals
- Opening, income, expense, and closing-balance reconciliation
- Markdown front-matter totals
- Expense breakdown totals

## Manual Checks

1. Start a local server with `python -m http.server 8000`.
2. Open `http://localhost:8000/financials.html`.
3. Check Dashboard, Monthly Dashboard, Finances, and Monthly Data tabs.
4. Select every available month in both monthly selectors.
5. Confirm opening and closing balances agree with the statement.
6. Check PDF and Markdown links.
7. Check desktop and narrow-screen layouts.
8. Check light and dark themes.

If Node.js is installed, also run:

```text
node --check js/dashboard.js
node --check js/monthly-dashboard.js
node --check js/monthly-data.js
node --check js/monthly-options.js
```

Do not declare the work complete if validation fails. Report any unavailable
tool, such as Node.js, clearly.
