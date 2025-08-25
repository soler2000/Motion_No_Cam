#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/Motion_No_Cam"
VENV="${APP_DIR}/venv"
DB_PATH="${APP_DIR}/motion.db"
SERVICE_FILE="/etc/systemd/system/motion_wide.service"

log() { printf "[+] %s\n" "$*"; }
warn() { printf "[!] %s\n" "$*" >&2; }

# --- Packages ---------------------------------------------------------------
log "APT update & base packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y \
  git python3 python3-venv python3-pip sqlite3 \
  network-manager i2c-tools raspi-config

# --- Enable I²C (idempotent) -----------------------------------------------
log "Enable I2C (ok if already enabled)"
if command -v raspi-config >/dev/null 2>&1; then
  raspi-config nonint do_i2c 0 || true
else
  warn "raspi-config not found; enable I2C manually if needed."
fi

# --- Python venv ------------------------------------------------------------
log "Create venv and install Python deps"
python3 -m venv "${VENV}"
"${VENV}/bin/pip" install --upgrade pip wheel
if [ -f "${APP_DIR}/requirements.txt" ]; then
  "${VENV}/bin/pip" install -r "${APP_DIR}/requirements.txt"
else
  "${VENV}/bin/pip" install flask adafruit-blinka adafruit-circuitpython-vl53l1x adafruit-circuitpython-ina219
fi

# --- One-time DB migration now ---------------------------------------------
log "Run DB migrations now"
chown -R root:root "${APP_DIR}"
chmod -R u+rwX,go+rX "${APP_DIR}"
DB_ENV="MOTION_DB=${DB_PATH}"
env ${DB_ENV} "${VENV}/bin/python" -m app.migrations || {
  warn "Migrations returned non-zero; continuing (service will run them on start too)."
}

# --- Systemd service --------------------------------------------------------
log "Install systemd unit: ${SERVICE_FILE}"
tee "${SERVICE_FILE}" >/dev/null <<UNIT
[Unit]
Description=Motion_No_Cam Flask Service
After=network-online.target i2c-dev.service
Wants=network-online.target i2c-dev.service

[Service]
Type=simple
WorkingDirectory=${APP_DIR}
Environment=FLASK_ENV=production
Environment=MOTION_DB=${DB_PATH}
ExecStartPre=${VENV}/bin/python -m app.migrations
ExecStartPre=/bin/sh -c 'for i in \$(seq 1 10); do [ -e /dev/i2c-1 ] && exit 0; sleep 1; done; exit 1'
ExecStart=${VENV}/bin/python -m app.main
Restart=on-failure
User=root
AmbientCapabilities=CAP_NET_ADMIN
NoNewPrivileges=false

[Install]
WantedBy=multi-user.target
UNIT

# --- Enable + start ---------------------------------------------------------
log "Reload systemd, enable and start service"
systemctl daemon-reload
systemctl enable motion_wide.service
systemctl restart motion_wide.service

log "Done. Check status with:"
echo "  sudo systemctl status motion_wide.service -n 100 --no-pager"
log "Web UI at: http://<pi-ip>:5000"
