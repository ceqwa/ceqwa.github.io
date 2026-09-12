(function () {
  var transactionsPromise = fetch('data/finances/finances.json')
    .then(function (response) {
      if (!response.ok) throw new Error('HTTP ' + response.status);
      return response.json();
    })
    .then(function (data) {
      if (!data || !Array.isArray(data.transactions)) throw new Error('Invalid transaction data');
      return data.transactions;
    });

  function comparePeriods(left, right) {
    function compareText(first, second) {
      first = String(first); second = String(second);
      return first < second ? -1 : (first > second ? 1 : 0);
    }
    return compareText(left.start_date, right.start_date) ||
      compareText(left.end_date, right.end_date) ||
      compareText(left.period_id, right.period_id) ||
      compareText(left.file, right.file);
  }

  var periodsPromise = fetch('data/metadata.json')
    .then(function (response) {
      if (!response.ok) throw new Error('HTTP ' + response.status);
      return response.json();
    })
    .then(function (data) {
      if (!data || typeof data !== 'object' || !Array.isArray(data.financials)) throw new Error('Invalid metadata');
      if (!data.financials.every(function (period) {
        return period && typeof period === 'object' && typeof period.file === 'string' && period.file.trim() &&
          typeof period.period_id === 'string' && typeof period.start_date === 'string' && typeof period.end_date === 'string';
      })) throw new Error('Invalid financial metadata');
      return data.financials.slice().sort(comparePeriods);
    });

  var dataPromise = Promise.all([transactionsPromise, periodsPromise]).then(function (results) {
    return { transactions: results[0], periods: results[1] };
  });

  function fallbackLabel(source) {
    var match = /^(\d{2})\.(\d{4})\.pdf$/.exec(source || '');
    if (!match) return source || 'Unknown period';
    return new Date(Number(match[2]), Number(match[1]) - 1, 1).toLocaleString('en', { month: 'long', year: 'numeric' });
  }

  window.CEQWAMonthlyData = dataPromise.then(function (data) { return data.transactions; });
  window.populateMonthlySelector = function (select) {
    return dataPromise.then(function (data) {
      while (select.firstChild) select.removeChild(select.firstChild);
      data.periods.forEach(function (period) {
        var source = period.file.split('/').pop();
        var option = document.createElement('option');
        option.value = source;
        option.textContent = period.period_label || period.period || fallbackLabel(source);
        select.appendChild(option);
      });
      return data.transactions;
    });
  };
})();
