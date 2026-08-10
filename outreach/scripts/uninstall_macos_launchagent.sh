#!/bin/sh
set -eu
LABEL="com.eliora.outreach"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
DOMAIN="gui/$(id -u)"
launchctl bootout "$DOMAIN/$LABEL" >/dev/null 2>&1 || launchctl unload -w "$PLIST" >/dev/null 2>&1 || true
if [ -f "$PLIST" ]; then rm "$PLIST"; fi
echo "Removed $LABEL scheduler. Logs and private config were preserved."
