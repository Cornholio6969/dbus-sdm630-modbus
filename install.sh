#!/bin/sh
set -eu

SERVICE_NAME="dbus-sdm630-modbus"
REPO_OWNER="Cornholio6969"
REPO_NAME="dbus-sdm630-modbus"
REPO_BRANCH="master"
ARCHIVE_URL="https://github.com/${REPO_OWNER}/${REPO_NAME}/archive/refs/heads/${REPO_BRANCH}.tar.gz"
TARGET_DIR="/data/etc/${SERVICE_NAME}"

download_file() {
    url="$1"
    output="$2"

    if command -v curl >/dev/null 2>&1; then
        curl -fsSL "$url" -o "$output"
    elif command -v wget >/dev/null 2>&1; then
        wget -qO "$output" "$url"
    else
        echo "ERROR: curl or wget is required for online installation."
        exit 1
    fi
}

script_dir() {
    case "$0" in
        */*)
            dir=$(dirname "$0")
            (cd "$dir" >/dev/null 2>&1 && pwd)
            ;;
        *)
            pwd
            ;;
    esac
}

copy_to_target() {
    source_dir="$1"
    saved_config=""

    echo
    echo "Copying ${SERVICE_NAME} to ${TARGET_DIR}..."

    mkdir -p /data/etc

    if [ -f "${TARGET_DIR}/config.ini" ]; then
        saved_config=$(mktemp "${TMPDIR:-/tmp}/${SERVICE_NAME}.config.XXXXXX")
        cp "${TARGET_DIR}/config.ini" "$saved_config"
    fi

    rm -rf "$TARGET_DIR"
    mkdir -p "$TARGET_DIR"
    cp -a "${source_dir}/." "$TARGET_DIR/"
    rm -rf "${TARGET_DIR}/.git"

    if [ -n "$saved_config" ]; then
        mv "$saved_config" "${TARGET_DIR}/config.ini"
    fi
}

online_install() {
    tmp_dir=$(mktemp -d "${TMPDIR:-/tmp}/${SERVICE_NAME}.XXXXXX")
    trap 'rm -rf "$tmp_dir"' EXIT INT TERM

    archive="${tmp_dir}/repo.tar.gz"

    echo
    echo "Downloading ${REPO_OWNER}/${REPO_NAME} (${REPO_BRANCH})..."
    download_file "$ARCHIVE_URL" "$archive"

    tar -xzf "$archive" -C "$tmp_dir"
    source_dir="${tmp_dir}/${REPO_NAME}-${REPO_BRANCH}"

    if [ ! -f "${source_dir}/install.sh" ]; then
        echo "ERROR: downloaded archive did not contain install.sh."
        exit 1
    fi

    copy_to_target "$source_dir"
    chmod 755 "${TARGET_DIR}/install.sh"
    exec sh "${TARGET_DIR}/install.sh"
}

SCRIPT_DIR=$(script_dir)

if [ ! -f "${SCRIPT_DIR}/config.sample.ini" ] || [ ! -f "${SCRIPT_DIR}/service/run" ]; then
    online_install
fi

if [ "$SCRIPT_DIR" != "$TARGET_DIR" ]; then
    copy_to_target "$SCRIPT_DIR"
    chmod 755 "${TARGET_DIR}/install.sh"
    exec sh "${TARGET_DIR}/install.sh"
fi

echo
echo "Installing ${SERVICE_NAME}..."

if [ ! -f "${SCRIPT_DIR}/config.ini" ]; then
    echo "Creating config.ini from config.sample.ini..."
    cp "${SCRIPT_DIR}/config.sample.ini" "${SCRIPT_DIR}/config.ini"
fi

echo "Setting permissions..."
chmod 755 "${SCRIPT_DIR}"/*.py
chmod 755 "${SCRIPT_DIR}"/*.sh
chmod 755 "${SCRIPT_DIR}"/tools/*.py
chmod 755 "${SCRIPT_DIR}/service/run"
chmod 755 "${SCRIPT_DIR}/service/log/run"

SERVICE_LINK="/service/${SERVICE_NAME}"
if [ -L "$SERVICE_LINK" ]; then
    CURRENT_TARGET=$(readlink "$SERVICE_LINK")
    if [ "$CURRENT_TARGET" != "${SCRIPT_DIR}/service" ]; then
        echo "Updating existing service link..."
        rm -f "$SERVICE_LINK"
        ln -s "${SCRIPT_DIR}/service" "$SERVICE_LINK"
    else
        echo "Service already exists."
    fi
elif [ -e "$SERVICE_LINK" ]; then
    echo "ERROR: ${SERVICE_LINK} exists and is not a symlink."
    exit 1
else
    echo "Creating service..."
    ln -s "${SCRIPT_DIR}/service" "$SERVICE_LINK"
fi

RC_LOCAL="/data/rc.local"
if [ ! -f "$RC_LOCAL" ]; then
    touch "$RC_LOCAL"
    chmod 755 "$RC_LOCAL"
    echo "#!/bin/sh" >> "$RC_LOCAL"
    echo >> "$RC_LOCAL"
fi

sed -i "\#bash ${SCRIPT_DIR}/install.sh#d" "$RC_LOCAL"
grep -qxF "sh ${SCRIPT_DIR}/install.sh" "$RC_LOCAL" || echo "sh ${SCRIPT_DIR}/install.sh" >> "$RC_LOCAL"

echo "Restarting service..."
if command -v svc >/dev/null 2>&1; then
    svc -t "$SERVICE_LINK" 2>/dev/null || true
    svc -u "$SERVICE_LINK" 2>/dev/null || true
fi

echo
echo "Done."
echo
echo "Config:"
echo "nano ${SCRIPT_DIR}/config.ini"
echo
echo "Status:"
echo "svstat ${SERVICE_LINK}"
echo
echo "Logs:"
echo "tail -f /var/log/${SERVICE_NAME}/current"
echo
