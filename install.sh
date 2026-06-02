#!/bin/bash
set -eu

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)
SERVICE_NAME=$(basename "$SCRIPT_DIR")

# The mr-manuel style expects the driver to live in /data/etc/<service>.
# If this installer was run elsewhere, copy it there first and re-run from the final path.
TARGET_DIR="/data/etc/$SERVICE_NAME"
if [ "$SCRIPT_DIR" != "$TARGET_DIR" ]; then
    echo
    echo "Copying $SERVICE_NAME to $TARGET_DIR..."
    mkdir -p /data/etc
    rm -rf "$TARGET_DIR"
    cp -a "$SCRIPT_DIR" "$TARGET_DIR"
    chmod 755 "$TARGET_DIR/install.sh"
    exec bash "$TARGET_DIR/install.sh"
fi

echo
echo "Installing $SERVICE_NAME..."

if [ ! -f "$SCRIPT_DIR/config.ini" ]; then
    echo "Creating config.ini from config.sample.ini..."
    cp "$SCRIPT_DIR/config.sample.ini" "$SCRIPT_DIR/config.ini"
fi

# set permissions for script files
echo "Setting permissions..."
chmod 755 "$SCRIPT_DIR"/*.py
chmod 755 "$SCRIPT_DIR"/*.sh
chmod 755 "$SCRIPT_DIR"/tools/*.py
chmod 755 "$SCRIPT_DIR/service/run"
chmod 755 "$SCRIPT_DIR/service/log/run"

# create symlink to run script in daemon
SERVICE_LINK="/service/$SERVICE_NAME"
if [ -L "$SERVICE_LINK" ]; then
    CURRENT_TARGET=$(readlink "$SERVICE_LINK")
    if [ "$CURRENT_TARGET" != "$SCRIPT_DIR/service" ]; then
        echo "Updating existing service link..."
        rm -f "$SERVICE_LINK"
        ln -s "$SCRIPT_DIR/service" "$SERVICE_LINK"
    else
        echo "Service already exists."
    fi
elif [ -e "$SERVICE_LINK" ]; then
    echo "ERROR: $SERVICE_LINK exists and is not a symlink."
    exit 1
else
    echo "Creating service..."
    ln -s "$SCRIPT_DIR/service" "$SERVICE_LINK"
fi

# add install-script to rc.local to be ready for firmware update
filename=/data/rc.local
if [ ! -f "$filename" ]; then
    touch "$filename"
    chmod 755 "$filename"
    echo "#!/bin/bash" >> "$filename"
    echo >> "$filename"
fi

# if not already added, then add to rc.local
grep -qxF "bash $SCRIPT_DIR/install.sh" "$filename" || echo "bash $SCRIPT_DIR/install.sh" >> "$filename"

echo "Restarting service..."
if command -v svc >/dev/null 2>&1; then
    svc -t "/service/$SERVICE_NAME" 2>/dev/null || true
    svc -u "/service/$SERVICE_NAME" 2>/dev/null || true
fi

echo
echo "Done."
echo
echo "Config:"
echo "nano $SCRIPT_DIR/config.ini"
echo
echo "Status:"
echo "svstat /service/$SERVICE_NAME"
echo
echo "Logs:"
echo "tail -f /var/log/$SERVICE_NAME/current"
echo
