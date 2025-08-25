import os
import logging
from flask import Flask, jsonify, request, render_template

# Models (DB helpers)
from .models import kv_get, kv_set_many, kv_all

# Threads (hardware + sampling) – degrade gracefully if missing
try:
    from .threads import STATE, start_all, stop_all, request_settings_reload
except Exception:
    STATE = {}
    def start_all(): print("threads: not available; running without background threads")
    def stop_all(): pass
    def request_settings_reload(): pass

# Flask setup
app = Flask(
    __name__,
    static_folder="web/static",
    template_folder="web/templates",
)

log = logging.getLogger("main")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

@app.get("/")
def home():
    return render_template("index.html")

@app.get("/api/state")
def api_state():
    # Minimal base info
    base = {
        "db_path": os.environ.get("MOTION_DB", "/opt/Motion_No_Cam/motion.db"),
    }
    # Merge STATE if present
    try:
        if isinstance(STATE, dict):
            base.update(STATE)
    except Exception:
        pass
    return jsonify(base)

@app.get("/api/settings")
def api_settings_get():
    return jsonify(kv_all())

@app.post("/api/settings")
def api_settings_set():
    data = request.get_json(force=True, silent=True) or {}
    # Accept dict or list of {key,value}
    if isinstance(data, list):
        data = {
            item["key"]: item.get("value")
            for item in data
            if isinstance(item, dict) and "key" in item
        }
    kv_set_many(data)
    request_settings_reload()
    return jsonify({"ok": True})

@app.post("/api/reload")
def api_reload():
    request_settings_reload()
    return jsonify({"ok": True})

def run():
    log.info("Starting background threads (if available)...")
    try:
        start_all()
        log.info("Background threads started")
    except Exception as e:
        log.exception("Failed to start background threads: %s", e)

    host = "0.0.0.0"
    port = int(os.environ.get("PORT", "5000"))
    log.info("Starting Flask on %s:%s", host, port)
    app.run(host=host, port=port, debug=False, use_reloader=False)

if __name__ == "__main__":
    run()
