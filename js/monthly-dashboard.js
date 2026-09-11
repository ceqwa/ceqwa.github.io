(function () {
  var select = document.getElementById('monthly-dashboard-period');
  if (!select) return;

  var transactions = [];
  function amount(value) { return Number(value || 0); }
  function hasTag(row, tag) { return (row.tags || []).indexOf(tag) !== -1; }
  function expenseLabel(row) {
    if (hasTag(row, 'food_waste')) return 'Food Waste Cleaning';
    if (hasTag(row, 'onam')) return 'Onam Celebration';
    if (hasTag(row, 'badminton') || hasTag(row, 'carrom') || hasTag(row, 'sports')) return 'Sports Activities';
    if (hasTag(row, 'electricity')) return 'Club Electricity';
    if (hasTag(row, 'catering')) return 'Catering';
    if (hasTag(row, 'electrical')) return 'Electrical Work';
    if (hasTag(row, 'fuel')) return 'Fuel';
    if (hasTag(row, 'quarters')) return 'Quarter Cleaning';
    if (hasTag(row, 'office_supplies') || hasTag(row, 'printing')) return 'Office Supplies and Printing';
    if (hasTag(row, 'repair')) return 'Repairs';
    if (hasTag(row, 'incinerator')) return 'Incinerator';
    if (hasTag(row, 'cleaning')) return 'Cleaning';
    if (hasTag(row, 'materials')) return 'Materials';
    if (hasTag(row, 'equipment')) return 'Equipment';
    return row.raw_category || 'Other Expenses';
  }
  function money(value) {
    return 'Rs. ' + amount(value).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  function grouped(rows, field) {
    var totals = {};
    rows.forEach(function (row) {
      var category = typeof field === 'function' ? field(row) : row[field] || 'Uncategorized';
      totals[category] = (totals[category] || 0) + amount(row.amount);
    });
    return Object.keys(totals).map(function (category) {
      return { label: category, amount: totals[category] };
    }).sort(function (a, b) { return b.amount - a.amount; });
  }
  function renderPie(id, rows) {
    Plotly.react(id, [{
      type: 'pie', labels: rows.map(function (row) { return row.label; }), values: rows.map(function (row) { return row.amount; }),
      hole: 0.4, marker: { colors: window.CEQWAChartColors() }, textinfo: 'percent', textposition: 'inside',
      hovertemplate: '%{label}: Rs. %{value:,.2f}<extra></extra>'
    }], window.CEQWAChartLayout({ height: 380, margin: { l: 20, r: 20, t: 20, b: 95 }, automargin: true, legend: { orientation: 'h', x: 0, y: -0.2, font: { size: 10 } } }), { responsive: true });
  }
  function render() {
    var rows = transactions.filter(function (row) { return row.source_file === select.value; });
    var income = rows.filter(function (row) { return hasTag(row, 'income'); });
    var expenses = rows.filter(function (row) { return hasTag(row, 'expense'); });
    var opening = rows.filter(function (row) { return hasTag(row, 'opening_balance'); });
    var incomeTotal = income.reduce(function (total, row) { return total + amount(row.amount); }, 0);
    var expenseTotal = expenses.reduce(function (total, row) { return total + amount(row.amount); }, 0);
    var openingTotal = opening.reduce(function (total, row) { return total + amount(row.amount); }, 0);
    var incomeByCategory = grouped(income, 'raw_category');
    var expenseByCategory = grouped(expenses, expenseLabel);
    var activities = Array.from(new Set(incomeByCategory.concat(expenseByCategory).map(function (row) { return row.label; })));
    var incomeMap = {}, expenseMap = {};
    incomeByCategory.forEach(function (row) { incomeMap[row.label] = row.amount; });
    expenseByCategory.forEach(function (row) { expenseMap[row.label] = row.amount; });

    document.getElementById('monthly-opening').textContent = money(openingTotal);
    document.getElementById('monthly-income').textContent = money(incomeTotal);
    document.getElementById('monthly-expenses').textContent = money(expenseTotal);
    document.getElementById('monthly-closing').textContent = money(openingTotal + incomeTotal - expenseTotal);
    document.getElementById('monthly-dashboard-count').textContent = rows.length + (rows.length === 1 ? ' transaction' : ' transactions');

    var colors = window.CEQWAChartColors();
    Plotly.react('chart-monthly-flow', [
      ].concat(activities.map(function (activity, index) {
        return { name: activity, type: 'bar', orientation: 'h', y: ['Income', 'Expenses'], x: [incomeMap[activity] || 0, expenseMap[activity] || 0], text: [incomeMap[activity] ? money(incomeMap[activity]) : '', expenseMap[activity] ? money(expenseMap[activity]) : ''], textposition: 'inside', insidetextanchor: 'middle', marker: { color: colors[index % colors.length] }, hovertemplate: '%{y}<br>' + activity + ': Rs. %{x:,.2f}<extra></extra>' };
      })), window.CEQWAChartLayout({ barmode: 'stack', height: 390, margin: { t: 20, r: 35, b: 145, l: 70 }, xaxis: { title: 'Amount (Rs.)' }, yaxis: { title: 'Flow', automargin: true }, legend: { orientation: 'h', x: 0, y: -0.32, font: { size: 10 } } }), { responsive: true });
    renderPie('chart-monthly-income', incomeByCategory);
    renderPie('chart-monthly-expenses', expenseByCategory);

    var recurringIncome = income.filter(function (row) { return row.recurrence === 'recurring'; }).reduce(function (total, row) { return total + amount(row.amount); }, 0);
    var oneOffIncome = income.filter(function (row) { return row.recurrence === 'one_off'; }).reduce(function (total, row) { return total + amount(row.amount); }, 0);
    var recurringExpenses = expenses.filter(function (row) { return row.recurrence === 'recurring'; }).reduce(function (total, row) { return total + amount(row.amount); }, 0);
    var oneOffExpenses = expenses.filter(function (row) { return row.recurrence === 'one_off'; }).reduce(function (total, row) { return total + amount(row.amount); }, 0);
    Plotly.react('chart-monthly-recurrence', [
      { name: 'Income', type: 'bar', x: ['Recurring', 'One-off'], y: [recurringIncome, oneOffIncome], text: [money(recurringIncome), money(oneOffIncome)], textposition: 'outside', cliponaxis: false, marker: { color: colors[2] }, hovertemplate: '%{x}<br>Income: Rs. %{y:,.2f}<extra></extra>' },
      { name: 'Expenses', type: 'bar', x: ['Recurring', 'One-off'], y: [recurringExpenses, oneOffExpenses], text: [money(recurringExpenses), money(oneOffExpenses)], textposition: 'outside', cliponaxis: false, marker: { color: colors[4] }, hovertemplate: '%{x}<br>Expenses: Rs. %{y:,.2f}<extra></extra>' }
    ], window.CEQWAChartLayout({ barmode: 'group', height: 380, margin: { t: 35, r: 35, b: 85, l: 60 }, yaxis: { title: 'Amount (Rs.)', automargin: true }, legend: { orientation: 'h', x: 0, y: -0.2, font: { size: 10 } } }), { responsive: true });
  }

  window.populateMonthlySelector(select)
    .then(function (data) { transactions = data; render(); select.addEventListener('change', render); })
    .catch(function () { document.getElementById('monthly-dashboard-count').textContent = 'Unable to load monthly data'; });

  window.addEventListener('resize', function () {
    ['chart-monthly-flow', 'chart-monthly-income', 'chart-monthly-expenses', 'chart-monthly-recurrence'].forEach(function (id) {
      var chart = document.getElementById(id);
      if (chart && chart.data) Plotly.Plots.resize(chart);
    });
  });
})();
