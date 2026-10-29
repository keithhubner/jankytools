#!/bin/sh
# Open Noggin in its own window, starting the background service if needed.
# This is what the "Noggin" app launcher runs.
URL=http://127.0.0.1:8791/

systemctl --user start noggin-server.service 2>/dev/null || true

# Give a just-started server a moment to bind before the window loads.
if command -v curl >/dev/null 2>&1; then
    i=0
    while [ $i -lt 30 ] && ! curl -sf -o /dev/null "$URL"; do
        sleep 0.1; i=$((i + 1))
    done
fi

# --app (a window with no tabs or URL bar) needs a Chromium-family browser.
for b in brave-browser chromium-browser chromium google-chrome-stable google-chrome; do
    if command -v "$b" >/dev/null 2>&1; then exec "$b" --app="$URL"; fi
done
exec xdg-open "$URL"
