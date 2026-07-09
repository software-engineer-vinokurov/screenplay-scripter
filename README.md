# screenplay-scripter

Record and replay macOS mouse/keyboard interactions as human-readable Python
scripts. Recordings become plain Python DSL files you can hand-edit, then replay
with smooth, interpolated mouse movement for polished tutorial screen recordings.

## Why

Screen-recording a tutorial by hand is fiddly: jittery cursor paths, mistimed
clicks, and no way to redo a take cleanly. `scripter` captures your interactions
into an editable script, then replays them deterministically with eased mouse
motion so every take looks intentional.

## Requirements

- macOS
- [`cliclick`](https://github.com/BlueM/cliclick) 5.1+

## Install

### Homebrew (recommended)

```sh
brew tap software-engineer-vinokurov/tap
brew install screenplay-scripter
```

### uv

```sh
uv tool install screenplay-scripter
```

Or add to an existing project / run from a clone:

```sh
uv add screenplay-scripter          # as a project dependency
uv sync && uv run scripter --help   # from a clone
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

A **menu bar indicator** appears while recording:

- Title blinks `● REC` / `○ REC` while active, `○ rec` while paused.
- Click the indicator to open the menu:
  - **Stop & Edit** — save the script and open it in `$EDITOR` inside iTerm (or Terminal.app as fallback).
  - **Quit (discard)** — exit without saving.
- **Ctrl+C** — stop recording, save, and open the editor.

Controls while recording:

- **Ctrl+Opt** — toggle recording ON/OFF (the gate). The chord itself is never
  written to the script.
- **Ctrl+Opt+Shift** — insert a `move(x, y)` call for the current cursor
  position without clicking. Use this to record an explicit cursor path between
  two clicks. The chord itself is never written to the script.

The recorder starts **PAUSED**. Press Ctrl+Opt to arm it, perform your actions,
press Ctrl+Opt again to pause. Section comments are inserted automatically:

```python
# --- recording started ---
click(760, 540)
# --- paused ---
# --- resumed ---
type_text('hello')
```

To disable the menu bar and use terminal-only mode:

```sh
scripter record demo.py --no-menubar
# Ctrl+C ends the session, writes the script, and opens $EDITOR
```

Suppress automatic `sleep()` insertion between events:

```sh
scripter record demo.py --no-timing
```

### Play

```sh
scripter play demo.py
```

The terminal shows a live status line while the script runs:

```
▶ Playing  —  Ctrl+Opt: stop
```

Press **Ctrl+Opt** at any time to abort; the line updates in place:

```
⏹ Stopped  —  Ctrl+Opt: stop
```

Show a **menu bar progress indicator** and enable pause/resume:

```sh
scripter play demo.py --review
```

The terminal status line now reads:

```
▶ Playing demo.py  —  Ctrl+Opt: pause/resume
```

Pressing **Ctrl+Opt** toggles it between playing and paused:

```
⏸ Paused  demo.py  —  Ctrl+Opt: pause/resume
```

The `--review` menu bar shows `▶ 12/87` (current source line / total lines) and
includes a **Previous Pauses** submenu. As `sleep()` calls are executed, they
appear in the submenu (newest first, up to 10). Clicking an entry toggles it
between active and commented-out directly in the script file — no editor needed:

```
Previous Pauses
  7.38          ← click to comment out: becomes # 7.38
  # 1.00        ← click again to uncomment
  0.25
```

Commented-out sleeps from a previous session are remembered and appear in the
submenu as soon as the player walks past their line in the script, so you can
toggle them without restarting from scratch.

Click the indicator itself for a **Stop** menu item.

Preview the exact `cliclick` argv without moving the mouse:

```sh
scripter play demo.py --dry-run
```

Override the easing calibration factor (default 555 — see [Easing](#easing)):

```sh
scripter play demo.py --easing 300
```

Environment equivalents (CLI flags take precedence):

- `SCRIPTER_DRY_RUN=1`
- `SCRIPTER_EASING=300`

## Easing

Mouse movement speed is kept **constant across all distances** using inverse
proportional easing:

```
easing = factor × 1000 / distance
```

The `--easing` flag (default `555`) is the cliclick easing coefficient applied
at exactly 1000 px. Shorter moves get proportionally higher easing so the cursor
always travels at the same apparent speed. Pass a smaller factor for faster
overall motion, a larger one for slower.

## DSL reference

Every generated script begins with `from scripter import *`. Available calls:

| Function                     | Description                                                    |
| ---------------------------- | ------------------------------------------------------------- |
| `click(x, y)`                | Move to `(x, y)` with easing, then left-click.                |
| `double_click(x, y)`         | Move to `(x, y)` with easing, then double-click.              |
| `right_click(x, y)`          | Move to `(x, y)` with easing, then right-click.               |
| `drag(start, end)`           | Press at `start`, drag along eased path, release at `end`.    |
| `scroll(x, y, amount)`       | Position at `(x, y)`, scroll `amount` lines (Quartz wheel).   |
| `key(*keys)`                 | Key combo. Modifiers (`cmd`, `shift`, `ctrl`, `alt`, `fn`) held around the terminal key, e.g. `key('cmd', 'c')`, `key('return')`. |
| `type_text(text)`            | Type a literal string (including spaces).                      |
| `sleep(seconds)`             | Pause for `seconds`.                                           |
| `move(x, y)`                 | Move the cursor with easing (rarely needed; `click` auto-moves). |

Named keys accepted by `key()`: `return`, `space`, `tab`, `esc`,
`arrow-up/down/left/right`, `f1`–`f16`, `page-up`, `page-down`, `home`, `end`,
and more (see `cliclick`'s `kp:` list). Any single character not in that set is
typed with `t:`.

**Double-clicks** are detected automatically during recording: two left-clicks
within 0.5 s and 10 px of each other are collapsed into a single
`double_click()` call.

**Capital letters** typed while Shift is held are captured directly into
`type_text(...)` rather than emitted as `key('shift', 'X')` combos, so a
sentence like "Nice descent" records as one `type_text('Nice descent')` call.

**Space** typed in a text field is captured as part of `type_text(...)`, not as
a separate `key('space')`. Space combined with a modifier (e.g. Cmd+Space for
Spotlight) is recorded as `key('cmd', 'space')`.

## Editing scripts

Recorded scripts are ordinary Python. Open and tweak them freely:

- Adjust coordinates, reorder actions, or delete takes you do not want.
- Tune `sleep()` values to change pacing.
- Add an explicit `move()` for a deliberate cursor path between clicks.

Playback runs a **warn-only** AST scan first: non-DSL imports or unexpected
function calls are reported to stderr but do not block execution, so you can add
light control flow (`for`, `range`, `print`) when you need it.

Example hand-edited script:

```python
from scripter import *

# --- recording started ---
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

