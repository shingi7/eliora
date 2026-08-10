#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
OUTREACH_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
PYTHON_BIN="${ELIORA_OUTREACH_PYTHON:-$OUTREACH_ROOT/.venv/bin/python}"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
mkdir -p "$UNIT_DIR"
cat > "$UNIT_DIR/eliora-outreach.service" <<EOF
[Unit]
Description=EliOra local outreach due check

[Service]
Type=oneshot
WorkingDirectory=$OUTREACH_ROOT/..
ExecStart=$PYTHON_BIN -m eliora_outreach run-if-due
EOF
cat > "$UNIT_DIR/eliora-outreach.timer" <<EOF
[Unit]
Description=Hourly EliOra outreach due check

[Timer]
OnBootSec=5m
OnUnitActiveSec=1h
Persistent=true
Unit=eliora-outreach.service

[Install]
WantedBy=timers.target
EOF
systemctl --user daemon-reload
systemctl --user enable --now eliora-outreach.timer
echo "Installed user systemd timer; state is stored outside the repository."
