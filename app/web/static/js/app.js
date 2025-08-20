async function fetchJSON(url, opts={}) {
  const res = await fetch(url, Object.assign({headers:{'Content-Type':'application/json'}}, opts));
  return res.json();
}
function setText(id, val) { const el = document.getElementById(id); if (el) el.textContent = val; }

let batChart;

function ensureChart() {
  const canvas = document.getElementById('batChart');
  if (!canvas || batChart) return;
  const ctx = canvas.getContext('2d');
  batChart = new Chart(ctx, {
    type: 'line',
    data: { labels: [], datasets: [{ label:'Battery %', data: [], borderWidth:2, pointRadius:0, tension:0.2 }]},
    options: {
      responsive: true, animation: false,
      plugins: { legend: { display: true } },
      scales: { y: { min:0, max:100, ticks:{ stepSize:20 } } }
    }
  });
}

function colorForPct(p) {
  if (p === null || p === undefined) return '#9aa6b2';
  if (p < 20) return '#ff4d4f';      // red
  if (p < 50) return '#f0a500';      // amber
  return '#2ecc71';                  // green
}

async function poll() {
  try {
    const s = await fetchJSON('/api/stats');

    // Distance & LED (Dashboard)
    setText('distance', (s.distance_m?.toFixed ? s.distance_m.toFixed(1) : '--.-'));
    setText('led_mode', s.led_mode ?? '--');
    setText('led_mode_dup', s.led_mode ?? '--');

    // Distance & LED (Reversing page)
    if (typeof s.distance_m === 'number') {
      setText('rev_distance', s.distance_m.toFixed(1) + ' m');
    } else {
      setText('rev_distance', '--.- m');
    }
    setText('rev_status', 'LED: ' + (s.led_mode ?? '--'));

    // Battery & power
    setText('bus_v',  s.bus_voltage_v?.toFixed ? s.bus_voltage_v.toFixed(2) : '--');
    setText('curr_a', s.current_a?.toFixed ? s.current_a.toFixed(2) : '--');
    setText('power_w',s.power_w?.toFixed ? s.power_w.toFixed(2) : '--');
    setText('bat_pct', s.battery_pct?.toFixed ? s.battery_pct.toFixed(0) : '--');

    // System
    setText('wifi',   (s.wifi_signal ?? '--'));
    setText('cpu_t',  s.cpu_temp_c?.toFixed ? s.cpu_temp_c.toFixed(1) : '--');

    // Convert load average (1m) to % of cores
    if (typeof s.load_1 === "number") {
      const cores = navigator.hardwareConcurrency || 4;
      const pct = (s.load_1 / cores) * 100;
      setText('load1', pct.toFixed(0) + " %");
    } else {
      setText('load1', '--');
    }

    // Chart
    ensureChart();
    if (batChart && typeof s.battery_pct === 'number') {
      const now = new Date();
      const label = now.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit', second:'2-digit'});
      const ds = batChart.data.datasets[0];
      batChart.data.labels.push(label);
      ds.data.push(s.battery_pct);
      ds.borderColor = colorForPct(s.battery_pct);
      ds.backgroundColor = ds.borderColor + '33';
      if (ds.data.length > 120) {
        ds.data.shift();
        batChart.data.labels.shift();
      }
      batChart.update();
    }
  } catch(e) { /* ignore transient errors */ }
}

async function refreshHistory() {
  const canvas = document.getElementById('batChart');
  if (!canvas) return;
  ensureChart();
  try {
    const h = await fetchJSON('/api/history?metric=battery&minutes=180');
    if (!batChart) return;
    const ds = batChart.data.datasets[0];
    batChart.data.labels = h.map(x => new Date(x.ts*1000).toLocaleTimeString());
    ds.data = h.map(x => x.pct ?? null);
    const last = ds.data.length ? ds.data[ds.data.length-1] : null;
    ds.borderColor = colorForPct(last);
    ds.backgroundColor = ds.borderColor + '33';
    batChart.update();
  } catch(e) { /* ignore */ }
}

setInterval(poll, (window.POLL ?? 2)*1000);
setInterval(refreshHistory, 60000);
poll(); refreshHistory();
