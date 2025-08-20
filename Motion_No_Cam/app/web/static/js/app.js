async function fetchJSON(url, opts={}) {
  const res = await fetch(url, Object.assign({headers:{'Content-Type':'application/json'}}, opts));
  return res.json();
}

function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

let batChart;
async function poll() {
  try {
    const s = await fetchJSON('/api/stats');
    setText('distance', s.distance_m?.toFixed ? s.distance_m.toFixed(1) : (s.distance_m ?? '--'));
    setText('rev_distance', s.distance_m?.toFixed ? s.distance_m.toFixed(1)+' m' : '--.- m');
    setText('bus_v', s.bus_voltage_v ?? '--');
    setText('curr_a', s.current_a ?? '--');
    setText('power_w', s.power_w ?? '--');
    setText('bat_pct', s.battery_pct ?? '--');
    setText('wifi', s.wifi_signal ?? '--');
    setText('cpu_t', s.cpu_temp_c ?? '--');
    setText('load1', s.load_1 ?? '--');
    setText('led_mode', s.led_mode ?? '--');
    setText('rev_status', 'LED: '+(s.led_mode ?? '--'));

    if (!batChart) {
      const ctx = document.getElementById('batChart');
      if (ctx) {
        batChart = new Chart(ctx, {
          type: 'line',
          data: { labels: [], datasets: [{ label:'Battery %', data: [] }]},
          options: { responsive:true, animation:false, scales:{ y:{ min:0, max:100 } } }
        });
      }
    }
  } catch(e) { /* ignore */ }
}

async function refreshHistory() {
  try {
    const h = await fetchJSON('/api/history?metric=battery&minutes=180');
    if (batChart) {
      batChart.data.labels = h.map(x => new Date(x.ts*1000).toLocaleTimeString());
      batChart.data.datasets[0].data = h.map(x => x.pct ?? null);
      batChart.update();
    }
  } catch(e) { /* ignore */ }
}

async function savePanel(formId) {
  const form = document.getElementById(formId);
  const data = {};
  for (const el of form.elements) {
    if (!el.name) continue;
    if (el.type === 'checkbox') data[el.name] = el.checked ? 'true' : 'false';
    else data[el.name] = el.value;
  }
  await fetchJSON('/api/settings', { method:'POST', body: JSON.stringify(data) });
  alert('Saved');
}

async function wifiScan() {
  const list = document.getElementById('wifi_list');
  list.innerHTML = '<li>Scanning…</li>';
  const nets = await fetchJSON('/api/wifi/scan', { method:'POST' });
  list.innerHTML = nets.map(n => `<li>${n.ssid} — ${n.signal ?? '--'}% — ${n.security}</li>`).join('');
}

async function wifiConnect() {
  const ssid = document.getElementById('wifi_ssid').value;
  const pass = document.getElementById('wifi_pass').value;
  const res = await fetchJSON('/api/wifi/connect', { method:'POST', body: JSON.stringify({ssid, password:pass}) });
  alert(res.ok ? 'Connect requested' : 'Connect failed');
}

setInterval(poll, (window.POLL ?? 2)*1000);
setInterval(refreshHistory, 15000);
poll(); refreshHistory();