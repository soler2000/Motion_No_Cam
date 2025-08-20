#!/usr/bin/env bash
set -euo pipefail

APP_SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DST_DIR="/opt/Motion_No_Cam"
VENV_DIR="$APP_DST_DIR/venv"

echo "[+] Installing apt packages..."
apt-get update -y
apt-get install -y python3-venv python3-dev build-essential \
                   network-manager i2c-tools git curl rsync

systemctl enable NetworkManager.service --now || true
echo "[+] Preflight: checking I2C bus..."

if [ ! -e /dev/i2c-1 ]; then
  echo "[!] /dev/i2c-1 not present. Enable I2C and reboot:";
  echo "    sudo raspi-config nonint do_i2c 0 && sudo reboot";
  exit 1;
fi

if command -v i2cdetect >/dev/null 2>&1; then
  if ! i2cdetect -y 1 | grep -q -E '29|43'; then
    echo "[i] Warning: i2cdetect didn't show 0x29 or 0x43. Check wiring/addresses.";
  fi
fi

echo "[+] Preparing target directory at $APP_DST_DIR"
mkdir -p "$APP_DST_DIR"
# Clean old app files (keep venv if present)
if [ -d "$APP_DST_DIR/app" ]; then
  echo "[i] Removing old app files..."
  find "$APP_DST_DIR/app" -mindepth 1 -delete || true
fi
mkdir -p "$APP_DST_DIR/app" "$APP_DST_DIR/systemd"

echo "[+] Syncing files..."
rsync -a --delete --exclude 'venv' --exclude '.git' --exclude '*.zip' \
  "$APP_SRC_DIR/" "$APP_DST_DIR/"

echo "[+] Python venv..."
if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/pip" install --upgrade pip wheel
"$VENV_DIR/bin/pip" install -r "$APP_DST_DIR/requirements.txt"

echo "[+] Downloading Chart.js for offline charts..."
CHART_JS="$APP_DST_DIR/app/web/static/js/chart.umd.min.js"
mkdir -p "$(dirname "$CHART_JS")"
curl -fsSL "https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js" \
  -o "$CHART_JS" || true

echo "[+] Database migrations..."
"$VENV_DIR/bin/python" - <<'PY'
from app.migrations import migrate
migrate()
print("[i] DB migrated")
PY

echo "[+] Installing systemd service..."
install -m 0644 "$APP_SRC_DIR/systemd/motion_wide.service" /etc/systemd/system/motion_wide.service
systemctl daemon-reload
systemctl enable motion_wide.service
systemctl restart motion_wide.service

echo "[+] Building ZIP artifact..."
cd "$APP_DST_DIR/.."
zip -qr "$HOME/Motion_No_Cam.zip" "Motion_No_Cam"
chown "$(id -u):$(id -g)" "$HOME/Motion_No_Cam.zip" || true

echo "[✓] Done. Visit http://<pi-ip>:8080 (or AP if fallback)."