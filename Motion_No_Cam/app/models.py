import sqlite3, time, json
from typing import Any, Dict
from .config import DB_PATH

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def kv_get(key: str, default: str = None):
    c = get_conn()
    try:
        row = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default
    finally:
        c.close()

def kv_set_many(pairs: Dict[str, Any]):
    c = get_conn()
    try:
        c.executemany("INSERT INTO settings(key,value) VALUES(?,?) "
                      "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                      [(k, str(v)) for k,v in pairs.items()])
        c.commit()
    finally:
        c.close()

def kv_all():
    c = get_conn()
    try:
        rows = c.execute("SELECT key,value FROM settings").fetchall()
        return {r["key"]: r["value"] for r in rows}
    finally:
        c.close()

def insert_sample(**kwargs):
    c = get_conn()
    try:
        fields = ",".join(kwargs.keys())
        qs = ",".join(["?"]*len(kwargs))
        c.execute(f"INSERT INTO samples(ts,{fields}) VALUES(?,{qs})", (int(time.time()), *kwargs.values()))
        c.commit()
    finally:
        c.close()

def insert_event(kind: str, payload: Dict[str,Any]):
    c = get_conn()
    try:
        c.execute("INSERT INTO events(ts,kind,payload) VALUES(?,?,?)",
                  (int(time.time()), kind, json.dumps(payload)))
        c.commit()
    finally:
        c.close()

def rollup_minute(battery_pct, voltage_v, current_a, power_w, distance_m):
    ts_min = int(time.time() // 60 * 60)
    c = get_conn()
    try:
        c.execute("INSERT OR REPLACE INTO metrics_battery_minute(ts,pct,voltage_v,current_a,power_w) "
                  "VALUES(?,?,?,?,?)", (ts_min, battery_pct, voltage_v, current_a, power_w))
        c.execute("INSERT OR REPLACE INTO metrics_distance_minute(ts,distance_m) VALUES(?,?)",
                  (ts_min, distance_m))
        c.commit()
    finally:
        c.close()

def history(metric: str, minutes: int = 180):
    since = int(time.time()) - minutes*60
    c = get_conn()
    try:
        if metric == "battery":
            rows = c.execute("SELECT ts,pct,voltage_v,current_a,power_w FROM metrics_battery_minute WHERE ts>=? ORDER BY ts", (since,)).fetchall()
            return [dict(r) for r in rows]
        if metric == "distance":
            rows = c.execute("SELECT ts,distance_m FROM metrics_distance_minute WHERE ts>=? ORDER BY ts", (since,)).fetchall()
            return [dict(r) for r in rows]
        return []
    finally:
        c.close()