# Deep Interview Spec: screenplay-scripter

## Metadata
- Interview ID: di-screenplay-scripter-2026-07-06
- Rounds: 8 (+ Round 0 topology)
- Final Ambiguity Score: 15%
- Type: greenfield
- Generated: 2026-07-06
- Threshold: 0.2
- Threshold Source: default
- Initial Context Summarized: no
- Status: PASSED

## Clarity Breakdown
| Dimension | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| Goal Clarity | 0.92 | 0.40 | 0.37 |
| Constraint Clarity | 0.80 | 0.30 | 0.24 |
| Success Criteria | 0.80 | 0.30 | 0.24 |
| **Total Clarity** | | | **0.85** |
| **Ambiguity** | | | **15%** |

## Topology
| Component | Status | Description | Coverage Note |
|-----------|--------|-------------|---------------|
| Recorder | active | Toggle-gated interaction capture → .py script | Fully specified: toggle, pynput, $EDITOR open |
| Script Format | active | Real Python .py file with `from scripter import ...` | Fully specified: v1 API surface defined |
| Player | active | Executes script with auto-interpolated mouse movement | Fully specified: auto-interpolation before clicks |
| ffmpeg Integration | active | External wrapper; documented example shell script | Resolved as docs-only, not built-in CLI feature |

## Goal
Build a Python CLI tool (`scripter`) using uv + Typer that allows macOS users to record mouse/keyboard interactions into a human-readable, editable Python script file, then replay that script with smooth auto-interpolated mouse movement — enabling the creation of polished, error-free app tutorial screen recordings.

## Constraints
- **Platform:** macOS only (cliclick + avfoundation dependency)
- **Package manager:** uv
- **CLI framework:** Typer
- **Event capture library:** pynput (or Quartz/pyobjc — implementation choice; pynput is cross-platform but macOS Accessibility permission required either way)
- **Execution backend:** cliclick (subprocess calls)
- **v1 DSL API** (what recorder emits, player executes):
  - `click(x, y)` — left click
  - `right_click(x, y)` — right click
  - `drag((x1, y1), (x2, y2))` — click-hold-drag
  - `scroll(x, y, amount)` — scroll wheel
  - `key(*keys)` — keyboard shortcuts (e.g. `key('cmd', 'space')`)
  - `type_text(text)` — text input
  - `sleep(seconds)` — pause
- **Deferred to v2:** `open_app()`, `osascript()`, bezier-curve interpolation choice
- **Recording gate:** Ctrl+Opt toggle (not hold) — requires global hotkey detection while app is in background
- **Smooth movement:** player auto-interpolates before every `click()`/`drag()` with linear step interpolation (~30–60 intermediate `cliclick m:` steps); user does NOT need to write `move()` calls
- **ffmpeg integration:** documented wrapper only; no built-in `scripter capture` subcommand

## Non-Goals
- Windows/Linux support
- `open_app()` / `osascript()` DSL commands in v1
- Built-in screen recording (ffmpeg managed by user)
- Bezier curve interpolation (linear steps sufficient for v1)
- Network/cloud sync of scripts
- GUI application

## Acceptance Criteria
- [ ] `scripter record output.py` starts recording session with instructions printed to terminal
- [ ] Ctrl+Opt toggle visibly changes state (menubar icon or terminal indicator)
- [ ] All keyboard events captured while gate is ON: key combos (`key()`), text typing (`type_text()`)
- [ ] All mouse events captured while gate is ON: clicks, right-clicks, drags, scrolls
- [ ] Events while gate is OFF are NOT recorded (user navigates freely)
- [ ] Multiple pause/resume cycles in one session work correctly
- [ ] Ctrl+C ends session; tool opens `$EDITOR` (env var) to review generated script
- [ ] Generated script is a valid, importable Python file: `from scripter import click, sleep, drag, ...`
- [ ] `scripter play script.py` executes the script via cliclick subprocess calls
- [ ] Player auto-interpolates smooth mouse movement before every `click()` and `drag()` — no teleport
- [ ] Smooth movement: cursor visibly travels from A to B (multiple `cliclick m:` intermediate steps)
- [ ] Script is human-readable and manually editable (users can add/remove/reorder steps)
- [ ] Docs include an example ffmpeg + `scripter play` shell script for screen recording

## Assumptions Exposed & Resolved
| Assumption | Challenge | Resolution |
|------------|-----------|------------|
| Ctrl+Opt is held while acting | Assumed hold-based gate | **Toggle-based**: one click = start, another = pause |
| Mouse-only recording | Initial prompt focused on mouse | **All interactions**: keyboard + mouse captured while gate is ON |
| Script needs `move()` calls | Recorder would emit explicit moves | **Player auto-interpolates**: script stays clean, player adds movement |
| ffmpeg is a CLI subcommand | Initial prompt showed wrapped shell script | **External wrapper**: docs-only, user manages ffmpeg themselves |
| Smooth = bezier curves | Complex interpolation needed | **Linear steps sufficient** for tutorial recording look |
| Script is a parsed custom format | Custom DSL parser needed | **Real Python file**: `from scripter import ...`; `python script.py` = play |

## Technical Context
**Greenfield project.** Key technical decisions:

- **Event capture:** pynput global listeners for keyboard + mouse; requires macOS Accessibility permission in System Settings
- **Modifier detection:** pynput `keyboard.Listener` detects Ctrl+Opt combination for gate toggle
- **Execution:** cliclick called via `subprocess.run(['cliclick', ...])` for each action
- **Interpolation:** Player computes N intermediate `(x, y)` points along the line from current cursor position to target, calls `cliclick m:x,y` for each step
- **Menubar indicator:** rumps or objc bridge for macOS menubar icon; or simpler terminal-based indicator (stdout line)
- **Script generation:** recorder writes a `.py` file with `from scripter import *` header + one function call per captured event
- **Script execution:** player imports the scripter module with real implementations and executes the script, OR the script is run directly with `python script.py` if scripter is installed

## Ontology (Key Entities)
| Entity | Type | Fields | Relationships |
|--------|------|--------|---------------|
| Script | core domain | path, actions[], created_at | produced by Recorder, consumed by Player |
| Checkpoint | core domain | action_type, x, y, keys, text, delay | contained in Script |
| Recorder | core domain | gate_state, output_path, event_listener | produces Script via EventListener |
| Player | core domain | script_path, speed, step_count | consumes Script, calls cliclick |
| RecordingGate | supporting | state (on/off/paused), toggle_hotkey | owned by Recorder |
| ScripterModule | supporting | click, drag, scroll, key, type_text, sleep | imported by Script, implemented by Player |
| EventListener | external system | keyboard_listener, mouse_listener | pynput component, used by Recorder |
| Interpolation | supporting | from_pos, to_pos, steps, step_delay | computed by Player before each click/drag |
| ScreenRecording | external system | ffmpeg_pid, display_index, output_file | external; user manages, docs provide example |
| DSLCommand | supporting | name, args | unit of Script; maps 1:1 to ScripterModule function |

## Ontology Convergence
| Round | Entity Count | New | Changed | Stable | Stability Ratio |
|-------|-------------|-----|---------|--------|----------------|
| 1 | 5 | 5 | — | — | N/A |
| 2 | 6 | 1 | 0 | 5 | N/A |
| 3 | 7 | 1 | 0 | 6 | 86% |
| 4 | 8 | 1 | 0 | 7 | 88% |
| 5 | 9 | 1 | 0 | 8 | 89% |
| 6 | 10 | 1 | 0 | 9 | 90% |
| 7 | 10 | 0 | 0 | 10 | 100% |
| 8 | 10 | 0 | 0 | 10 | 100% |

## Interview Transcript
<details>
<summary>Full Q&A (8 rounds + topology)</summary>

### Round 0 — Topology
**Q:** Is the topology 4 components (Recorder, Script Format, Player, ffmpeg Integration)?
**A:** "Recorder can call `cliclick p` when gate is open and kill it when gate is closed."
*(Interpreted as topology confirmation + implementation note)*

### Round 1 — Script Format
**Q:** What format should the script file be?
**A:** Python DSL
**Ambiguity:** 60%

### Round 2 — Recorder
**Q:** How does the recorder detect click TYPE (not just position)?
**A:** Python library (pynput/pyobjc)
**Ambiguity:** 55%

### Round 3 — Script Format
**Q:** Is the Python DSL a real `.py` file or a custom parsed format?
**A:** Real Python — importable module
**Ambiguity:** 49%

### Round 4 — Player (Contrarian)
**Q:** Does smooth movement actually require interpolation, or just move + sleep?
**A:** User confirmed interpolation needed (teleport would look bad)
**Ambiguity:** 44%

### Round 5 — Script Format (Simplifier)
**Q:** Which DSL commands are in scope for v1?
**A:** key(), type_text(), move(), click(), right_click(), drag(), scroll(), sleep() — deferred: open_app(), osascript()
**Ambiguity:** 35%

### Round 6 — Recorder
**Q:** Walk me through a complete recording session lifecycle.
**A:** Toggle (not hold). Full capture while on. Pause/resume. Menubar state. $EDITOR opens post-session. Ctrl+C ends.
**Ambiguity:** 25%

### Round 7 — Player
**Q:** Who generates smooth move() calls — recorder or player?
**A:** Player auto-interpolates (Option A) — clean script, smart runtime
**Ambiguity:** 22%

### Round 8 — ffmpeg Integration
**Q:** Is ffmpeg a built-in subcommand or external wrapper?
**A:** External / documented wrapper (Option B)
**Ambiguity:** 15% ✓ Below threshold

</details>
