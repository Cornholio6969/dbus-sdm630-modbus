#!/bin/sh
set -eu

SCRIPT_DIR=$(cd "$(dirname "$0")" >/dev/null 2>&1 && pwd)
SERVICE_NAME="dbus-sdm630-modbus"

echo "Uninstalling ${SERVICE_NAME}..."

if command -v svc >/dev/null 2>&1; then
    svc -d "/service/${SERVICE_NAME}" 2>/dev/null || true
fi
rm -f "/service/${SERVICE_NAME}"

RC_LOCAL=/data/rc.local
if [ -f "$RC_LOCAL" ]; then
    sed -i "\#bash ${SCRIPT_DIR}/install.sh#d" "$RC_LOCAL"
    sed -i "\#sh ${SCRIPT_DIR}/install.sh#d" "$RC_LOCAL"
fi

echo "Done. Remove files manually if wanted: ${SCRIPT_DIR}"
