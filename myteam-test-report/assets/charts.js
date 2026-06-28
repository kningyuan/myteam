(function() {
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var accent2 = style.getPropertyValue('--accent2').trim();
  var ink = style.getPropertyValue('--ink').trim();
  var muted = style.getPropertyValue('--muted').trim();
  var rule = style.getPropertyValue('--rule').trim();
  var bg2 = style.getPropertyValue('--bg2').trim();
  var warn = style.getPropertyValue('--warn').trim();

  // --- Chart: Token Consumption by Task ---
  var chart1 = echarts.init(document.getElementById('chart-tokens'), null, { renderer: 'svg' });
  chart1.setOption({
    animation: false,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      appendToBody: true,
      formatter: function(params) {
        var p = params[0];
        return p.name + '<br/>Token: ' + parseInt(p.value).toLocaleString();
      }
    },
    grid: { left: '3%', right: '4%', bottom: '15%', top: '5%', containLabel: true },
    xAxis: {
      type: 'category',
      data: [
        'step-collect\n(已拆分)',
        'step-collect.cursor',
        'step-collect.windsurf',
        'step-collect.github-copilot',
        'step-compare',
        'step-plan',
        'step-review\n(卡住)'
      ],
      axisLabel: {
        color: muted,
        fontSize: 10,
        interval: 0,
        rotate: 25
      },
      axisLine: { lineStyle: { color: rule } }
    },
    yAxis: {
      type: 'value',
      name: 'Token',
      nameTextStyle: { color: muted, fontSize: 11 },
      axisLabel: {
        color: muted,
        formatter: function(v) { return (v / 1000) + 'K'; }
      },
      splitLine: { lineStyle: { color: rule, type: 'dashed' } },
      axisLine: { lineStyle: { color: rule } }
    },
    series: [{
      type: 'bar',
      data: [
        { value: 97123, itemStyle: { color: muted } },
        { value: 257165, itemStyle: { color: accent2 } },
        { value: 238386, itemStyle: { color: accent2 } },
        { value: 251551, itemStyle: { color: accent2 } },
        { value: 212128, itemStyle: { color: accent2 } },
        { value: 170164, itemStyle: { color: accent2 } },
        { value: 46960, itemStyle: { color: warn } }
      ],
      barWidth: '50%',
      label: {
        show: true,
        position: 'top',
        color: ink,
        fontSize: 10,
        formatter: function(p) { return (p.value / 1000).toFixed(0) + 'K'; }
      }
    }]
  });
  window.addEventListener('resize', function() { chart1.resize(); });
})();
