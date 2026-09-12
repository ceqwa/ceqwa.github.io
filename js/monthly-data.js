(function () {
  var select = document.getElementById('monthly-period');
  var table = document.getElementById('monthly-data-table');
  var count = document.getElementById('monthly-count');
  var transactions = [];

  if (!select || !table) return;

  function escapeHtml(text) {
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  function render() {
    var rows = transactions.filter(function (transaction) {
      return transaction.source_file === select.value;
    });
    var tbody = table.querySelector('tbody');
    count.textContent = rows.length + (rows.length === 1 ? ' transaction' : ' transactions');

    if (!rows.length) {
      tbody.innerHTML = '<tr><td colspan="9"><div class="empty-state">No transactions recorded for this source period.</div></td></tr>';
      return;
    }

    tbody.innerHTML = rows.map(function (row, index) {
      var tags = (row.tags || []).map(escapeHtml).join(', ');
      var type = row.tags && row.tags.indexOf('income') !== -1 ? 'Income' :
        (row.tags && row.tags.indexOf('expense') !== -1 ? 'Expense' : 'Opening balance');
      var numericAmount = Number(row.amount);
      var displayAmount = Number.isFinite(numericAmount) ? numericAmount.toFixed(2) : 'Unavailable';
      var recurrence = row.recurrence === 'not_applicable' ? 'Not applicable' : (row.recurrence || '');
      return '<tr>' +
        '<td>' + (index + 1) + '</td>' +
        '<td>' + type + '</td>' +
        '<td>' + escapeHtml(row.raw_category || '') + '</td>' +
        '<td>' + escapeHtml(row.raw_description || '') + '</td>' +
        '<td>' + escapeHtml(row.date || 'Not specified') + '</td>' +
        '<td>' + displayAmount + '</td>' +
        '<td class="tag-list">' + tags + '</td>' +
        '<td>' + escapeHtml(row.accounting_class || 'Not specified') + '</td>' +
        '<td>' + escapeHtml(recurrence) + '</td>' +
        '</tr>';
    }).join('');
  }

  window.populateMonthlySelector(select)
    .then(function (data) {
      transactions = data;
      render();
      select.addEventListener('change', render);
    })
    .catch(function () {
      table.querySelector('tbody').innerHTML = '<tr><td colspan="9"><div class="state-message">Unable to load source-period data. Please try again later.</div></td></tr>';
    });
})();
