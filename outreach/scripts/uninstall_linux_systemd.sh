#!/bin/sh
set -eu
systemctl --user disable --now eliora-outreach.timer >/dev/null 2>&1 || true
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
rm -f "$UNIT_DIR/eliora-outreach.service" "$UNIT_DIR/eliora-outreach.timer"
systemctl --user daemon-reload
echo "Removed EliOra user systemd timer."
