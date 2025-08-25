# app/migrations.py
import os
import json
import sqlite3
from datetime import datetime, timezone

try:
    # The repo uses config for DB_PATH
    from .config import DB_PATH
except Exception:
    # Fallback (useful if run standalone)
    DB_PATH = os.environ.get("MOTION_DB", "/opt/Motion_No_Cam/motion.db")


SCHEMA_VERSION = 1

DEFAULT_SETTINGS = {
    # Power / battery
    "ina219.shunt_ohms": "0.1",
    "battery.vmin": "3.0",
    "battery.vmax": "4.2",
    "battery.capacity_mah": "1000",

    # Distance / warnings
    "warn.distance_threshold_m": "0.6",
    "warn.freq_min_hz": "0.1",
    "warn.freq_max_hz": "20",
    "distance.min_m": "0.05",
    "distance.max_m": "4.0",
    "warn.enabled": "true",

    # LEDs
    "led.master_on": "true",
    "led.brightness": "0.6",
    "led.color_white": "#FFFFFF",
    "led.color_warn": "#FF0000",

    # AP / Wi‑Fi (these keys are used by the UI/settings)
    "ap.ssid": "MotionAP",
    "ap.password": "change-me-123",
    "wifi.try_seconds": "20",
}

DDL = [
    # schema version
    """
    CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER NOT NULL
    );
    """,
    # K/V settings
    """
    CREATE TABLE IF NOT EXISTS settings (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """,
    # raw samples (telemetry)
    """
    CREATE TABLE IF NOT EXISTS samples (
        ts               INTEGER NOT NULL,
        distance_m       REAL,
        ambient_rate     REAL,
        bus_voltage_v    REAL,
        shunt_voltage_v  REAL,
        current_a        REAL,
        power_w          REAL
    );
    """,
    # minute rollups (battery/power)
    """
    CREATE TABLE IF NOT EXISTS metrics_battery_minute (
        minute_ts        INTEGER PRIMARY KEY,
        battery_pct      REAL,
        bus_voltage_v    REAL,
        current_a        REAL,
        power_w          REAL
    );
    """,
    # minute rollups (distance)
    """
    CREATE TABLE IF NOT EXISTS metrics_distance_minute (
        minute_ts   INTEGER PRIMARY KEY,
        distance_m  REAL
    );
    """,
    # events (warnings, etc)
    """
    CREATE TABLE IF NOT EXISTS events (
        ts       INTEGER NOT NULL,
        name     TEXT NOT NULL,
        payload  TEXT
    );
    """,
]


def _ensure_dir(path: str) -> None:
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)


def _connect():
    _ensure_dir(DB_PATH)
    conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    for ddl in DDL:
        cur.execute(ddl)

    # seed defaults (INSERT OR IGNORE keeps user’s changes)
    cur.executemany(
        "INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)",
        list(DEFAULT_SETTINGS.items()),
    )

    # set schema version (truncate then insert)
    cur.execute("DELETE FROM schema_version")
    cur.execute("INSERT INTO schema_version(version) VALUES (?)", (SCHEMA_VERSION,))

    conn.commit()


def main():
    print(f"Using DB: {DB_PATH}")
    conn = _connect()
    try:
        migrate(conn)
        v = conn.execute("SELECT version FROM schema_version").fetchone()
        print("Migration complete. schema_version =", v[0] if v else None)
    finally:
        conn.close()


if __name__ == "__main__":
    import sqlite3
    from .config import DB_PATH
    print("Running migrations on", DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    migrate(conn)
    conn.close()
    print("Migrations complete.")
