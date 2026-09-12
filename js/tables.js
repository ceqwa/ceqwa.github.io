function safeRelativePath(value) {
  if (typeof value !== 'string' || !value.trim()) return null;
  var path = value.trim();
  if (/^[a-z][a-z\d+.-]*:/i.test(path) || path.indexOf('//') === 0 || path.indexOf('\\') !== -1) return null;
  return path;
}

function replaceChildren(element) {
  while (element.firstChild) element.removeChild(element.firstChild);
}

function addCell(row, value, className) {
  var cell = document.createElement('td');
  if (className) cell.className = className;
  cell.textContent = value == null ? '' : String(value);
  row.appendChild(cell);
  return cell;
}

function compareFinancialPeriods(left, right) {
  function compareText(first, second) {
    first = String(first); second = String(second);
    return first < second ? -1 : (first > second ? 1 : 0);
  }
  return compareText(left.start_date, right.start_date) ||
    compareText(left.end_date, right.end_date) ||
    compareText(left.period_id, right.period_id) ||
    compareText(left.file, right.file);
}

function renderTable(config) {
  var table = document.querySelector(config.table);
  if (!table) return;

  var tbody = table.querySelector('tbody');
  var colspan = table.querySelectorAll('thead th').length;
  if (!tbody) return;

  function showState(message, className) {
    replaceChildren(tbody);
    var row = document.createElement('tr');
    var cell = document.createElement('td');
    cell.colSpan = colspan;
    cell.className = className || 'state-message';
    cell.textContent = message;
    row.appendChild(cell);
    tbody.appendChild(row);
  }

  fetch(config.source)
    .then(function (res) {
      if (!res.ok) throw new Error('HTTP ' + res.status);
      return res.json();
    })
    .then(function (payload) {
      var rows = config.dataKey ? payload[config.dataKey] : payload;
      if (!Array.isArray(rows)) {
        showState('Unable to load ' + config.label.toLowerCase() + ': invalid metadata.', 'state-message');
        return;
      }
      if (config.validateRows && !rows.every(config.validateRows)) {
        showState('Unable to load ' + config.label.toLowerCase() + ': invalid metadata.', 'state-message');
        return;
      }
      if (!rows.length) {
        showState('No ' + config.label.toLowerCase() + ' uploaded yet.', 'empty-state');
        return;
      }
      if (config.sort) rows = rows.slice().sort(config.sort);
      replaceChildren(tbody);
      rows.forEach(function (row, index) {
        var tr = document.createElement('tr');
        config.columns.forEach(function (col) {
          if (col === '#') {
            addCell(tr, index + 1);
          } else if (col === 'file') {
            var cell = document.createElement('td');
            var filePath = safeRelativePath(row[col]);
            if (filePath) {
              var link = document.createElement('a');
              link.className = 'action';
              link.href = filePath;
              link.textContent = 'Download';
              cell.appendChild(link);
            } else {
              cell.textContent = 'Unavailable';
            }
            var markdownPath = safeRelativePath(row.markdown);
            if (markdownPath) {
              var separator = document.createTextNode(' ');
              var markdownLink = document.createElement('a');
              markdownLink.className = 'action';
              markdownLink.href = markdownPath;
              markdownLink.textContent = 'Markdown';
              cell.appendChild(separator);
              cell.appendChild(markdownLink);
            }
            tr.appendChild(cell);
          } else if (col === 'period') {
            addCell(tr, row.period_label || row.period || '');
          } else {
            addCell(tr, row[col]);
          }
        });
        tbody.appendChild(tr);
      });
    })
    .catch(function () {
      showState('Unable to load ' + config.label.toLowerCase() + '. Please try again later.');
    });
}

document.addEventListener('DOMContentLoaded', function () {
  renderTable({ table: '#documents-table', source: 'data/metadata.json', dataKey: 'documents', columns: ['#', 'title', 'category', 'date', 'file'], label: 'Documents', validateRows: function (row) { return row && typeof row === 'object' && typeof row.file === 'string' && row.file.trim(); } });
  renderTable({ table: '#financials-table', source: 'data/metadata.json', dataKey: 'financials', columns: ['#', 'description', 'period', 'amount', 'file'], label: 'Financial records', sort: compareFinancialPeriods, validateRows: function (row) { return row && typeof row === 'object' && typeof row.file === 'string' && row.file.trim() && typeof row.start_date === 'string' && typeof row.end_date === 'string' && typeof row.period_id === 'string'; } });
});
