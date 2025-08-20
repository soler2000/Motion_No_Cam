from .models import get_conn, kv_set_many

DEFAULTS = {
  "wifi.ap_ssid": "SensorBoard-AP-XXXX",
  "wifi.ap_password": "change-me-1234",
  "wifi.try_seconds": "30",
  "distance.min_m": "0.2",
  "distance.max_m": "4.0",
  "warn.freq_min_hz": "0.1",
  "warn.freq_max_hz": "20.0",
  "warn.enabled": "true",
  "warn.distance_threshold_m": "1.5",
  "led.master_on": "true",
  "led.brightness": "0.3",
  "led.color_white": "#FFFFFF",
  "led.color_warn": "#FF0000",
  "led.lux_threshold": "50.0",
  "led.ambient_to_lux_factor": "800.0",
  "battery.voltage_full": "4.2",
  "battery.voltage_empty": "3.3",
  "battery.shutdown_voltage": "0",
  "battery.internal_resistance_ohm": "0.15",
  "ina219.shunt_ohms": "0.10",
  "log.retain_days": "14"
}

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS samples (
  ts INTEGER NOT NULL,
  distance_m REAL,
  ambient_rate REAL,
  bus_voltage_v REAL,
  shunt_voltage_v REAL,
  current_a REAL,
  power_w REAL
);
CREATE INDEX IF NOT EXISTS idx_samples_ts ON samples(ts);
CREATE TABLE IF NOT EXISTS metrics_battery_minute (
  ts INTEGER PRIMARY KEY,
  pct REAL, voltage_v REAL, current_a REAL, power_w REAL
);
CREATE TABLE IF NOT EXISTS metrics_distance_minute (
  ts INTEGER PRIMARY KEY, distance_m REAL
);
CREATE TABLE IF NOT EXISTS events (
  ts INTEGER NOT NULL, kind TEXT NOT NULL, payload TEXT
);
"""

def migrate():
    c = get_conn()
    try:
        for stmt in SCHEMA_SQL.strip().split(";"):
            s = stmt.strip()
            if s:
                c.execute(s)
        c.commit()
    finally:
        c.close()
    kv_set_many(DEFAULTS)