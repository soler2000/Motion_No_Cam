import threading, time, psutil, os
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
  "led_mode": "off",
}

_stop = threading.Event()
_reload_settings = threading.Event()
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
        pct = (v_rest - v_empty) / max(0.001, (v_full - v_empty))
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
    while not _stop.is_set():
        power = ina.read()
        dist = tof.read()
        now = int(time.time())
        STATE["cpu_temp_c"] = _read_cpu_temp()
        try:
            loads = psutil.getloadavg()
            STATE["load_1"] = round(loads[0],2)
        except Exception:
            STATE["load_1"] = None
        STATE["wifi_signal"] = netmgr.wifi_signal()
        vbus = power.get("bus_voltage_v")
        STATE["bus_voltage_v"] = vbus
        STATE["current_a"] = power.get("current_a")
        STATE["power_w"] = power.get("power_w")
        if vbus is not None:
            pct = _battery_pct(vbus, STATE["current_a"] or 0.0)
            if pct is not None:
                pct_prev = pct if pct_prev is None else alpha_pct*pct + (1-alpha_pct)*pct_prev
                STATE["battery_pct"] = round(pct_prev, 1)
        STATE["distance_m"] = dist.get("distance_m")
        insert_sample(distance_m=STATE["distance_m"], ambient_rate=None,
                      bus_voltage_v=vbus, shunt_voltage_v=power.get("shunt_voltage_v"),
                      current_a=STATE["current_a"], power_w=STATE["power_w"])
        if dist_prev is not None and STATE["distance_m"] is not None:
            dt = 1.0
            approach_rate = (dist_prev - STATE["distance_m"]) / dt
            if approach_rate > 0.3 or (STATE["distance_m"] < float(kv_get("warn.distance_threshold_m"))):
                insert_event("distance_warn", {"distance_m": STATE["distance_m"], "approach_rate": approach_rate})
        dist_prev = STATE["distance_m"]
        m = now // 60
        if m != last_rollup_min:
            last_rollup_min = m
            rollup_minute(STATE["battery_pct"], vbus, STATE["current_a"], STATE["power_w"], STATE["distance_m"])
        time.sleep(1)

def _load_led_settings(ring):
    try:
        ring.set_brightness(float(kv_get("led.brightness")))
    except Exception:
        pass
    try:
        ring.set_colors(kv_get("led.color_white"), kv_get("led.color_warn"))
    except Exception:
        pass
    return {
        "freq_min": float(kv_get("warn.freq_min_hz")),
        "freq_max": float(kv_get("warn.freq_max_hz")),
        "dmin": float(kv_get("distance.min_m")),
        "dmax": float(kv_get("distance.max_m")),
        "master_on": kv_get("led.master_on") == "true",
        "warn_enabled": kv_get("warn.enabled") == "true",
    }

def led_manager_thread():
    ring = NeoPixelRing()
    cfg = _load_led_settings(ring)
    phase = 0.0
    last = time.time()
    last_poll = 0.0
    while not _stop.is_set():
        now = time.time()
        dt = now - last
        last = now
        if _reload_settings.is_set() or (now - last_poll) > 2.0:
            cfg = _load_led_settings(ring)
            _reload_settings.clear()
            last_poll = now
        d = STATE["distance_m"]
        if cfg["warn_enabled"] and d is not None:
            d_clamped = max(cfg["dmin"], min(cfg["dmax"], d))
            t = (d_clamped - cfg["dmin"]) / max(0.0001, (cfg["dmax"] - cfg["dmin"]))
            f = cfg["freq_min"] + (1.0 - t) * (cfg["freq_max"] - cfg["freq_min"])
            f = max(cfg["freq_min"], min(cfg["freq_max"], f))
            phase += dt * f
            color = ring.color_white if (int(phase*2) % 2 == 0) else ring.color_warn
            if cfg["master_on"]:
                ring.fill(color)
                STATE["led_mode"] = "warn"
            else:
                ring.off()
                STATE["led_mode"] = "off"
        else:
            if cfg["master_on"]:
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

def request_settings_reload():
    _reload_settings.set()
