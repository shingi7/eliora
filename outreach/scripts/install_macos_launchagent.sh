#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
OUTREACH_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
REPO_ROOT=$(CDPATH= cd -- "$OUTREACH_ROOT/.." && pwd)
PYTHON_BIN="${ELIORA_OUTREACH_PYTHON:-$OUTREACH_ROOT/.venv/bin/python}"
LOG_DIR="${ELIORA_OUTREACH_LOG_DIR:-$HOME/Library/Logs/eliora-outreach}"
AGENT_DIR="$HOME/Library/LaunchAgents"
PLIST="$AGENT_DIR/com.eliora.outreach.plist"
LABEL="com.eliora.outreach"

if [ ! -x "$PYTHON_BIN" ]; then
  echo "Missing $PYTHON_BIN. Create outreach/.venv and install outreach first." >&2
  exit 1
fi
mkdir -p "$AGENT_DIR" "$LOG_DIR"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>$LABEL</string>
<key>ProgramArguments</key><array><string>$PYTHON_BIN</string><string>-m</string><string>eliora_outreach</string><string>run-if-due</string></array>
<key>WorkingDirectory</key><string>$REPO_ROOT</string>
<key>RunAtLoad</key><true/>
<key>StartInterval</key><integer>3600</integer>
<key>StandardOutPath</key><string>$LOG_DIR/stdout.log</string>
<key>StandardErrorPath</key><string>$LOG_DIR/stderr.log</string>
</dict></plist>
EOF
if command -v plutil >/dev/null 2>&1; then plutil -lint "$PLIST"; fi
DOMAIN="gui/$(id -u)"
launchctl bootout "$DOMAIN/$LABEL" >/dev/null 2>&1 || true
if launchctl bootstrap "$DOMAIN" "$PLIST" 2>/dev/null; then
  launchctl kickstart -k "$DOMAIN/$LABEL" >/dev/null 2>&1 || true
else
  launchctl load -w "$PLIST"
fi
echo "Installed $LABEL with RunAtLoad and hourly checks."
