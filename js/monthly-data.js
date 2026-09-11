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
      tbody.innerHTML = '<tr><td colspan="7"><div class="empty-state">No transactions recorded for this month.</div></td></tr>';
      return;
    }

    tbody.innerHTML = rows.map(function (row, index) {
      var tags = (row.tags || []).map(escapeHtml).join(', ');
      var type = row.tags && row.tags.indexOf('income') !== -1 ? 'Income' :
        (row.tags && row.tags.indexOf('expense') !== -1 ? 'Expense' : 'Opening balance');
      return '<tr>' +
        '<td>' + (index + 1) + '</td>' +
        '<td>' + type + '</td>' +
        '<td>' + escapeHtml(row.raw_category || '') + '</td>' +
        '<td>' + escapeHtml(row.raw_description || '') + '</td>' +
        '<td>' + Number(row.amount || 0).toFixed(2) + '</td>' +
        '<td class="tag-list">' + tags + '</td>' +
        '<td>' + escapeHtml(row.recurrence || '') + '</td>' +
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
      table.querySelector('tbody').innerHTML = '<tr><td colspan="7"><div class="state-message">Unable to load monthly data. Please try again later.</div></td></tr>';
    });
})();
