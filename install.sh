#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------
# Config (change if you use a different fork/branch)
# ---------------------------------------
REPO_URL="${REPO_URL:-https://github.com/soler2000/Motion_No_Cam.git}"
BRANCH="${BRANCH:-Instal-1}"
APP_DIR="/opt/Motion_No_Cam"
PY_BIN="/usr/bin/python3"
VENVDIR="${APP_DIR}/venv"
SERVICE_NAME="motion_wide.service"
DB_PATH="${APP_DIR}/motion.db"

# ---------------------------------------
# Root check
# ---------------------------------------
if [[ $EUID -ne 0 ]]; then
  echo "[!] Please run as root (sudo -i then rerun)."
  exit 1
fi

echo "[+] APT update / base packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y \
  git curl ca-certificates \
  python3 python3-venv python3-pip python3-dev \
  build-essential \
  sqlite3 \
  i2c-tools raspi-config \
  network-manager

echo "[+] Ensure NetworkManager enabled (ok if already running)"
systemctl enable NetworkManager || true
systemctl start  NetworkManager || true

# ---------------------------------------
# I2C preflight
# ---------------------------------------
if [[ ! -e /dev/i2c-1 ]]; then
  echo "[!] /dev/i2c-1 missing. Enabling I2C then you MUST reboot:"
  raspi-config nonint do_i2c 0 || true
  echo "    Now run:  sudo reboot"
  exit 0
fi

# ---------------------------------------
# Deploy app under /opt (root-owned)
# ---------------------------------------
echo "[+] Create ${APP_DIR}"
mkdir -p "${APP_DIR}"
# If not a git repo yet, clone fresh; else fetch/switch.
if [[ ! -d "${APP_DIR}/.git" ]]; then
  echo "[+] Cloning ${REPO_URL} (branch ${BRANCH})"
  git clone --branch "${BRANCH}" --single-branch "${REPO_URL}" "${APP_DIR}"
else
  echo "[+] Repo already present; fetching latest ${BRANCH}"
  git -C "${APP_DIR}" fetch origin
  git -C "${APP_DIR}" checkout "${BRANCH}"
  git -C "${APP_DIR}" reset --hard "origin/${BRANCH}"
  git -C "${APP_DIR}" clean -fd
fi

# Make sure root owns the tree
chown -R root:root "${APP_DIR}"

# ---------------------------------------
# Python venv + deps
# ---------------------------------------
echo "[+] Python venv & dependencies"
if [[ ! -d "${VENVDIR}" ]]; then
  "${PY_BIN}" -m venv "${VENVDIR}"
fi
# Always upgrade pip/setuptools/wheel for smoother builds
"${VENVDIR}/bin/pip" install --upgrade pip setuptools wheel

REQ_FILE="${APP_DIR}/requirements.txt"
if [[ -f "${REQ_FILE}" ]]; then
  echo "[+] Installing requirements.txt"
  "${VENVDIR}/bin/pip" install -r "${REQ_FILE}"
else
  echo "[!] requirements.txt not found; installing minimal known deps"
  "${VENVDIR}/bin/pip" install flask jinja2 waitress psutil ina219 adafruit-blinka
fi

# ---------------------------------------
# Ensure DB path exists and is writable by root
# ---------------------------------------
echo "[+] Preparing DB path ${DB_PATH}"
touch "${DB_PATH}"
chown root:root "${DB_PATH}"
chmod 0644 "${DB_PATH}"

# ---------------------------------------
# systemd unit
# ---------------------------------------
UNIT_FILE="/etc/systemd/system/${SERVICE_NAME}"
echo "[+] Writing ${UNIT_FILE}"
cat > "${UNIT_FILE}" <<UNIT
# ${SERVICE_NAME}
[Unit]
Description=Motion_No_Cam Flask Service
After=network-online.target i2c-dev.service
Wants=network-online.target i2c-dev.service

[Service]
Type=simple
User=root
WorkingDirectory=${APP_DIR}
Environment=FLASK_ENV=production
Environment=MOTION_DB=${DB_PATH}
# Run DB migrations first (must succeed but be harmless if up-to-date)
ExecStartPre=${VENVDIR}/bin/python -m app.migrations
# wait for /dev/i2c-1 to appear (race guard)
ExecStartPre=/bin/sh -c 'for i in \$(seq 1 10); do [ -e /dev/i2c-1 ] && exit 0; sleep 1; done; exit 1'
ExecStart=${VENVDIR}/bin/python -m app.main
Restart=on-failure
AmbientCapabilities=CAP_NET_ADMIN
NoNewPrivileges=false

[Install]
WantedBy=multi-user.target
UNIT

echo "[+] systemd reload/enable/start"
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"
systemctl restart "${SERVICE_NAME}"

echo "[✓] Install complete."
echo "    Status:   systemctl status ${SERVICE_NAME} -n 100 --no-pager"
echo "    Web UI:   http://<this-pi-ip>:5000/"
