import board, busio, adafruit_vl53l1x
from typing import Optional

class VL53L1XReader:
    """
    Fast VL53L1X reader.
    - timing_budget_ms: 20ms for ~50 Hz measurements (min safe budget on this driver)
    - distance_mode: 1=short (≈1.3 m, better speed/indoor), 2=long (≈3.6 m)
    """
    def __init__(self, address=0x29, timing_budget_ms=20, distance_mode=1):
        # 400 kHz I2C for speed
        self.i2c = busio.I2C(board.SCL, board.SDA, frequency=400000)
        self.tof = adafruit_vl53l1x.VL53L1X(self.i2c, address=address)
        # Configure for speed
        self.tof.distance_mode = distance_mode  # 1=short, 2=long
        self.tof.timing_budget = max(20, min(1000, int(timing_budget_ms)))
        self.tof.start_ranging()
        self.last_valid_m: Optional[float] = None

    def read(self):
        """
        Non-blocking read: returns {'distance_m': float or None, 'ambient_rate': None}
        """
        try:
            if self.tof.data_ready:
                d_cm = self.tof.distance  # cm
                self.tof.clear_interrupt()
                if d_cm is not None:
                    d_m = d_cm / 100.0
                    self.last_valid_m = d_m
            return dict(distance_m=self.last_valid_m, ambient_rate=None)
        except Exception:
            return dict(distance_m=None, ambient_rate=None)

    def close(self):
        try:
            self.tof.stop_ranging()
        except Exception:
            pass
