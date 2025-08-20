import board, busio, adafruit_vl53l1x
from typing import Optional

class VL53L1XReader:
    def __init__(self, address=0x29, timing_budget_ms=50, distance_mode=2):
        self.i2c = busio.I2C(board.SCL, board.SDA, frequency=400000)
        self.tof = adafruit_vl53l1x.VL53L1X(self.i2c, address=address)
        self.tof.distance_mode = distance_mode  # 1 short, 2 long
        self.tof.timing_budget = timing_budget_ms
        self.tof.start_ranging()
        self.last_valid_m: Optional[float] = None

    def read(self):
        try:
            if self.tof.data_ready:
                d_cm = self.tof.distance  # cm
                self.tof.clear_interrupt()
                if d_cm is not None:
                    self.last_valid_m = round(d_cm / 100.0, 3)
            return dict(distance_m=self.last_valid_m, ambient_rate=None)
        except Exception:
            return dict(distance_m=None, ambient_rate=None)

    def close(self):
        try:
            self.tof.stop_ranging()
        except Exception:
            pass