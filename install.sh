#!/usr/bin/env bash
set -euo pipefail

APP_SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DST_DIR="/opt/Motion_No_Cam"
VENV_DIR="$APP_DST_DIR/venv"
UNIT_PATH="/etc/systemd/system/motion_wide.service"

echo "[+] Apt deps"
sudo apt-get update -y
sudo apt-get install -y python3-venv python3-dev build-essential \
                        network-manager i2c-tools git curl rsync tar

echo "[+] Enable NetworkManager (ok if already on)"
sudo systemctl enable NetworkManager.service --now || true

echo "[+] I2C preflight"
if [ ! -e /dev/i2c-1 ]; then
  echo "[!] /dev/i2c-1 missing. Enable I2C then reboot:"
  echo "    sudo raspi-config nonint do_i2c 0 && sudo reboot"
  exit 1
fi
if command -v i2cdetect >/dev/null 2>&1; then
  if ! i2cdetect -y 1 | grep -q -E '29|43'; then
    echo "[i] Warning: i2cdetect didn't find 0x29 or 0x43 — check wiring/addresses."
  fi
fi

echo "[+] Sync app to $APP_DST_DIR"
sudo mkdir -p "$APP_DST_DIR"
# keep venv if exists, replace code
sudo rsync -a --delete --exclude 'venv' "$APP_SRC_DIR/." "$APP_DST_DIR/."

echo "[+] Python venv + requirements"
if [ ! -d "$VENV_DIR" ]; then
  sudo python3 -m venv "$VENV_DIR"
fi
sudo "$VENV_DIR/bin/pip" install --upgrade pip wheel
if [ -f "$APP_DST_DIR/requirements.txt" ]; then
  sudo "$VENV_DIR/bin/pip" install -r "$APP_DST_DIR/requirements.txt"
fi

echo "[+] Systemd unit for Motion_No_Cam"
sudo tee "$UNIT_PATH" > /dev/null <<'UNIT'
[Unit]
Description=Motion_No_Cam Flask Service
After=network-online.target i2c-dev.service
Wants=network-online.target i2c-dev.service

[Service]
Type=simple
WorkingDirectory=/opt/Motion_No_Cam
Environment=FLASK_ENV=production
ExecStart=/opt/Motion_No_Cam/venv/bin/python -m app.main
Restart=on-failure
User=root
AmbientCapabilities=CAP_NET_ADMIN
NoNewPrivileges=false
# wait for /dev/i2c-1 (race guard)
ExecStartPre=/bin/sh -c 'for i in $(seq 1 10); do [ -e /dev/i2c-1 ] && exit 0; sleep 1; done; exit 1'

[Install]
WantedBy=multi-user.target
UNIT

echo "[+] Reload systemd + (re)start Motion_No_Cam"
sudo systemctl daemon-reload
sudo systemctl enable --now motion_wide.service

###############################################################################
# MediaMTX (WebRTC camera) install / upgrade
###############################################################################
MEDIAMTX_DIR="/opt/mediamtx"
MEDIAMTX_UNIT="/etc/systemd/system/mediamtx.service"
MEDIAMTX_VER="${MEDIAMTX_VER:-v1.12.3}"

echo "[+] Install/Update MediaMTX ($MEDIAMTX_VER)"
ARCH="$(uname -m)"
if [ "$ARCH" = "armv7l" ]; then
  PKG="mediamtx_${MEDIAMTX_VER}_linux_armv7.tar.gz"
elif [ "$ARCH" = "aarch64" ]; then
  PKG="mediamtx_${MEDIAMTX_VER}_linux_arm64.tar.gz"
else
  echo "[!] Unsupported arch: $ARCH (need armv7l or aarch64)"; PKG=""
fi

if [ -n "$PKG" ]; then
  TMPD="$(mktemp -d)"
  pushd "$TMPD" >/dev/null
  # Only (re)download if binary missing or version changed
  NEED_DL=true
  if [ -x "$MEDIAMTX_DIR/mediamtx" ]; then
    CURR_VER="$("$MEDIAMTX_DIR/mediamtx" --version 2>/dev/null || true)"
    case "$CURR_VER" in
      *"$MEDIAMTX_VER"*) NEED_DL=false ;;
    esac
  fi
  if $NEED_DL; then
    echo "[+] Downloading $PKG"
    curl -fL -o "$PKG" "https://github.com/bluenviron/mediamtx/releases/download/${MEDIAMTX_VER}/${PKG}"
    sudo rm -rf "$MEDIAMTX_DIR"
    sudo mkdir -p "$MEDIAMTX_DIR"
    sudo tar -xzf "$PKG" -C "$MEDIAMTX_DIR"
    sudo useradd -r -s /usr/sbin/nologin mediamtx 2>/dev/null || true
    sudo usermod -a -G video mediamtx || true
    sudo chown -R mediamtx:mediamtx "$MEDIAMTX_DIR"
  else
    echo "[i] MediaMTX already at $MEDIAMTX_VER — skip download"
  fi
  popd >/dev/null
  rm -rf "$TMPD"

  echo "[+] Write MediaMTX config"
  sudo tee "$MEDIAMTX_DIR/mediamtx.yml" > /dev/null <<'YML'
logLevel: info
paths:
  reverse:
    source: rpiCamera
    sourceOnDemand: yes
    rpiCameraWidth: 1280
    rpiCameraHeight: 720
    rpiCameraFPS: 30
    rpiCameraBitrate: 1500000
    rpiCameraIDRPeriod: 30
    # rpiCameraHFlip: true
    # rpiCameraVFlip: true
YML

  echo "[+] Systemd unit for MediaMTX"
  sudo tee "$MEDIAMTX_UNIT" > /dev/null <<'SERVICE'
[Unit]
Description=MediaMTX (WebRTC/RTSP/RTMP/HLS) server
After=network-online.target
Wants=network-online.target

[Service]
User=mediamtx
Group=mediamtx
WorkingDirectory=/opt/mediamtx
ExecStart=/opt/mediamtx/mediamtx
Restart=on-failure

[Install]
WantedBy=multi-user.target
SERVICE

  echo "[+] Reload systemd + (re)start MediaMTX"
  sudo systemctl daemon-reload
  sudo systemctl enable --now mediamtx.service
else
  echo "[!] Skipping MediaMTX install due to unsupported arch"
fi

echo "[✓] Install complete."
echo "    App:      http://$(hostname -I | awk '{print $1}'):8080"
echo "    WebRTC:   http://$(hostname -I | awk '{print $1}'):8889/reverse"
