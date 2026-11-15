#!/bin/sh
set -e

SRC="$1"
DEST="/etc/udev/rules.d/99-areyoulowbattery.rules"

if [ -z "$SRC" ] || [ ! -f "$SRC" ]; then
    echo "Error: valid udev rules source file path required." >&2
    exit 1
fi

install -m 0644 "$SRC" "$DEST"
udevadm control --reload
udevadm trigger
exit 0
