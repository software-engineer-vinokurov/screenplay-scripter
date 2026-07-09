# Open Questions

## screenplay-scripter - 2026-07-06
- [ ] Recording indicator: stdout-only (B1) acceptable for v1, or is a rumps menubar (B2) required? — Determines whether we take on the rumps dep + NSApplication runloop complexity alongside pynput.
- [ ] `type_text` keystroke coalescing: coalesce printable chars into one `type_text(...)`, or strict one-`key()`-per-event? — Trades script readability against capture fidelity (AC-12).
- [ ] Should recording auto-capture inter-event delays as `sleep()` calls, or only honor user-authored sleeps? — Spec defines `sleep(seconds)` but is silent on timing capture; affects replay realism.
