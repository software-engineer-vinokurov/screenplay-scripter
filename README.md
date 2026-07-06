# screenplay-scripter

Record and replay macOS mouse/keyboard interactions as human-readable Python
scripts. Recordings become plain Python DSL files you can hand-edit, then replay
with smooth, interpolated mouse movement for polished tutorial screen
recordings.

## Why

Screen-recording a tutorial by hand is fiddly: jittery cursor paths, mistimed
clicks, and no way to redo a take cleanly. `scripter` captures your interactions
into an editable script, then replays them deterministically with eased mouse
motion so every take looks intentional.

## Requirements

- macOS
- Python >= 3.12
- [`cliclick`](https://github.com/BlueM/cliclick) — `brew install cliclick`
- [`uv`](https://github.com/astral-sh/uv)

## Install

As a tool (recommended):

```sh
uv tool install --editable .
```

Or add to an existing project / run from the repo:

```sh
uv add screenplay-scripter          # as a dependency
uv sync                             # from a clone
uv run scripter --help
```

## macOS Accessibility permission

`scripter` uses `pynput` to listen for global input events and `cliclick` /
Quartz to synthesize them. macOS gates both behind **Accessibility** permission.

1. Open **System Settings -> Privacy & Security -> Accessibility**.
2. Add and enable the app that runs `scripter` — this is your **terminal**
   (Terminal.app, iTerm2, etc.), not `scripter` itself.
3. If you run through an IDE terminal, grant the IDE the permission.
4. Restart the terminal after granting so the entitlement takes effect.

Without this permission, recording captures nothing and playback silently fails.

## Usage

### Record

```sh
scripter record demo.py
```

Controls while recording:

- **Ctrl+Opt** — toggle recording ON/OFF (the gate). The chord itself is never
  written to the script.
- **Ctrl+C** — end the session, write the script, and open it in `$EDITOR`.

The recorder starts **PAUSED**. Press Ctrl+Opt to arm it, perform your actions,
press Ctrl+Opt again to pause. Pausing lets you reposition between captured
segments without polluting the script.

Suppress automatic `sleep()` insertion between events:

```sh
scripter record demo.py --no-timing
```

### Play

```sh
scripter play demo.py
```

Preview the exact `cliclick` argv without moving the mouse:

```sh
scripter play demo.py --dry-run
```

Override interpolation smoothness (step count per move):

```sh
scripter play demo.py --steps 45
```

Environment equivalents (CLI flags take precedence):

- `SCRIPTER_DRY_RUN=1`
- `SCRIPTER_STEPS=45`

## DSL reference

Every generated script begins with `from scripter import *`. Available calls:

| Function                     | Description                                                    |
| ---------------------------- | ------------------------------------------------------------- |
| `click(x, y)`                | Move to `(x, y)` with interpolation, then left-click.         |
| `right_click(x, y)`          | Move to `(x, y)` with interpolation, then right-click.        |
| `drag(start, end)`           | Press at `start`, drag along interpolated path, release at `end`. |
| `scroll(x, y, amount)`       | Position at `(x, y)`, scroll `amount` lines (Quartz wheel).   |
| `key(*keys)`                 | Key combo. Modifiers (`cmd`, `shift`, `ctrl`, `alt`, `fn`) held around the terminal key, e.g. `key('cmd', 'c')`, `key('return')`. |
| `type_text(text)`            | Type a literal string.                                         |
| `sleep(seconds)`             | Pause for `seconds`.                                          |
| `move(x, y)`                 | Explicitly move the cursor with interpolation (rarely needed; `click` auto-moves). |

Named keys accepted by `key()` include `return`, `space`, `tab`, `esc`,
`arrow-up/down/left/right`, `f1`–`f16`, `page-up`, `page-down`, `home`, `end`,
and more (see `cliclick`'s `kp:` list). Any single character not in that set is
typed with `t:`.

## Editing scripts

Recorded scripts are ordinary Python. Open and tweak them freely:

- Adjust coordinates, reorder actions, or delete takes you do not want.
- Tune `sleep()` values to change pacing.
- Add `--steps` at playback for globally smoother/faster motion, or drop in an
  explicit `move()`.

Playback runs a **warn-only** AST scan first: non-DSL imports or unexpected
function calls are reported to stderr but do not block execution, so you can add
light control flow (`for`, `range`, `print`) when you need it.

Example hand-edited script:

```python
from scripter import *

click(760, 540)
sleep(0.50)
type_text('hello world')
key('return')
for i in range(3):
    scroll(760, 540, -3)
    sleep(0.30)
```

## ffmpeg screen-recording wrapper

Capture the screen with `ffmpeg` while `scripter` drives the UI, so the whole
take is hands-off. Save as `record-take.sh`:

```sh
#!/usr/bin/env bash
set -euo pipefail

SCRIPT="${1:?usage: record-take.sh SCRIPT.py [OUTPUT.mp4]}"
OUTPUT="${2:-take.mp4}"

# List devices to find your screen index:
#   ffmpeg -f avfoundation -list_devices true -i ""
SCREEN_INDEX="${SCREEN_INDEX:-1}"

# Start the screen capture in the background.
ffmpeg -y -f avfoundation -capture_cursor 1 -framerate 30 \
  -i "${SCREEN_INDEX}:none" "${OUTPUT}" &
FFMPEG_PID=$!

# Give the capture a moment to spin up, then play the script.
sleep 1
scripter play "${SCRIPT}"

# Stop ffmpeg cleanly.
sleep 1
kill -INT "${FFMPEG_PID}"
wait "${FFMPEG_PID}" 2>/dev/null || true

echo "Wrote ${OUTPUT}"
```

Run it:

```sh
chmod +x record-take.sh
./record-take.sh demo.py my-tutorial.mp4
```

## Known limitations

- **B1 indicator / unfocused terminal**: If the terminal window is not focused,
  macOS may show a `B1` mouse-button state indicator and some synthesized events
  can be dropped. Keep the target app in focus during playback; drive from a
  background capture rather than clicking into the terminal mid-take.
- **`type_text` caveat**: Typing is synthesized via `cliclick t:`. Characters
  requiring dead keys, IME composition, or non-US layouts may not render as
  expected; prefer ASCII, and use `key()` for special keys.
- **Trackpad scroll fidelity**: Recorded scroll is coarse line-based (`dy`
  coalesced to integer lines). High-resolution/inertial trackpad scrolling is
  approximated and will not reproduce momentum exactly.
- **Horizontal scroll discarded**: Only vertical scroll (`dy`) is captured; the
  horizontal component (`dx`) is dropped during recording.
