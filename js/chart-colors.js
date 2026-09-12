(function () {
  var paletteSize = 10;
  var startingHue = 210;
  var goldenAngle = 137.508;

  function isDarkTheme() {
    return document.documentElement.getAttribute('data-theme') === 'dark';
  }

  function chartColor(index) {
    var hue = (startingHue + (index * goldenAngle)) % 360;
    var lightness = isDarkTheme() ? 63 : 43;
    return 'hsl(' + hue.toFixed(1) + ', 68%, ' + lightness + '%)';
  }

  window.CEQWAChartColors = function () {
    return Array.from({ length: paletteSize }, function (_, index) { return chartColor(index); });
  };
  window.CEQWAChartColor = function (index) {
    return chartColor(index % paletteSize);
  };
  window.CEQWAChartSeparator = function () {
    return getComputedStyle(document.documentElement).getPropertyValue('--surface').trim();
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
