*** a/app/migrations.py
--- b/app/migrations.py
@@
 import sqlite3
-from .config import DB_PATH
+from .config import DB_PATH
 
 SCHEMA = [
     "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);",
     "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);",
     "CREATE TABLE IF NOT EXISTS samples ("
         "ts INTEGER NOT NULL,"
         "distance_m REAL,"
         "ambient_rate REAL,"
         "bus_voltage_v REAL,"
         "shunt_voltage_v REAL,"
         "current_a REAL,"
         "power_w REAL"
     ");",
     "CREATE TABLE IF NOT EXISTS metrics_battery_minute ("
         "minute INTEGER PRIMARY KEY, pct REAL, vbus REAL, current_a REAL, power_w REAL"
     ");",
     "CREATE TABLE IF NOT EXISTS metrics_distance_minute ("
         "minute INTEGER PRIMARY KEY, distance_m REAL"
     ");",
     "CREATE TABLE IF NOT EXISTS events ("
         "ts INTEGER NOT NULL,"
         "name TEXT NOT NULL,"
         "payload TEXT"
     ");",
 ]
 
+DEFAULT_SETTINGS = {
+    "ina219.shunt_ohms": "0.1",
+    "battery.vmin": "6.0",
+    "battery.vmax": "8.4",
+    "battery.capacity_mah": "2000",
+    "warn.distance_threshold_m": "0.6",
+    "warn.freq_min_hz": "0.1",
+    "warn.freq_max_hz": "20",
+    "distance.min_m": "0.05",
+    "distance.max_m": "4.0",
+    "led.master_on": "true",
+    "led.brightness": "0.6",
+    "led.color_white": "#FFFFFF",
+    "led.color_warn": "#FF0000",
+    "ap.ssid": "MotionAP",
+    "ap.password": "change-me-123",
+}
+
 def migrate():
     print("Using DB:", DB_PATH)
     conn = sqlite3.connect(DB_PATH, check_same_thread=False)
     try:
         cur = conn.cursor()
         for stmt in SCHEMA:
             print("Executing:", stmt.split("(")[0].strip())
             cur.execute(stmt)
-        # initialize schema_version if empty
+        # initialize schema_version if empty
         cur.execute("SELECT COUNT(*) FROM schema_version;")
         if cur.fetchone()[0] == 0:
             cur.execute("INSERT INTO schema_version(version) VALUES (1);")
+        # seed defaults idempotently
+        for k, v in DEFAULT_SETTINGS.items():
+            cur.execute(
+                "INSERT OR IGNORE INTO settings(key,value) VALUES (?,?)",
+                (k, v),
+            )
         conn.commit()
     finally:
         conn.close()
 
 if __name__ == "__main__":
     migrate()
