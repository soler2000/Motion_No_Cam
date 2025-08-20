#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
ZIP="$HOME/Motion_No_Cam.zip"
cd "$ROOT/.."
zip -qr "$ZIP" "Motion_No_Cam"
echo "ZIP created at $ZIP"