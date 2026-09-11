(function () {
  var dataPromise = fetch('data/finances/finances.json')
    .then(function (response) {
      if (!response.ok) throw new Error('HTTP ' + response.status);
      return response.json();
    })
    .then(function (data) { return data.transactions || []; });

  function labelFor(source) {
    var match = /^(\d{2})\.(\d{4})\.pdf$/.exec(source);
    if (!match) return source;
    return new Date(Number(match[2]), Number(match[1]) - 1, 1).toLocaleString('en', { month: 'long', year: 'numeric' });
  }

  window.CEQWAMonthlyData = dataPromise;
  window.populateMonthlySelector = function (select) {
    return dataPromise.then(function (transactions) {
      var sources = Array.from(new Set(transactions.map(function (row) { return row.source_file; }))).sort(function (a, b) {
        return a.localeCompare(b, undefined, { numeric: true });
      });
      select.innerHTML = sources.map(function (source) {
        return '<option value="' + source + '">' + labelFor(source) + '</option>';
      }).join('');
      return transactions;
    });
  };
})();
