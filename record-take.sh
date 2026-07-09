#!/usr/bin/env bash
set -euo pipefail

SCRIPT="${1:?usage: record-take.sh SCRIPT.py [OUTPUT.mp4]}"
OUTPUT="${2:-take.mp4}"

if [ -z "${SCREEN_INDEX:-}" ]; then
  echo "SCREEN_INDEX not set. Available video/screen devices:" >&2
  echo >&2
  ffmpeg -f avfoundation -list_devices true -i "" 2>&1 \
    | sed -n '/AVFoundation video devices:/,/AVFoundation audio devices:/p' \
    | grep -E '\[[0-9]+\]' >&2 || true
  echo >&2
  read -rp "Enter the screen device index to capture: " SCREEN_INDEX
  if ! [[ "${SCREEN_INDEX}" =~ ^[0-9]+$ ]]; then
    echo "Error: SCREEN_INDEX must be a number, got '${SCREEN_INDEX}'" >&2
    exit 1
  fi
fi

# Start the screen capture in the background.
ffmpeg -y -f avfoundation -capture_cursor 1 -framerate 30 \
  -i "${SCREEN_INDEX}:none" "${OUTPUT}" &
FFMPEG_PID=$!

# Give the capture a moment to spin up, then play the script.
sleep 3
scripter play "${SCRIPT}"

# Stop ffmpeg cleanly.
sleep 1
kill -INT "${FFMPEG_PID}"
wait "${FFMPEG_PID}" 2>/dev/null || true

echo "Wrote ${OUTPUT}"
