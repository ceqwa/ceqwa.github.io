(function () {
  var names = ['--chart-1', '--chart-2', '--chart-3', '--chart-4', '--chart-5', '--chart-6', '--chart-7', '--chart-8', '--chart-9', '--chart-10'];
  window.CEQWAChartColors = function () {
    var styles = getComputedStyle(document.documentElement);
    return names.map(function (name) { return styles.getPropertyValue(name).trim(); });
  };
  window.CEQWAChartLayout = function (layout) {
    var styles = getComputedStyle(document.documentElement);
    var font = styles.getPropertyValue('--font-main').trim();
    var text = styles.getPropertyValue('--text').trim();
    var muted = styles.getPropertyValue('--text-muted').trim();
    var border = styles.getPropertyValue('--border').trim();
    var surface = styles.getPropertyValue('--surface').trim();
    layout.font = { family: font, size: 12, color: text };
    layout.paper_bgcolor = surface;
    layout.plot_bgcolor = surface;
    ['xaxis', 'yaxis'].forEach(function (axis) {
      if (!layout[axis]) layout[axis] = {};
      layout[axis] = Object.assign({
        gridcolor: border,
        zerolinecolor: border,
        tickfont: { family: font, size: 11, color: muted },
        titlefont: { family: font, size: 12, color: text }
      }, layout[axis]);
    });
    return layout;
  };
})();
