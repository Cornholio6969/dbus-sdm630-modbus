#!/bin/bash
set -eu

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)
SERVICE_NAME=$(basename "$SCRIPT_DIR")

echo "Uninstalling $SERVICE_NAME..."

if command -v svc >/dev/null 2>&1; then
    svc -d "/service/$SERVICE_NAME" 2>/dev/null || true
fi
rm -f "/service/$SERVICE_NAME"

RCLOCAL=/data/rc.local
if [ -f "$RCLOCAL" ]; then
    sed -i "\#bash $SCRIPT_DIR/install.sh#d" "$RCLOCAL"
fi

echo "Done. Remove files manually if wanted: $SCRIPT_DIR"
