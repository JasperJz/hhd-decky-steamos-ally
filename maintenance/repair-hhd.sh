#!/bin/sh
# Reinstall the tested versions, then reapply SteamOS compatibility patches.
set -eu
test "$(id -u)" = 0 || { echo 'Run this maintenance command with sudo'; exit 1; }
systemctl stop hhd-power.service
trap 'systemctl start hhd-power.service' EXIT
/home/deck/.local/share/hhd/venv/bin/pip install --force-reinstall --no-deps hhd==4.1.12 adjustor==4.0.1
/home/deck/.local/share/hhd/venv/bin/python /home/deck/.local/share/hhd/maintenance/compatibility.py
echo 'Repaired tested HHD versions and compatibility patches.'
