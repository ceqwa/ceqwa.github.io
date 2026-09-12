(function () {
  var dashboardData = null;
  function money(value) {
    var number = Number(value);
    return Number.isFinite(number) ? 'Rs. ' + number.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : 'Unavailable';
  }

  window.CEQWAAccessibleTable = function (containerId, caption, headers, rows) {
    var container = document.getElementById(containerId);
    if (!container) return;
    replaceChildren(container);
    var table = document.createElement('table');
    table.className = 'data-table compact-data-table';
    var tableCaption = document.createElement('caption');
    tableCaption.textContent = caption;
    table.appendChild(tableCaption);
    var thead = document.createElement('thead');
    var headRow = document.createElement('tr');
    headers.forEach(function (header) {
      var th = document.createElement('th');
      th.scope = 'col';
      th.textContent = header;
      headRow.appendChild(th);
    });
    thead.appendChild(headRow);
    table.appendChild(thead);
    var tbody = document.createElement('tbody');
    rows.forEach(function (values) {
      var row = document.createElement('tr');
      values.forEach(function (value) {
        var cell = document.createElement('td');
        cell.textContent = value == null ? '' : String(value);
        row.appendChild(cell);
      });
      tbody.appendChild(row);
    });
    table.appendChild(tbody);
    container.appendChild(table);
  };

  function replaceChildren(element) {
    while (element.firstChild) element.removeChild(element.firstChild);
  }

  function setupTabs() {
    var buttons = document.querySelectorAll('.tab-btn');
    buttons.forEach(function (btn) {
      btn.addEventListener('click', function () {
        buttons.forEach(function (b) {
          var active = b === btn;
          b.classList.toggle('active', active);
          b.setAttribute('aria-selected', active ? 'true' : 'false');
        });
        document.querySelectorAll('.tab-panel').forEach(function (panel) {
          var show = panel.id === 'panel-' + btn.dataset.tab;
          panel.classList.toggle('active', show);
          if (show) panel.removeAttribute('hidden'); else panel.setAttribute('hidden', '');
        });
        if (btn.dataset.tab === 'dashboard' || btn.dataset.tab === 'monthly-dashboard') window.dispatchEvent(new Event('resize'));
      });
    });
  }

  function renderPie(id, breakdown) {
    Plotly.newPlot(id, [{
      type: 'pie', labels: breakdown.map(function (e) { return e.category; }), values: breakdown.map(function (e) { return e.amount; }), hole: 0.4,
      marker: { colors: window.CEQWAChartColors(), line: { color: window.CEQWAChartSeparator(), width: 1.5 } }, textinfo: 'percent', textposition: 'inside', rotation: 45,
      hovertemplate: '%{label}: Rs. %{value:,.0f}<extra></extra>'
    }], window.CEQWAChartLayout({ margin: { l: 20, r: 20, t: 20, b: 85 }, automargin: true, height: 460, legend: { orientation: 'h', x: 0, y: -0.2, font: { size: 10 } } }), { responsive: true });
  }

  function renderCharts(data) {
    var periods = data.periods;
    var labels = data.period_labels || periods;
    var positions = periods.map(function (_, index) { return index; });
    var incomePositions = positions.map(function (position) { return position - 0.2; });
    var expensePositions = positions.map(function (position) { return position + 0.2; });
    var capex = data.expense_capex || positions.map(function () { return 0; });
    var opex = data.expense_opex || positions.map(function (_, index) { return Number(data.expense_recurring[index] || 0) + Number(data.expense_one_off[index] || 0); });
    var colors = window.CEQWAChartColors();
    var separator = window.CEQWAChartSeparator();

    window.CEQWAAccessibleTable('table-income-expense', 'Income and expenses by source period', ['Source period', 'Recurring income', 'One-off income', 'Recurring expenses', 'One-off expenses'], labels.map(function (label, i) { return [label, money(data.income_recurring[i]), money(data.income_one_off[i]), money(data.expense_recurring[i]), money(data.expense_one_off[i])]; }));
    window.CEQWAAccessibleTable('table-expense-recurring', 'Recurring expenses by category', ['Category', 'Amount'], data.expense_recurring_breakdown.map(function (row) { return [row.category, money(row.amount)]; }));
    window.CEQWAAccessibleTable('table-expense-oneoff', 'One-off expenses by category', ['Category', 'Amount'], data.expense_one_off_breakdown.map(function (row) { return [row.category, money(row.amount)]; }));
    window.CEQWAAccessibleTable('table-capex-opex', 'CAPEX and OPEX by source period', ['Source period', 'CAPEX', 'OPEX'], labels.map(function (label, i) { return [label, money(capex[i]), money(opex[i])]; }));
    window.CEQWAAccessibleTable('table-balance', 'Closing balance by source period', ['Source period', 'Closing balance'], labels.map(function (label, i) { return [label, money(data.closing_balance[i])]; }));

    Plotly.newPlot('chart-income-expense', [
      { name: 'Income: Recurring', type: 'bar', x: incomePositions, y: data.income_recurring, customdata: labels, hovertemplate: '%{customdata}<br>Income: Recurring: Rs. %{y:,.0f}<extra></extra>', width: 0.35, marker: { color: colors[2], line: { color: separator, width: 1 } } },
      { name: 'Income: One-off', type: 'bar', x: incomePositions, y: data.income_one_off, customdata: labels, hovertemplate: '%{customdata}<br>Income: One-off: Rs. %{y:,.0f}<extra></extra>', width: 0.35, marker: { color: colors[1], line: { color: separator, width: 1 } } },
      { name: 'Expenses: Recurring', type: 'bar', x: expensePositions, y: data.expense_recurring, customdata: labels, hovertemplate: '%{customdata}<br>Expenses: Recurring: Rs. %{y:,.0f}<extra></extra>', width: 0.35, marker: { color: colors[0], line: { color: separator, width: 1 } } },
      { name: 'Expenses: One-off', type: 'bar', x: expensePositions, y: data.expense_one_off, customdata: labels, hovertemplate: '%{customdata}<br>Expenses: One-off: Rs. %{y:,.0f}<extra></extra>', width: 0.35, marker: { color: colors[4], line: { color: separator, width: 1 } } }
    ], window.CEQWAChartLayout({ barmode: 'stack', margin: { t: 20, r: 20, b: 60, l: 60 }, yaxis: { title: 'Amount (Rs.)' }, xaxis: { tickmode: 'array', tickvals: positions, ticktext: labels }, legend: { orientation: 'h', y: 1.08 } }), { responsive: true });
    renderPie('chart-expense-recurring', data.expense_recurring_breakdown);
    renderPie('chart-expense-oneoff', data.expense_one_off_breakdown);
    Plotly.newPlot('chart-capex-opex', [{ name: 'CAPEX', type: 'bar', x: labels, y: capex, marker: { color: colors[3], line: { color: separator, width: 1 } }, hovertemplate: '%{x}<br>CAPEX: Rs. %{y:,.0f}<extra></extra>' }, { name: 'OPEX', type: 'bar', x: labels, y: opex, marker: { color: colors[1], line: { color: separator, width: 1 } }, hovertemplate: '%{x}<br>OPEX: Rs. %{y:,.0f}<extra></extra>' }], window.CEQWAChartLayout({ barmode: 'group', margin: { t: 20, r: 20, b: 70, l: 60 }, yaxis: { title: 'Amount (Rs.)' }, legend: { orientation: 'h', y: 1.08 } }), { responsive: true });
    Plotly.newPlot('chart-balance', [{ type: 'scatter', mode: 'lines+markers', x: labels, y: data.closing_balance, line: { color: colors[0], width: 3 }, marker: { size: 8, color: colors[0], line: { color: separator, width: 1.5 } }, hovertemplate: '%{x}<br>Closing balance: Rs. %{y:,.0f}<extra></extra>' }], window.CEQWAChartLayout({ margin: { t: 20, r: 20, b: 60, l: 60 }, yaxis: { title: 'Closing Balance (Rs.)' } }), { responsive: true });
  }

  document.addEventListener('DOMContentLoaded', function () {
    setupTabs();
    fetch('data/financials-dashboard.json')
      .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
      .then(function (data) { dashboardData = data; renderCharts(data); })
      .catch(function () {
        document.querySelectorAll('#panel-dashboard .chart').forEach(function (chart) { chart.textContent = 'Chart unavailable. Use “View chart data” below.'; });
      });
  });

  window.addEventListener('ceqwa:themechange', function () {
    if (dashboardData) renderCharts(dashboardData);
  });
})();
