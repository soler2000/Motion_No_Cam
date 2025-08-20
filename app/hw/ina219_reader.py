from ina219 import INA219

class INA219Reader:
    def __init__(self, shunt_ohms=0.1, address=0x43, busnum=1):
        """
        Force Raspberry Pi I²C bus 1 (/dev/i2c-1). Some versions of pi-ina219 /
        Adafruit_GPIO can't auto-detect on Bookworm; passing bus explicitly avoids
        'Could not determine default I2C bus' errors.
        """
        try:
            self.ina = INA219(shunt_ohms, address=address, busnum=busnum)
        except TypeError:
            self.ina = INA219(shunt_ohms, address=address, i2c_busnum=busnum)
        self.ina.configure()

    def read(self):
        try:
            v_bus = self.ina.voltage()                  # V
            shunt_v = self.ina.shunt_voltage() / 1000.0 # mV -> V
            current_a = self.ina.current() / 1000.0     # mA -> A
            power_w = self.ina.power()                  # W
            return dict(bus_voltage_v=v_bus,
                        shunt_voltage_v=shunt_v,
                        current_a=current_a,
                        power_w=power_w)
        except Exception:
            return dict()
