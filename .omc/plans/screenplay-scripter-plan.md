# Implementation Plan: screenplay-scripter

**Status:** PENDING APPROVAL — Critic APPROVED (iteration 2). Consensus reached.
**Mode:** RALPLAN-DR SHORT
**Date:** 2026-07-06
**Target:** Python CLI tool `scripter` (macOS-only) to record mouse/keyboard interactions into a human-readable, editable Python script, then replay with smooth auto-interpolated mouse movement.

---

## 1. Requirements Summary

Build a `uv`-managed Python package exposing a Typer CLI named `scripter` with two primary subcommands:

- `scripter record output.py` — starts a global mouse/keyboard capture session gated by a **Ctrl+Opt toggle** (press = start, press again = pause/resume, Ctrl+C = end). Captured events are serialized into a human-readable `.py` file using the v1 DSL API. On session end, opens `$EDITOR` for review.
- `scripter play script.py` — executes the recorded script via `cliclick` subprocess calls, auto-interpolating smooth linear mouse movement before every `click()`/`right_click()`/`drag()`.

The generated script is also directly runnable via `python script.py` (running the script *is* playing it), because the DSL functions live in the importable `scripter` package.

**v1 DSL surface** (defined in `scripter` package, importable via `from scripter import *`):
`click(x, y)`, `right_click(x, y)`, `drag((x1, y1), (x2, y2))`, `scroll(x, y, amount)`, `key(*keys)`, `type_text(text)`, `sleep(seconds)`.

**Deferred to v2** (out of scope for this plan): `open_app()`, `osascript()`, bezier-curve interpolation.

**Key technical decisions inherited from spec:**
- Event capture: `pynput` global listeners (macOS Accessibility permission required).
- Execution backend: `cliclick` for all cursor positioning and actions; `pyobjc-framework-Quartz` for wheel-event emission only (scroll has no cliclick equivalent — confirmed: `c, cp, dc, dd, dm, du, kd, kp, ku, m, p, rc, t, tc, w`).
- Scroll: **hybrid** — `cliclick m:x,y` positions cursor (cliclick stays movement authority), then `CGEventCreateScrollWheelEvent(None, kCGScrollEventUnitLine, 1, amount)` + `CGEventPost` fires the wheel event. Unit: `kCGScrollEventUnitLine` matches pynput's line-count deltas. No additional macOS permission beyond existing Accessibility (posting events requires Accessibility, same as pynput).
- Smooth movement (click/right_click): player computes ~30–60 intermediate points along the line from current cursor to target, batched as `cliclick -w <ms> m:x0,y0 m:x1,y1 … c:xt,yt` (one process spawn per action).
- Smooth movement (drag): player computes ~30–60 points using `dm:` (drag-move, not `m:`): `cliclick -w <ms> dd:x0,y0 dm:x1,y1 … dm:xN,yN du:xt,yt` (cliclick `dm:` continues an active drag; plain `m:` would not track in target apps).
- Recording indicator: terminal stdout indicator (rumps menubar deferred as optional enhancement — see Risks).
- ffmpeg: documented wrapper example only, NOT a built-in subcommand.

**Non-Goals:** Windows/Linux support, `open_app()`/`osascript()` in v1, built-in screen recording, GUI application.

---

## 2. Acceptance Criteria (testable)

Each maps to a spec checkbox and is verifiable.

1. **AC-1** `scripter record output.py` prints startup instructions (toggle key, Ctrl+C to end) and begins in the OFF/paused state.
2. **AC-2** Pressing Ctrl+Opt changes a visible terminal indicator (e.g. `● RECORDING` ↔ `⏸ PAUSED`).
3. **AC-3** With gate ON, all keyboard key-press events are captured and written as `key(...)` / `type_text(...)` calls.
4. **AC-4** With gate ON, all mouse events (click, right-click, drag, scroll) are captured with correct coordinates.
5. **AC-5** With gate OFF, no keyboard/mouse events are written to the output file.
6. **AC-6** Multiple pause/resume cycles work: events during OFF windows are excluded, events during ON windows are included, in correct order.
7. **AC-7** Ctrl+C cleanly stops listeners, flushes/writes the file, and opens `$EDITOR` on the output path.
8. **AC-8** The generated file starts with `from scripter import *` (or explicit imports) and is a valid, importable Python module (`python -c "import ast; ast.parse(open('output.py').read())"` succeeds; `python output.py` runs without ImportError).
9. **AC-9** `scripter play script.py` executes each DSL call via `cliclick` subprocess invocations, in file order.
10. **AC-10** Before every `click()`/`right_click()`, player emits ≥30 `m:` command tokens in a single batched `cliclick -w <ms> m:… c:` invocation. Before every `drag()`, player emits `dd:` then ≥30 `dm:` tokens (drag-move, not plain move) then `du:` in one batched invocation.
11. **AC-11** Cursor visibly travels during playback. Verifiable via `--dry-run`: click/right_click actions have ≥30 `m:` tokens; drag actions have ≥30 `dm:` tokens. One process spawn per action.
12. **AC-12** The generated script is human-readable (one DSL call per event, one line each) and can be hand-edited then re-played without regeneration.
13. **AC-13** README documents an ffmpeg + `scripter play` shell wrapper example that records the screen while playing the script.
14. **AC-14** `--dry-run` flag on `play` prints the exact `cliclick` argv for every action without executing (enables deterministic testing without a display/permissions).
15. **AC-15** Recorder captures inter-event timestamps and emits `sleep(N)` calls for gaps > 150ms between actions. `scripter record --no-timing` disables this, emitting only explicit user-authored `sleep()` calls.
16. **AC-16** The Ctrl+Opt toggle chord and Ctrl+C keystrokes are **excluded** from captured event output — they never appear as `key(...)` lines in the generated script.
17. **AC-17** `scripter record` polls a stop-flag on the main thread (not `listener.join()`) so Ctrl+C is delivered promptly via SIGINT even while pynput's CFRunLoop runs on a listener thread.

Target: 17/17 concrete and testable (100%).

---

## 3. Architecture Overview

```
scripter/
  __init__.py        # exports DSL API + __all__; defines click/right_click/drag/scroll/key/type_text/sleep
  dsl.py             # DSL function implementations (each calls backend.execute)
  backend.py         # cliclick subprocess wrapper: run(args), get_cursor_pos(), dry_run flag
  interpolate.py     # linear_points(start, end, steps) -> list[(x,y)]; movement executor
  recorder.py        # pynput listeners, Ctrl+Opt toggle state machine, event->DSL serialization
  player.py          # loads a .py script and executes it (delegates to dsl via import), or execs file
  cli.py             # Typer app: record, play subcommands
  codegen.py         # Event -> source line rendering (human-readable formatting)
pyproject.toml       # uv project, entry point scripter = scripter.cli:app
README.md            # install, permissions, usage, ffmpeg wrapper
tests/
  test_interpolate.py
  test_codegen.py
  test_backend_dryrun.py
  test_dsl_import.py
```

**Critical design point — dual execution model:** The DSL functions in `scripter/dsl.py` ARE the player. When a recorded script does `from scripter import *` and calls `click(100, 200)`, that function itself performs interpolation + cliclick calls. Therefore `scripter play script.py` is a thin wrapper that `runpy.run_path()`s the script; there is no separate interpretation engine. This satisfies AC-8/AC-9/AC-12 with a single code path and avoids DSL drift between "play" and "python script.py".

Config flow: `scripter.configure(dry_run, steps)` is the single entry point, called **before** `runpy.run_path()`. DSL functions read config at **call time** (not import time). Precedence: CLI flag > env var (`SCRIPTER_DRY_RUN`, `SCRIPTER_STEPS`) > default. This eliminates the "module state or env" ambiguity — `--dry-run` always wins over env. The same-process / `sys.modules` assumption (why CLI-set config is visible to the script) is documented inline as a load-bearing invariant.

`scripter play` also runs a **warn-only AST pre-flight** (`compile()` + `ast.walk()`) before execution: it flags any non-DSL imports or function calls as warnings (not errors) in v1. This gives users feedback without blocking `python script.py` compatibility, and the pre-flight path provides file:line traceback mapping vs raw runpy tracebacks.

---

## 4. Implementation Steps

### Step 1 — Project scaffold + DSL package skeleton
- **Files:** `pyproject.toml`, `scripter/__init__.py`, `scripter/dsl.py`, `scripter/backend.py`
- Init `uv` project (`uv init`), add deps: `typer`, `pynput`, `pyobjc-framework-Quartz` (for `scroll()` — cliclick has no scroll command). Declare console entry point `scripter = "scripter.cli:app"`.
- Define DSL signatures and `__all__` in `__init__.py`. Implement `backend.run(args, dry_run)` wrapping `subprocess.run(['cliclick', *args])` and `backend.get_cursor_pos()` (parse `cliclick p` **stdout only** — cliclick prints a multi-line WARNING banner to stderr when Accessibility is ungranted; parse must not read stderr).
- **Capability pre-check:** on first import/startup, verify `cliclick -h` lists `dd`, `dm`, `du`, `m`, `kd`, `ku`, `kp`, `t`, `c`, `rc`; warn if not (R12). Note: cliclick 5.1 verified command set: `c, cp, dc, dd, dm, du, kd, kp, ku, m, p, rc, t, tc, w`.
- **Acceptance:** `uv run python -c "from scripter import click, right_click, drag, scroll, key, type_text, sleep"` succeeds (AC-8 import portion). `backend.run(..., dry_run=True)` returns argv without executing.

### Step 2 — Interpolation engine + DSL action implementations
- **Files:** `scripter/interpolate.py`, `scripter/dsl.py`
- Implement `linear_points(start, end, steps=None)` returning N points (clamp 30–60, default derived from distance).
- **Batch emission — click/right_click:** `move_and_click(target, button)` builds one invocation: `cliclick -w <ms> m:x0,y0 m:x1,y1 … m:xN,yN c:xt,yt` (or `rc:` for right-click). `-w` = desired traversal ms / step count, minimum 20ms per cliclick constraint (floor documented, ~0.6–1.2s minimum traversal for 30–60 steps).
- **Batch emission — drag:** `drag_path(start, end)` emits: `cliclick -w <ms> dd:x0,y0 dm:x1,y1 dm:x2,y2 … dm:xN,yN du:xt,yt`. Uses `dm:` (drag-move) not `m:` — `dm:` continues the active drag event in target apps. `m:` after `dd:` is a plain move and will not track as a drag.
- **key() decomposition (replaces kp:-only mapping):** `key(*keys)` separates keys into modifiers (`cmd/ctrl/alt/shift/fn` → `kd:`/`ku:` wrap) and terminal key (named key from kp-list → `kp:`; single printable char → `t:`). Examples: `key('cmd','c')` → `cliclick kd:cmd t:c ku:cmd`; `key('cmd','space')` → `cliclick kd:cmd kp:space ku:cmd`; `key('return')` → `cliclick kp:return`. Named kp: keys (verified): arrows, F1–F16, return/enter, space, tab, esc, delete, page-up/down, home, end, num-* etc. Document combos cliclick cannot express (e.g. non-ASCII chars).
- **scroll() via hybrid (cliclick move + Quartz wheel):** `scroll(x, y, amount)` must first position the cursor at `(x,y)` — `CGEventCreateScrollWheelEvent` has no location parameter; macOS hit-tests the wheel event against the actual cursor position at post time. **Sequencing invariant:** `cliclick m:x,y` (blocking subprocess) MUST complete before the Quartz wheel post — `subprocess.run` is blocking so this is guaranteed, but document it inline as load-bearing. Implementation: `cliclick m:x,y` first (reuses existing backend seam, same dry-run path), then `Quartz.CGEventCreateScrollWheelEvent(None, kCGScrollEventUnitLine, 1, int(amount))` + `CGEventPost(kCGHIDEventTap, event)`. **Unit contract:** pynput's `on_scroll` delivers deltas as line/click counts; replay must use `kCGScrollEventUnitLine` (not `kCGScrollEventUnitPixel` — pixel would under-deliver by ~1-2 orders of magnitude). **Trackpad fidelity caveat (README):** trackpad momentum scrolling may deliver high-magnitude pixel-precise deltas through pynput; replaying as line units may over- or under-scroll relative to the original gesture. After scroll, cursor is left at `(x,y)` — document this so the next action's interpolation start (`get_cursor_pos`) is correct. Dry-run: emit the `cliclick m:x,y` argv (testable) **and** print `[scroll x,y amount=N lines]` sentinel (so positioning is also verified headlessly).
- Implement `sleep` (native `time.sleep`).
- **Acceptance:** AC-10, AC-11. Unit test asserts ≥30 `m:` tokens per click in dry-run argv; ≥30 `dm:` tokens per drag; key decomposition correct for modifier+named, modifier+char, named-only cases; scroll dry-run prints sentinel. Single subprocess per action.

### Step 3 — Codegen + recorder state machine
- **Files:** `scripter/codegen.py`, `scripter/recorder.py`
- `codegen.render_event(event) -> str` produces one human-readable line per event (AC-12). Coalesce consecutive printable-char keystrokes into a single `type_text("...")` (non-printable/modifier flushes the buffer → `key(...)`). Document `type_text` limitation: `cliclick t:` types near-instantly and may overflow fast-consuming apps or mangle some Unicode — warn in README (R6).
- **Scroll capture:** each pynput `on_scroll` event (typically `dy=±1`) becomes its own `scroll(x, y, amount)` line — no coalescing. This is intentional (preserves exact gesture rhythm) but can be verbose for fast scroll gestures. Horizontal scroll (`dx`) is silently discarded by design — `scroll(x, y, amount)` is single-axis. Codegen must `int()`-coerce `dy` before rendering (pynput macOS `dy` is int in practice, but coercion guards against fractional values from high-resolution scrolling). Document both behaviors in README.
- **Drag reconstruction state machine (blocks AC-4):** pynput exposes `on_click(x,y, button, pressed)` and `on_move(x,y)` — not high-level "drag." The recorder maintains a `MouseState` with `press_pos`, `moved` flag, and `release_pos`. On `pressed=True`: record `press_pos + timestamp`, set `moved=False`. On `on_move` while pressed: set `moved=True` (discard intermediate positions — player re-interpolates). On `pressed=False`: if `moved=True` → emit `drag((press_pos),(release_pos))`; else → emit `click(release_pos)` (or `right_click` per button). A movement threshold (e.g. 5px total displacement) distinguishes accidental micro-moves from intentional drags. Unit-tested with synthetic press/move/release sequences.
- **Control-key filtering (blocks AC-16):** The keyboard listener maintains a `currently_pressed_modifiers` set. The Ctrl+Opt toggle chord (`ctrl+alt`) is excluded from the capture stream — never emitted as `key(...)`. Ctrl+C (`ctrl+c`) is similarly excluded (it terminates, not captured). All other events pass through normally while gate is ON.
- **Timestamp capture → sleep emission (AC-15):** Each event is timestamped (`time.monotonic()`). On flush, consecutive event pairs with gap > 150ms emit a preceding `sleep(gap_seconds)` rounded to 2 decimal places. `--no-timing` flag disables this; only explicit user `sleep()` calls appear.
- **Recorder session lifecycle + SIGINT (blocks AC-17):** Main thread sets up pynput listeners, then polls `threading.Event(stop_flag)` in a tight loop (`stop_flag.wait(timeout=0.05)`) rather than blocking on `listener.join()`. SIGINT handler sets `stop_flag`; pynput CFRunLoop runs on its own thread unimpeded. This ensures Ctrl+C is always delivered promptly (AC-7).
- **Stdout indicator (B1 — known limitation documented):** Prints `● RECORDING` / `⏸ PAUSED` to terminal on toggle. **Documented limitation:** the terminal is typically unfocused during recording (user is clicking in other apps) so this indicator is invisible in the most common scenario. Users should check state before toggling. Menubar indicator (B2 / rumps) is the recommended v2 upgrade path.
- **Acceptance:** AC-2,3,4,5,6,7,15,16,17. Toggle logic, gating, drag reconstruction, control-key filtering, and timing capture all unit-tested via injectable event source (no real pynput/display needed).

### Step 4 — CLI wiring (record + play)
- **Files:** `scripter/cli.py`, `scripter/player.py`
- Typer app with:
  - `record(output: Path, no_timing: bool = False)` — prints startup instructions (AC-1), starts RecordingSession with the stop-flag poll loop (AC-17).
  - `play(script: Path, dry_run: bool = False, steps: int = None)` — config flow: call `scripter.configure(dry_run=dry_run, steps=steps)` with **explicit precedence** (CLI flag > `SCRIPTER_DRY_RUN`/`SCRIPTER_STEPS` env vars > defaults) before any execution. This is the single config entry point; DSL fns read it at call time (not import time).
- **Pre-flight + runpy (synthesis):** `player.py` calls `compile(source, filename=str(script), "exec")` first (gives file:line tracebacks). Then runs a warn-only AST scan (`ast.walk()`) flagging any non-DSL imports or calls as warnings. Then `exec(code, namespace)` in a fresh namespace where DSL names are pre-bound to the configured implementations. This preserves `python script.py` compat while providing better error attribution than raw `runpy`.
- `--dry-run` prints argv only (AC-14). `--no-timing` passed through to recorder.
- **Acceptance:** AC-1, AC-9, AC-14. Config precedence verified: `SCRIPTER_DRY_RUN=1 scripter play script.py --no-dry-run` uses CLI (no-dry-run wins). End-to-end: hand-write a demo.py, `--dry-run` output shows batched cliclick argv with ≥30 `m:` tokens per click.

### Step 5 — Docs, ffmpeg wrapper, permissions guide, tests
- **Files:** `README.md`, `tests/*`
- README: install via `uv`, macOS Accessibility/Screen-Recording permission setup, DSL reference, editing guide. Document B1 indicator limitation (unfocused-terminal). Document `type_text` caveat (near-instant; may overflow fast-responding apps). **ffmpeg wrapper shell example** (`ffmpeg -f avfoundation ...` + `scripter play` + `kill -INT`) (AC-13).
- Tests: `test_interpolate.py` (step count, batch argv tokens, endpoints), `test_codegen.py` (drag reconstruction, coalescing, timing gaps), `test_backend_dryrun.py` (config precedence: CLI > env > default), `test_dsl_import.py` (from scripter import *), `test_recorder_gating.py` (ON/OFF/ON sequences, control-key exclusion, timing emission). All pass headless via dry-run.
- Add `test_recorder_gating.py` — synthetic event sequences: toggle on/off, drag start/move/release, Ctrl+Opt exclusion, gap > 150ms → sleep emission, `--no-timing` suppression.
- Add `test_backend_capability.py`: run `cliclick -m test dd:0,0 dm:10,10 du:0,0` (cliclick's built-in test/dry-run mode) to validate that all used commands (`dd`, `dm`, `du`, `m`, `kd`, `ku`, `kp`, `t`, `c`, `rc`) are accepted by the installed cliclick binary. This headlessly catches backend capability mismatches before Step 2 is hit at runtime.
- **Acceptance:** AC-13, AC-8, AC-14, AC-15, AC-16; `uv run pytest` green.

---

## 5. Risks and Mitigations

| # | Risk | Impact | Mitigation |
|---|------|--------|------------|
| R1 | macOS Accessibility permission not granted → pynput listeners silently fail | Recording captures nothing | Detect at `record` startup (probe listener); print explicit permission-grant instructions + System Settings deep link; fail loud, not silent. |
| R2 | Ctrl+Opt toggle conflicts with system shortcuts / is hard to detect reliably in pynput | Toggle misfires or double-fires | Debounce (ignore repeats within ~300ms); require both modifiers with no other key; unit-test the state machine with an injectable event source (decoupled from pynput). |
| R3 | `cliclick p` cursor-position parsing format drift across versions | Interpolation start point wrong | Wrap parsing in `backend.get_cursor_pos()` with defensive parse + fallback to last-known target; pin/document tested cliclick version. |
| R4 | Interpolation timing: too many `m:` steps → slow playback; too few → jerky | Poor UX | Batch emission (`cliclick -w <ms> m:… m:…`) with distance-adaptive step count (30–60 band); configurable via `--steps`/`SCRIPTER_STEPS`; document tradeoff. |
| R5 | Testing GUI automation requires a real display + permissions → untestable in CI | Low coverage, regressions | `--dry-run`/`SCRIPTER_DRY_RUN` (CLI wins over env) prints batched argv without executing; injectable seams for event source and backend. |
| R6 | Keystroke → `type_text` coalescing + `cliclick t:` may mangle special keys or overflow fast-input apps | Unreadable or wrong scripts | Coalesce only printable chars; modifier/non-printable flushes to `key(...)`. Document cliclick `t:` near-instant typing caveat in README. |
| R7 | stdout indicator is invisible when terminal is unfocused (most recording scenarios) | User can't verify recording state | Documented limitation in README; B2 (rumps menubar) as recommended v2 upgrade. For v1: instructions tell user to check state before acting. |
| R8 | `exec(compile(...))` executing user-authored scripts = arbitrary code | Security | Warn-only AST pre-flight flags non-DSL content; trust model same as `python script.py`; no remote execution. Document in README. |
| R9 | Config read at import time (not call time) → `--dry-run` silently ignored | Silent test failures | DSL fns read config at **call time**; `scripter.configure()` is the single entry; precedence CLI > env > default; test with env set + CLI flag overriding. |
| R10 | Ctrl+Opt or Ctrl+C emitted as `key()` into recorded script | Corrupted output | Maintain `excluded_chords` set in keyboard listener; filter before gating check. Unit-tested (AC-16). |
| R11 | SIGINT delayed/swallowed by pynput's CFRunLoop thread blocking main | Ctrl+C unresponsive | Poll `threading.Event` with 50ms timeout on main thread; SIGINT handler sets flag (AC-17). |
| R12 | cliclick version lacks a required command (`s:` for scroll, unexpected `dm:` removal, etc.) | Silent wrong output or crash | On startup, parse `cliclick -h` stdout and verify required commands present; warn immediately if any are missing. `test_backend_capability.py` uses `cliclick -m test` to validate all used command tokens headlessly before deployment. |
| R13 | `cliclick p` stderr WARNING banner (Accessibility ungranted) contaminates stdout parse | `get_cursor_pos()` fails or returns garbage | Parse stdout only in `backend.get_cursor_pos()`; stderr routed to `subprocess.DEVNULL` or captured separately; handle empty/malformed stdout with documented fallback. |

---

## 6. Verification Steps

1. **Static/import:** `uv run python -c "from scripter import *; print(click, drag)"` — AC-8.
2. **Unit tests:** `uv run pytest` — interpolation batch argv token count ≥30 per click (AC-10/11), drag reconstruction (AC-4), codegen readability (AC-12), backend dry-run batched argv (AC-14), DSL import (AC-8), control-key exclusion (AC-16), timing gap → sleep (AC-15), config precedence CLI > env > default (R9).
3. **Dry-run playback:** hand-write a `demo.py`; `scripter play demo.py --dry-run` → assert: click/right_click have ≥30 `m:` tokens; drag has ≥30 `dm:` tokens (not `m:`); key decomposition correct; scroll prints `[scroll ...]` sentinel. One subprocess per action (AC-9/10/11).
3b. **Backend capability gate:** `uv run pytest tests/test_backend_capability.py` — runs `cliclick -m test <all-used-commands>` headlessly; confirms backend can actually execute every DSL verb (R12).
4. **Config precedence test:** `SCRIPTER_DRY_RUN=1 scripter play demo.py` (env sets dry-run); then `SCRIPTER_DRY_RUN=1 scripter play demo.py` after unsetting CLI flag → confirms env activates it. No `--dry-run` CLI flag needed if env set. Verify CLI flag overrides env in reverse.
5. **Recorder state-machine test:** synthetic event sequences — ON/OFF/ON gating (AC-5/6), drag press/move/release → drag() vs click() (AC-4), Ctrl+Opt excluded (AC-16), 200ms gap → sleep(0.2) (AC-15), --no-timing suppresses auto-sleeps (AC-15).
6. **SIGINT test:** spin up recorder in thread, send SIGINT to process, verify stop-flag set and flush completes within 200ms (AC-17).
7. **Manual macOS smoke (documented, human-run):** grant permissions → `scripter record out.py`, toggle, type + click + drag, Ctrl+C → verify `$EDITOR` opens with valid .py file (AC-1/2/7); `scripter play out.py` → visible smooth cursor travel, drag replayed (AC-11).
8. **Docs check:** README contains ffmpeg wrapper snippet (AC-13), B1 limitation note, `type_text` caveat.

---

## 7. RALPLAN-DR Summary (SHORT mode)

### Principles
1. **Single DSL path.** The DSL functions *are* the player — `python script.py` and `scripter play` execute the same implementations. **Honest caveat:** `scripter play` injects config (`dry_run`, `steps`) that bare `python script.py` does not; this control boundary is explicit and documented, not hidden.
2. **Human-readable, hand-editable output above all.** One DSL call per event, one line each; scripts are first-class artifacts, not opaque logs.
3. **Testable without a GUI.** Every core behavior (interpolation, codegen, gating, backend) is unit-testable via dry-run and injectable seams; real-display checks are documented manual smokes.
4. **Fail loud on permissions.** Never silently capture nothing — probe and instruct.
5. **Ship v1 scope; defer cleanly.** No bezier, no `open_app`/`osascript`, no menubar dependency unless free.

### Decision Drivers (top 3)
1. **Consistency between "play" and "run directly"** — the dual-execution requirement (AC-8 + AC-9 + AC-12) forces the DSL-as-player design.
2. **Testability under macOS permission/display constraints** — drives the dry-run + seams architecture (R5).
3. **Recording reliability** (Accessibility permission + Ctrl+Opt toggle robustness) — highest-risk area for user-visible failure (R1, R2).

### Viable Options

**Decision A — Playback engine architecture**
- **Option A1 (CHOSEN): DSL-as-player via `exec(compile(...))` + explicit configure call.** DSL functions perform interpolation+cliclick; `play` compiles + warns via AST scan + execs in a pre-configured namespace.
  - Pros: `python script.py` compatibility preserved; minimal semantic drift; file:line tracebacks via `compile()`; warn-only AST pre-flight recovers enforceability without breaking direct-run.
  - Cons: config must flow via `scripter.configure()` (same-process `sys.modules` invariant — documented); arbitrary code in user files (mitigated by warn-only pre-flight).
  - **Architect antithesis acknowledged:** A2 (AST dispatcher calling the same DSL fns) is NOT a false dichotomy — it would give explicit per-line error mapping + safe-subset enforcement + config as a parameter, without semantic drift IF it reuses the DSL functions. It is a valid v2 upgrade path if the warn-only pre-flight proves insufficient. Retained as viable, not invalidated.
- **Option A2: AST dispatcher reusing same DSL fns.** `play` walks AST, dispatches to the same `dsl.click/drag/…` functions via explicit call, passing config as parameters.
  - Pros: per-line error mapping, config as explicit parameter (no global state), safe-subset enforcement, pause/abort hooks — all structurally possible.
  - Cons: more code in `play`; `python script.py` no longer equivalent (needs to import configured runner). **Deferred to v2** — A1 + warn-only pre-flight achieves the most important properties at lower cost for v1.

**Decision B — Recording indicator**
- **Option B1 (CHOSEN): stdout terminal indicator.** Print `● RECORDING`/`⏸ PAUSED` state changes.
  - Pros: zero extra deps, no runloop conflict with pynput, meets AC-2, headless-friendly.
  - Cons: **genuinely weak in practice** — the terminal is unfocused during recording (user is clicking in other apps) so this indicator is invisible exactly when it matters. Documented as a known limitation; users instructed to verify state before toggling.
- **Option B2: rumps menubar app.** Native menubar indicator.
  - Pros: nicer UX, always-visible.
  - Cons: adds rumps dep + NSApplication runloop that must coexist with pynput listeners (threading complexity), packaging weight. **Deferred to optional follow-up**, not invalidated — viable but not worth v1 complexity.

**Decision C — Interpolation curve**
- **Option C1 (CHOSEN): linear step interpolation in Python, distance-adaptive 30–60 steps.**
  - Pros: simple, deterministic, fully testable (token count in dry-run), meets "visibly travels" AC-11.
  - Cons: constant velocity looks slightly mechanical; `-w` 20ms minimum floors traversal time (~0.6–1.2s for 30–60 steps — document this).
- **Option C2: bezier/eased curve.**
  - Cons: explicitly deferred to v2 by spec. **Out of scope.**
- **Option C3: cliclick native `-e` easing (newly identified).**
  - cliclick has a built-in `-e <easing_factor>` that produces natural/eased motion within a single `m:` command.
  - Pros: simpler codegen (2 points + easing vs 30–60 points); smoother motion from the tool itself.
  - Cons: easing applies globally to all `m:` commands in the invocation, not per-segment; less control over step count for AC-11 testability; `dm:` commands do not document `-e` behavior. **Deferred to v2** — manual steps give fine-grained control and deterministic token-count testing; native easing can replace them once AC-11 metric is relaxed.

*(3 viable options; C2 invalidated by spec, C3 deferred as sound v2 simplification.)*

*(≥2 viable options retained for Decisions A and B; Decision C's alternative is invalidated by explicit spec deferral — rationale documented.)*

---

## 8. Resolved Questions (Architect pass)
1. **Indicator:** B1 stdout accepted for v1; documented as a known UX limitation (unfocused terminal); B2 rumps menubar is v2.
2. **Keystroke coalescing:** conservative coalescing — printable chars merge into `type_text()`; modifier/non-printable flushes to `key(...)`. AC-12 satisfied; `type_text` limitation documented in README.
3. **Inter-event timing:** **Promoted to v1 requirement (AC-15).** Capture timestamps on all events; emit `sleep(gap_seconds)` for gaps > 150ms. `--no-timing` suppresses. Without this, the tool would frequently fail on real UIs that need time between actions.

## 9. ADR (Architecture Decision Record)
**Decision:** DSL-as-player via `exec(compile(...))` (A1 with synthesis improvements)
**Drivers:** (1) `python script.py` must equal `scripter play` at the semantic layer; (2) `--dry-run` testability; (3) human-readable scripts as first-class artifacts.
**Alternatives considered:** A2 (AST dispatcher reusing DSL fns) — valid, deferred to v2 as natural upgrade if warn-only pre-flight proves insufficient.
**Why chosen:** A1 minimizes code, preserves direct-run compatibility, and adds the critical control-plane gap (config precedence, warn-only AST scan, `compile()` tracebacks) at low cost. The Architect's antithesis demonstrated A2-reusing-DSL is not a false dichotomy — it is the right v2 path if enforcement needs harden.
**Consequences:** Same-process `sys.modules` invariant load-bearing (documented); arbitrary code execution in user files (mitigated by pre-flight); `python script.py` does not get `dry_run`/`steps` config (documented — by design).
**Follow-ups:** (1) Evaluate A2 (AST dispatcher) if users request pause/abort/per-line errors in v2. (2) Add B2 (rumps menubar) when pynput + NSApplication runloop coexistence is resolved. (3) Bezier/eased interpolation in v2.

## 10. Changelog
- AC-10/11: cliclick-per-move → batched single invocation with `-w` pacing; metric changed to token count
- AC-15/16/17: added (timing capture, control-key filtering, SIGINT poll)
- Step 2: batch emission specified; drag path interpolation
- Step 3: drag reconstruction state machine; control-key filtering; timestamp capture; SIGINT stop-flag poll; B1 limitation documented honestly
- Step 4: config flow → `scripter.configure()` with explicit CLI > env > default precedence; `exec(compile(...))` + warn-only AST pre-flight replacing raw runpy
- Step 5: tests expanded (gating, drag, exclusion, timing, config precedence, SIGINT)
- Risks: added R9 (import-time config), R10 (control-key leakage), R11 (SIGINT/CFRunLoop)
- RALPLAN-DR: Principle 1 honest about control boundary; A1 cons updated; A2 retained as deferred-viable; B1 cons updated
- Open questions 1-3: resolved and promoted/documented

**rev5 (Critic iteration-2 APPROVE — minor suggestions applied):**
- Scroll: added subprocess.run blocking invariant note (positioning must complete before Quartz wheel post)
- Scroll: trackpad momentum fidelity caveat added (high-magnitude trackpad deltas → line-unit replay may differ)
- Codegen: explicit statement that scroll dx is discarded by design; each on_scroll → one scroll() line (no coalescing); int()-coerce dy
- README: trackpad scroll caveat + horizontal scroll discard + scroll-before-use cursor note added to Step 5

**rev4 (Architect iteration-2 REVISE fixes):**
- scroll(): added `cliclick m:x,y` positioning BEFORE Quartz wheel post (CGEventCreateScrollWheelEvent has no location param; macOS hit-tests at cursor position)
- scroll(): changed `kCGScrollEventUnitPixel` → `kCGScrollEventUnitLine` (matches pynput line-count deltas)
- scroll dry-run: now emits `cliclick m:x,y` argv (testable) + `[scroll...]` sentinel — positioning is headlessly verified
- Added cursor-desync note: after scroll, cursor is at (x,y), so next get_cursor_pos() is correct
- Architecture boundary clarified: cliclick = movement authority everywhere; Quartz = wheel emission only
- AC count fixed: 14/14 → 17/17

**rev3 (Critic REJECT fixes):**
- scroll(): removed `cliclick s:` (does not exist in cliclick 5.1); replaced with pyobjc Quartz `CGEventCreateScrollWheelEvent`; added `pyobjc-framework-Quartz` dep
- drag interpolation: `m:` → `dm:` (drag-move) for all intermediate drag steps; AC-10/11 metric updated to count `dm:` tokens for drag
- key() decomposition: replaced `kp:`-only mapping with modifier-kd/ku wrap + named-key-kp + char-t decomposition; unit tests added
- Added cliclick capability pre-check at startup (R12) and `test_backend_capability.py` using `cliclick -m test`
- Added R13: `cliclick p` stderr WARNING banner — parse stdout only
- Decision C: added C3 (cliclick native `-e` easing) as deferred v2 option; `*(≥2 viable options)*` now 3 options
- `-w` 20ms floor documented in Step 2 and Risks
- Step 5: `test_backend_capability.py` and verification step 3b added
