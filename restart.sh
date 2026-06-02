#!/bin/sh
set -eu

SERVICE_NAME=$(basename "$(pwd)")
svc -t "/service/${SERVICE_NAME}" 2>/dev/null || true
svstat "/service/${SERVICE_NAME}"
