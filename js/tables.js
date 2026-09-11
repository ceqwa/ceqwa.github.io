function escapeHtml(text) {
  var div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

async function renderTable(config) {
  var table = document.querySelector(config.table);
  var tbody = table.querySelector('tbody');
  var colspan = table.querySelectorAll('thead th').length;
  var res;

  try {
    res = await fetch(config.source);
    if (!res.ok) { throw new Error('HTTP ' + res.status); }
    var rows = await res.json();
  } catch (e) {
    tbody.innerHTML = '<tr><td colspan="' + colspan + '"><div class="state-message">Unable to load ' + config.label.toLowerCase() + '. Please try again later.</div></td></tr>';
    return;
  }

  if (!rows || !rows.length) {
    tbody.innerHTML = '<tr><td colspan="' + colspan + '"><div class="empty-state">No ' + config.label.toLowerCase() + ' uploaded yet.</div></td></tr>';
    return;
  }

  tbody.innerHTML = rows.map(function (row, index) {
    var cells = config.columns.map(function (col) {
      if (col === '#') { return '<td>' + (index + 1) + '</td>'; }
      if (col === 'file') {
        var links = '<a class="action" href="' + escapeHtml(row[col]) + '">Download</a>';
        if (row.markdown) {
          links += ' <a class="action" href="' + escapeHtml(row.markdown) + '">Markdown</a>';
        }
        return '<td>' + links + '</td>';
      }
      return '<td>' + escapeHtml(row[col] !== undefined ? row[col] : '') + '</td>';
    });
    return '<tr>' + cells.join('') + '</tr>';
  }).join('');
}

document.addEventListener('DOMContentLoaded', function () {
  renderTable({ table: '#documents-table', source: 'data/documents.json', columns: ['#', 'title', 'category', 'date', 'file'], label: 'Documents' });
  renderTable({ table: '#financials-table', source: 'data/financials.json', columns: ['#', 'description', 'period', 'amount', 'file'], label: 'Financial records' });
});
