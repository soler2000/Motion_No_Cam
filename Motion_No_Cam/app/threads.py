import threading, time, math, psutil, os
from .models import kv_get, insert_sample, rollup_minute, insert_event
from .hw.ina219_reader import INA219Reader
from .hw.vl53l1x_reader import VL53L1XReader
from .hw.neopixel_ring import NeoPixelRing
from .hw import netmgr

STATE = {
  "distance_m": None,
  "battery_pct": None,
  "bus_voltage_v": None,
  "current_a": None,
  "power_w": None,
  "wifi_signal": None,
  "cpu_temp_c": None,
  "load_1": None,
  "led_mode": "off",  # "warn" | "illum" | "off"
}

_stop = threading.Event()
_threads = []

def _read_cpu_temp():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return round(int(f.read().strip())/1000.0, 1)
    except Exception:
        return None

def _battery_pct(v_bus, current_a):
    try:
        v_full = float(kv_get("battery.voltage_full"))
        v_empty = float(kv_get("battery.voltage_empty"))
        r_int = float(kv_get("battery.internal_resistance_ohm"))
        v_rest = v_bus + max(0.0,current_a) * r_int
        pct = (v_rest - v_empty) / (v_full - v_empty)
        return max(0.0, min(1.0, pct))*100.0
    except Exception:
        return None

def sampler_thread():
    ina = INA219Reader(shunt_ohms=float(kv_get("ina219.shunt_ohms")), address=0x43)
    tof = VL53L1XReader(address=0x29)
    alpha_pct = 0.2
    pct_prev = None
    dist_prev = None
    last_rollup_min = 0
    shutdown_v = float(kv_get("battery.shutdown_voltage"))
    while not _stop.is_set():
        power = ina.read()
        dist = tof.read()
        now = int(time.time())
        # CPU + Load
        STATE["cpu_temp_c"] = _read_cpu_temp()
        loads = psutil.getloadavg()
        STATE["load_1"] = round(loads[0],2)
        # Wi-Fi
        STATE["wifi_signal"] = netmgr.wifi_signal()
        # Power
        vbus = power.get("bus_voltage_v")
        STATE["bus_voltage_v"] = vbus
        STATE["current_a"] = power.get("current_a")
        STATE["power_w"] = power.get("power_w")
        # Battery %
        if vbus is not None:
            pct = _battery_pct(vbus, STATE["current_a"] or 0.0)
            if pct is not None:
                pct_prev = pct if pct_prev is None else alpha_pct*pct + (1-alpha_pct)*pct_prev
                STATE["battery_pct"] = round(pct_prev, 1)
        # Distance
        STATE["distance_m"] = dist.get("distance_m")
        # Store sample (1 Hz)
        insert_sample(distance_m=STATE["distance_m"], ambient_rate=(dist.get("ambient_rate") or None),
                      bus_voltage_v=vbus, shunt_voltage_v=power.get("shunt_voltage_v"),
                      current_a=STATE["current_a"], power_w=STATE["power_w"])
        # Motion event detection
        if dist_prev is not None and STATE["distance_m"] is not None:
            dt = 1.0
            approach_rate = (dist_prev - STATE["distance_m"]) / dt
            if approach_rate > 0.3 or (STATE["distance_m"] < float(kv_get("warn.distance_threshold_m"))):
                insert_event("distance_warn", {"distance_m": STATE["distance_m"], "approach_rate": approach_rate})
        dist_prev = STATE["distance_m"]
        # Minute rollup
        m = now // 60
        if m != last_rollup_min:
            last_rollup_min = m
            rollup_minute(STATE["battery_pct"], vbus, STATE["current_a"], STATE["power_w"], STATE["distance_m"])
        # Low-voltage shutdown
        if shutdown_v > 0 and vbus is not None and vbus <= shutdown_v:
            insert_event("low_voltage_shutdown", {"voltage_v": vbus})
            os.system("sudo shutdown -h now")
            time.sleep(10)
        time.sleep(1)

def led_manager_thread():
    ring = NeoPixelRing()
    ring.set_brightness(float(kv_get("led.brightness")))
    ring.set_colors(kv_get("led.color_white"), kv_get("led.color_warn"))
    freq_min = float(kv_get("warn.freq_min_hz")); freq_max = float(kv_get("warn.freq_max_hz"))
    dmin = float(kv_get("distance.min_m")); dmax = float(kv_get("distance.max_m"))
    master_on = kv_get("led.master_on") == "true"
    warn_enabled = kv_get("warn.enabled") == "true"
    phase = 0.0
    last = time.time()
    while not _stop.is_set():
        now = time.time()
        dt = now - last; last = now
        d = STATE["distance_m"]
        if warn_enabled and d is not None:
            d_clamped = max(dmin, min(dmax, d))
            t = (d_clamped - dmin) / (dmax - dmin)  # 0 near → 1 far
            f = freq_min + (1.0 - t) * (freq_max - freq_min)
            f = max(freq_min, min(freq_max, f))
            phase += dt * f
            color = ring.color_white if (int(phase*2) % 2 == 0) else ring.color_warn
            if master_on:
                ring.fill(color)
                STATE["led_mode"] = "warn"
        else:
            if master_on:
                ring.fill(ring.color_white)
                STATE["led_mode"] = "illum"
            else:
                ring.off()
                STATE["led_mode"] = "off"
        time.sleep(0.02)

def netmgr_thread():
    try_seconds = int(kv_get("wifi.try_seconds"))
    ssid = kv_get("wifi.ap_ssid")
    pwd  = kv_get("wifi.ap_password")
    t0 = time.time()
    while time.time() - t0 < try_seconds and not _stop.is_set():
        if netmgr.is_wifi_connected():
            return
        time.sleep(2)
    # Start AP if not connected
    if not netmgr.is_wifi_connected():
        ok = netmgr.ensure_ap(ssid, pwd)
        insert_event("wifi_ap" if ok else "wifi_ap_failed", {"ssid": ssid})

def start_all():
    for target in (sampler_thread, led_manager_thread, netmgr_thread):
        th = threading.Thread(target=target, daemon=True)
        th.start()
        _threads.append(th)

def stop_all():
    _stop.set()
    for th in _threads:
        th.join(timeout=2)