# app/models.py
import os
import json
import sqlite3
from typing import Any, Dict, Iterable, Optional, Tuple
from datetime import datetime, timezone

try:
    from .config import DB_PATH
except Exception:
    DB_PATH = os.environ.get("MOTION_DB", "/opt/Motion_No_Cam/motion.db")


def _ensure_dir(path: str) -> None:
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)


def _conn() -> sqlite3.Connection:
    """
    Return a connection to the main DB.
    Ensures the directory exists and uses WAL for concurrency.
    """
    _ensure_dir(DB_PATH)
    conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


# ---------------------
# settings (key/value)
# ---------------------

def kv_get(key: str, default: Optional[str] = None) -> Optional[str]:
    try:
        with _conn() as c:
            row = c.execute(
                "SELECT value FROM settings WHERE key=?", (key,)
            ).fetchone()
            if row:
                return row["value"]
    except Exception:
        pass
    return default


def kv_set_many(pairs: Iterable[Tuple[str, str]]) -> None:
    with _conn() as c:
        c.executemany(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            list(pairs),
        )


def kv_all() -> Dict[str, str]:
    out: Dict[str, str] = {}
    with _conn() as c:
        for row in c.execute("SELECT key, value FROM settings"):
            out[row["key"]] = row["value"]
    return out


# -------------
# data inserts
# -------------

def _now_ts() -> int:
    # epoch seconds (UTC)
    return int(datetime.now(timezone.utc).timestamp())


def insert_sample(
    *,
    distance_m: Optional[float] = None,
    ambient_rate: Optional[float] = None,
    bus_voltage_v: Optional[float] = None,
    shunt_voltage_v: Optional[float] = None,
    current_a: Optional[float] = None,
    power_w: Optional[float] = None,
) -> None:
    ts = _now_ts()
    with _conn() as c:
        c.execute(
            """
            INSERT INTO samples
            (ts, distance_m, ambient_rate, bus_voltage_v, shunt_voltage_v, current_a, power_w)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (ts, distance_m, ambient_rate, bus_voltage_v, shunt_voltage_v, current_a, power_w),
        )


def insert_event(name: str, payload: Optional[Dict[str, Any]] = None) -> None:
    ts = _now_ts()
    payload_str = json.dumps(payload or {}, separators=(",", ":"), ensure_ascii=False)
    with _conn() as c:
        c.execute(
            "INSERT INTO events(ts, name, payload) VALUES(?, ?, ?)",
            (ts, name, payload_str),
        )


# ---------------
# rollup helpers
# ---------------

def _minute_floor(ts: Optional[int] = None) -> int:
    t = ts or _now_ts()
    return t - (t % 60)


def rollup_minute(
    battery_pct: Optional[float],
    bus_voltage_v: Optional[float],
    current_a: Optional[float],
    power_w: Optional[float],
    distance_m: Optional[float],
) -> None:
    """
    Threads call this roughly once per minute.
    We store the *latest* reading per minute (simple & robust).
    """
    m = _minute_floor()

    with _conn() as c:
        # battery/power metrics
        c.execute(
            """
            INSERT INTO metrics_battery_minute (minute_ts, battery_pct, bus_voltage_v, current_a, power_w)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(minute_ts) DO UPDATE SET
                battery_pct=excluded.battery_pct,
                bus_voltage_v=excluded.bus_voltage_v,
                current_a=excluded.current_a,
                power_w=excluded.power_w
            """,
            (m, battery_pct, bus_voltage_v, current_a, power_w),
        )

        # distance metrics
        c.execute(
            """
            INSERT INTO metrics_distance_minute (minute_ts, distance_m)
            VALUES (?, ?)
            ON CONFLICT(minute_ts) DO UPDATE SET
                distance_m=excluded.distance_m
            """,
            (m, distance_m),
        )
