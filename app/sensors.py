import os, threading, time

USE_SENSORS = os.getenv("USE_SENSORS", "1") == "1"
state = {"distance_m": None, "battery": {"percent": None, "voltage": None}}

def _run():
    if not USE_SENSORS:
        # Simulate values so UI works without hardware
        x = 2.5
        while True:
            state["distance_m"] = max(0.0, x)
            state["battery"] = {"percent": 75, "voltage": 3.9}
            x -= 0.05
            time.sleep(0.2)
        return

    # Real sensors
    try:
        import board, busio
        i2c = busio.I2C(board.SCL, board.SDA)
    except Exception:
        # If I2C not ready, keep trying without crashing the app
        while True:
            time.sleep(1)

    # VL53L1X
    tof = None
    try:
        from adafruit_vl53l1x import VL53L1X
        tof = VL53L1X(i2c)
        tof.start_ranging()
    except Exception:
        tof = None

    # INA219
    ina = None
    try:
        from ina219 import INA219
        ina = INA219(0.1)  # adjust shunt value for your UPS HAT if needed
        ina.configure()
    except Exception:
        ina = None

    while True:
        try:
            if tof:
                dist_mm = tof.distance
                state["distance_m"] = None if dist_mm is None else dist_mm / 1000.0
        except Exception:
            state["distance_m"] = None
        try:
            if ina:
                v = ina.voltage()
                p = int(max(0, min(100, (v - 3.2) / (4.2 - 3.2) * 100)))
                state["battery"] = {"percent": p, "voltage": v}
        except Exception:
            pass
        time.sleep(0.2)

def start():
    t = threading.Thread(target=_run, daemon=True)
    t.start()
