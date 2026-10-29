#!/bin/sh
# Install Noggin as a background service plus an app launcher.
#
#   - ~/.config/systemd/user/noggin-server.service, enabled and started
#   - ~/.local/share/applications/noggin.desktop, which runs launch.sh to open
#     Noggin in its own browser window
#
# Safe to re-run: it overwrites both files and restarts the service, so it is
# also how you pick up a moved checkout. Undo with: ./install.sh --uninstall
set -eu

DIR=$(cd "$(dirname "$0")" && pwd)
UNIT_DIR="$HOME/.config/systemd/user"
APP_DIR="$HOME/.local/share/applications"
UNIT="$UNIT_DIR/noggin-server.service"
DESKTOP="$APP_DIR/noggin.desktop"

if [ "${1:-}" = "--uninstall" ]; then
    systemctl --user disable --now noggin-server.service 2>/dev/null || true
    rm -f "$UNIT" "$DESKTOP"
    systemctl --user daemon-reload
    update-desktop-database "$APP_DIR" 2>/dev/null || true
    echo "noggin: service and launcher removed (maps in ~/.local/share/noggin are kept)"
    exit 0
fi

mkdir -p "$UNIT_DIR" "$APP_DIR"

cat > "$UNIT" <<EOF
[Unit]
Description=Noggin — a simple mind map tool
After=network.target
# A taken port makes server.py exit 1; give up after 5 tries rather than flap.
StartLimitIntervalSec=300
StartLimitBurst=5

[Service]
Type=simple
WorkingDirectory=$DIR
ExecStart=$(command -v python3) $DIR/server.py --port 8791 --no-browser
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF

sed -e "/^#/d" -e "s|@DIR@|$DIR|g" "$DIR/noggin.desktop" > "$DESKTOP"

systemctl --user daemon-reload
systemctl --user enable noggin-server.service
systemctl --user restart noggin-server.service
update-desktop-database "$APP_DIR" 2>/dev/null || true

echo "noggin: service running at http://127.0.0.1:8791"
echo "noggin: launcher installed — look for \"Noggin\" in your app launcher"
