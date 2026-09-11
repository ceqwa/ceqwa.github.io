(function () {
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
          if (show) { panel.removeAttribute('hidden'); } else { panel.setAttribute('hidden', ''); }
        });
        if (btn.dataset.tab === 'dashboard' || btn.dataset.tab === 'monthly-dashboard') {
          window.dispatchEvent(new Event('resize'));
        }
      });
    });
  }

  function renderPie(id, breakdown) {
    Plotly.newPlot(id, [{
      type: 'pie',
      labels: breakdown.map(function (e) { return e.category; }),
      values: breakdown.map(function (e) { return e.amount; }),
      hole: 0.4,
      marker: { colors: window.CEQWAChartColors() },
      textinfo: 'percent',
      textposition: 'inside',
      rotation: 45,
      hovertemplate: '%{label}: Rs. %{value:,.0f}<extra></extra>'
    }], window.CEQWAChartLayout({
      margin: { l: 20, r: 20, t: 20, b: 85 },
      automargin: true,
      height: 460,
      legend: { orientation: 'h', x: 0, y: -0.2, font: { size: 10 } }
    }), { responsive: true });
  }

  function renderCharts(data) {
    var barPositions = data.periods.map(function (_, index) { return index; });
    var incomePositions = barPositions.map(function (position) { return position - 0.2; });
    var expensePositions = barPositions.map(function (position) { return position + 0.2; });

    Plotly.newPlot('chart-income-expense', [
      { name: 'Income: Recurring', type: 'bar', x: incomePositions, y: data.income_recurring, customdata: data.periods, hovertemplate: '%{customdata}<br>Income: Recurring: Rs. %{y:,.0f}<extra></extra>', width: 0.35, marker: { color: getComputedStyle(document.documentElement).getPropertyValue('--chart-3').trim() } },
      { name: 'Income: One-off', type: 'bar', x: incomePositions, y: data.income_one_off, customdata: data.periods, hovertemplate: '%{customdata}<br>Income: One-off: Rs. %{y:,.0f}<extra></extra>', width: 0.35, marker: { color: getComputedStyle(document.documentElement).getPropertyValue('--accent').trim() } },
      { name: 'Expenses: Recurring', type: 'bar', x: expensePositions, y: data.expense_recurring, customdata: data.periods, hovertemplate: '%{customdata}<br>Expenses: Recurring: Rs. %{y:,.0f}<extra></extra>', width: 0.35, marker: { color: getComputedStyle(document.documentElement).getPropertyValue('--chart-1').trim() } },
      { name: 'Expenses: One-off', type: 'bar', x: expensePositions, y: data.expense_one_off, customdata: data.periods, hovertemplate: '%{customdata}<br>Expenses: One-off: Rs. %{y:,.0f}<extra></extra>', width: 0.35, marker: { color: getComputedStyle(document.documentElement).getPropertyValue('--chart-5').trim() } }
    ], window.CEQWAChartLayout({
      barmode: 'stack',
      margin: { t: 20, r: 20, b: 40, l: 60 },
      yaxis: { title: 'Amount (Rs.)' },
      xaxis: { tickmode: 'array', tickvals: barPositions, ticktext: data.periods },
      legend: { orientation: 'h', y: 1.08 }
    }), { responsive: true });

    renderPie('chart-expense-recurring', data.expense_recurring_breakdown);
    renderPie('chart-expense-oneoff', data.expense_one_off_breakdown);

    Plotly.newPlot('chart-balance', [{
      type: 'scatter',
      mode: 'lines+markers',
      x: data.periods,
      y: data.closing_balance,
       line: { color: getComputedStyle(document.documentElement).getPropertyValue('--chart-1').trim(), width: 3 },
       marker: { size: 8, color: getComputedStyle(document.documentElement).getPropertyValue('--chart-2').trim() }
    }], window.CEQWAChartLayout({
      margin: { t: 20, r: 20, b: 40, l: 60 },
      yaxis: { title: 'Closing Balance (Rs.)' }
    }), { responsive: true });
  }

  document.addEventListener('DOMContentLoaded', function () {
    setupTabs();
    fetch('data/financials-dashboard.json')
      .then(function (r) { if (!r.ok) { throw new Error('HTTP ' + r.status); } return r.json(); })
      .then(renderCharts)
      .catch(function () {
        var panel = document.querySelector('#panel-dashboard');
        if (panel) {
          panel.innerHTML = '<div class="state-message">Unable to load the financial dashboard. Please try again later.</div>';
        }
      });
  });
})();
