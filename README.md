# CEQWA Website

Organization website hosted on GitHub Pages.

## Structure

- `index.html` — main page (About, Documents, Financials, Contact)
- `css/style.css` — styles
- `js/main.js` — small scripts
- `docs/` — upload official documents here
- `financials/` — upload financial statements here

## Adding a document

1. Drop the file into `docs/` (or `financials/`)
2. Add a link in `index.html` under the matching section
3. Commit and push to `main` — GitHub Pages updates automatically

## Local preview

Open `index.html` in a browser, or run a local server:

```
python -m http.server 8000
```

Then visit http://localhost:8000