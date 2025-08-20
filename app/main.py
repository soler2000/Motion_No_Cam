from flask import Flask, jsonify, request, render_template
from .config import HOST, PORT, POLL_INTERVAL_S
from .models import kv_get, kv_set_many, kv_all, history
from .threads import STATE, start_all, stop_all, request_settings_reload
from .hw import netmgr
import signal, sys

app = Flask(__name__, template_folder="web/templates", static_folder="web/static")

@app.route("/")
def dashboard():
    return render_template("dashboard.html", poll=POLL_INTERVAL_S)

@app.route("/reversing")
def reversing():
    return render_template("reversing.html", poll=POLL_INTERVAL_S)

@app.route("/settings")
def settings():
    all_kv = kv_all()
    return render_template("settings.html", settings=all_kv)

@app.get("/api/stats")
def api_stats():
    s = dict(STATE)
    # Tidy rounding for UI
    if s.get("distance_m") is not None:
        s["distance_m"] = round(s["distance_m"], 1)
    if s.get("bus_voltage_v") is not None:
        s["bus_voltage_v"] = round(s["bus_voltage_v"], 2)
    if s.get("current_a") is not None:
        s["current_a"] = round(s["current_a"], 2)
    if s.get("power_w") is not None:
        s["power_w"] = round(s["power_w"], 2)
    return jsonify(s)

@app.get("/api/history")
def api_history():
    metric = request.args.get("metric","battery")
    minutes = int(request.args.get("minutes","180"))
    return jsonify(history(metric, minutes))

@app.post("/api/settings")
def api_settings():
    data = request.get_json(force=True) or {}
    kv_set_many(data)
    # >>> HOT RELOAD: tell background threads to re-read settings immediately
    request_settings_reload()
    return jsonify({"ok": True, "reloaded": True})

@app.post("/api/led/test")
def api_led_test():
    return jsonify({"ok": True})

@app.post("/api/wifi/scan")
def api_wifi_scan():
    nets = netmgr.scan_networks()
    return jsonify(nets)

@app.post("/api/wifi/connect")
def api_wifi_connect():
    data = request.get_json(force=True) or {}
    ssid = data.get("ssid","")
    password = data.get("password","")
    ok = netmgr.connect_wifi(ssid, password)
    return jsonify({"ok": ok})

def _graceful(*_):
    stop_all()
    sys.exit(0)

def run():
    start_all()
    signal.signal(signal.SIGTERM, _graceful)
    signal.signal(signal.SIGINT, _graceful)
    # Waitress serves production
    from waitress import serve
    serve(app, host=HOST, port=PORT)

if __name__ == "__main__":
    run()
