#!/usr/bin/env bash
set -euo pipefail
test "$(id -u)" = 0 || { echo 'Run with sudo'; exit 1; }
repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
decky_dir="${DECKY_HOME:-/home/deck/homebrew}"
plugin_dir="$decky_dir/plugins/hhd-decky"
test -S /run/hhd/api || { echo 'Start and configure HHD first: /run/hhd/api is missing'; exit 1; }
test -d "$decky_dir/plugins" || { echo 'Decky plugins directory is missing'; exit 1; }
if test -d "$plugin_dir"; then
    backup_dir="$decky_dir/hhd-plugin-backups"
    mkdir -p -- "$backup_dir"
    tar -czf "$backup_dir/hhd-decky-$(date +%Y%m%d-%H%M%S).tar.gz" -C "$decky_dir/plugins" hhd-decky
fi
mkdir -p -- "$plugin_dir/dist"
for name in main.py plugin.json package.json LICENSE; do
    install -m 644 -- "$repo_dir/$name" "$plugin_dir/$name"
done
install -m 644 -- "$repo_dir/dist/index.js" "$plugin_dir/dist/index.js"
echo 'Installed plugin files. Reload this plugin in Decky to apply.'
