#!/usr/bin/env bash
set -euo pipefail

LOG_DIR="${LOG_DIR:-/var/log/motion_no_cam}"
LOG_FILE="$LOG_DIR/install_$(date +%Y%m%d_%H%M%S).log"
mkdir -p "$LOG_DIR"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "== Motion_No_Cam installer ($(date)) =="

# --- Preflight ---
if [[ $EUID -ne 0 ]]; then
  echo "Please run with sudo:  sudo ./install.sh"
  exit 1
fi

# Detect Pi + OS
ARCH="$(dpkg --print-architecture || true)"
OS_CODENAME="$(. /etc/os-release && echo "$VERSION_CODENAME")"
echo "Arch: $ARCH | OS: $OS_CODENAME"

if ! command -v python3 >/dev/null; then
  apt-get update
  apt-get install -y python3 python3-venv python3-full
fi

# Enable I2C (safe if repeated)
if command -v raspi-config >/dev/null 2>&1; then
  raspi-config nonint do_i2c 0 || true
fi
adduser pi i2c || true
adduser pi video || true

# --- System deps ---
apt-get update
apt-get install -y git curl ffmpeg libatlas-base-dev

# --- App directory & venv ---
APP_DIR="/home/pi/Motion_No_Cam"
if [[ ! -d "$APP_DIR" ]]; then
  echo "Cloning repo into $APP_DIR"
  sudo -u pi git clone https://github.com/soler2000/Motion_No_Cam.git "$APP_DIR"
else
  echo "Updating existing repo in $APP_DIR"
  pushd "$APP_DIR"
  sudo -u pi git pull --rebase
  popd
fi

cd "$APP_DIR"
if [[ ! -d venv ]]; then
  sudo -u pi python3 -m venv venv
fi
./venv/bin/pip install --upgrade pip wheel setuptools
if [[ -f requirements.txt ]]; then
  ./venv/bin/pip install -r requirements.txt
fi

# --- MediaMTX (for low-latency WebRTC) ---
MEDIAMTX_DIR="/home/pi/mediamtx"
if [[ ! -x "$MEDIAMTX_DIR/mediamtx" ]]; then
  mkdir -p "$MEDIAMTX_DIR"
  pushd "$MEDIAMTX_DIR"
  # auto-pick latest release for arm64/armhf
  case "$ARCH" in
    arm64) URL="https://github.com/bluenviron/mediamtx/releases/latest/download/mediamtx_linux_arm64.tar.gz" ;;
    armhf|arm) URL="https://github.com/bluenviron/mediamtx/releases/latest/download/mediamtx_linux_armv7.tar.gz" ;;
    *) echo "Unknown arch $ARCH for MediaMTX, skipping"; URL="";;
  esac
  if [[ -n "$URL" ]]; then
    curl -L "$URL" | tar xz
    chown -R pi:pi "$MEDIAMTX_DIR"
  fi
  popd
fi

# --- systemd units ---
cat >/etc/systemd/system/mediamtx.service <<'EOF'
[Unit]
Description=MediaMTX (WebRTC/RTSP server)
After=network-online.target
Wants=network-online.target

[Service]
User=pi
Group=pi
ExecStart=/home/pi/mediamtx/mediamtx
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

cat >/etc/systemd/system/motion_no_cam.service <<'EOF'
[Unit]
Description=Motion_No_Cam Flask Service
After=network-online.target mediamtx.service
Wants=network-online.target

[Service]
WorkingDirectory=/home/pi/Motion_No_Cam/app
Environment=PYTHONUNBUFFERED=1
ExecStart=/home/pi/Motion_No_Cam/venv/bin/python app.py
User=pi
Group=pi
# Access to camera/video and I2C without /dev/mem
SupplementaryGroups=video i2c
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now mediamtx.service
systemctl enable --now motion_no_cam.service

echo ""
echo "Install complete."
echo "Logs: $LOG_FILE"
echo "If the app isn't reachable, run:  sudo systemctl status motion_no_cam --no-pager"
