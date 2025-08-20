from ina219 import INA219

class INA219Reader:
    def __init__(self, shunt_ohms=0.1, address=0x43):
        self.ina = INA219(shunt_ohms, address=address)
        self.ina.configure()

    def read(self):
        try:
            v_bus = self.ina.voltage()                 # V
            shunt_v = self.ina.shunt_voltage() / 1000  # mV->V
            current_a = self.ina.current() / 1000.0    # mA->A
            power_w = self.ina.power()                 # W
            return dict(bus_voltage_v=v_bus, shunt_voltage_v=shunt_v, current_a=current_a, power_w=power_w)
        except Exception:
            return dict()