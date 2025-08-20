# Motion_No_Cam

Flask-based mobile UI for a Pi Zero 2 W sensor board (no camera).  
Sensors: INA219 @ 0x43 (voltage/current/power/battery%), VL53L1X @ 0x29 (distance).  
NeoPixel 16-ring on GPIO18 for illumination and distance warning (0.1–20 Hz).

## Quick start
```bash
# on the Pi (Bookworm)
sudo raspi-config nonint do_i2c 0
git clone https://github.com/soler2000/Motion_No_Cam.git   # or copy this folder
cd Motion_No_Cam
sudo ./install.sh
# browse http://<pi>:8080