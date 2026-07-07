import math
import os
import shlex
import subprocess
import time

from .backend import KP_KEYS, MODIFIER_KEYS

# The Ctrl+Opt toggle chord — never recorded
EXCLUDED_CHORDS = frozenset({'ctrl', 'alt'})


def render_click(x: float, y: float) -> str:
    return f'click({round(x)}, {round(y)})'


def render_right_click(x: float, y: float) -> str:
    return f'right_click({round(x)}, {round(y)})'


def render_double_click(x: float, y: float) -> str:
    return f'double_click({round(x)}, {round(y)})'


def render_drag(start: tuple[float, float], end: tuple[float, float]) -> str:
    return f'drag(({round(start[0])}, {round(start[1])}), ({round(end[0])}, {round(end[1])}))'


def render_scroll(x: float, y: float, amount: int) -> str:
    return f'scroll({round(x)}, {round(y)}, {amount})'


def render_key(keys: list[str]) -> str:
    parts = ', '.join(f"'{k}'" for k in keys)
    return f'key({parts})'


def render_type_text(text: str) -> str:
    escaped = text.replace("'", "\\'")
    return f"type_text('{escaped}')"


def render_move(x: float, y: float) -> str:
    return f'move({round(x)}, {round(y)})'


def render_sleep(seconds: float) -> str:
    return f'sleep({seconds:.2f})'


class RecorderSession:
    """State machine that converts raw pynput events into DSL source lines."""

    # Movement threshold to distinguish click from drag (pixels)
    DRAG_THRESHOLD = 5
    # Minimum gap (seconds) to emit a sleep() between events
    SLEEP_THRESHOLD = 0.15
    # Double-click detection window
    DOUBLE_CLICK_THRESHOLD = 0.5   # seconds
    DOUBLE_CLICK_RADIUS = 10       # pixels

    def __init__(self, output_path: str, no_timing: bool = False):
        self.output_path = output_path
        self.no_timing = no_timing
        self.gate_on = False
        self.lines: list[str] = []
        self.last_event_time: float | None = None

        # Drag state machine
        self._press_pos: tuple[int, int] | None = None
        self._moved_significantly = False

        # Keystroke coalescing
        self._char_buffer: list[str] = []

        # Currently held modifiers (for gate toggle detection)
        self._held_modifiers: set[str] = set()

        # Double-click detection
        self._last_click_time: float | None = None
        self._last_click_pos: tuple[int, int] | None = None

    def _flush_char_buffer(self):
        if self._char_buffer:
            text = ''.join(self._char_buffer)
            self._append(render_type_text(text))
            self._char_buffer = []

    def _append(self, line: str):
        """Append a DSL line, optionally prefixed with a sleep()."""
        now = time.monotonic()
        if not self.no_timing and self.last_event_time is not None:
            gap = now - self.last_event_time
            if gap > self.SLEEP_THRESHOLD:
                self.lines.append(render_sleep(round(gap, 2)))
        self.lines.append(line)
        self.last_event_time = now

    def on_key_press(self, key_name: str, is_modifier: bool):
        """Called when a key is pressed."""
        if not self.gate_on:
            return
        if is_modifier:
            self._held_modifiers.add(key_name)
            return

        if len(key_name) == 1 and key_name.isprintable():
            active_mods = self._held_modifiers - EXCLUDED_CHORDS
            if self._held_modifiers and not active_mods:
                return  # only excluded-chord modifiers held (e.g. Ctrl+C)
            if active_mods == {'shift'}:
                # pynput already gives us the shifted char (e.g. 'N'); just buffer it
                self._char_buffer.append(key_name)
            elif active_mods:
                self._flush_char_buffer()
                self._append(render_key(sorted(active_mods) + [key_name]))
            else:
                self._char_buffer.append(key_name)
        elif key_name == 'space':
            # Space alone → typed character; space + modifier → key combo (e.g. Cmd+Space)
            active_mods = self._held_modifiers - EXCLUDED_CHORDS
            if active_mods:
                self._flush_char_buffer()
                self._append(render_key(sorted(active_mods) + ['space']))
            else:
                self._char_buffer.append(' ')
        elif key_name in KP_KEYS:
            self._flush_char_buffer()
            active_mods = self._held_modifiers - EXCLUDED_CHORDS
            if active_mods:
                all_keys = sorted(active_mods) + [key_name]
            else:
                all_keys = [key_name]
            self._append(render_key(all_keys))
        # Otherwise: unknown key, skip

    def on_key_release(self, key_name: str, is_modifier: bool):
        if is_modifier and key_name in self._held_modifiers:
            self._held_modifiers.discard(key_name)

    def _remove_last_click_and_sleep(self):
        """Pop the most recent click() and any immediately preceding sleep() from lines."""
        while self.lines and self.lines[-1].startswith('sleep('):
            self.lines.pop()
        if self.lines and self.lines[-1].startswith('click('):
            self.lines.pop()

    def on_mouse_click(self, x: int, y: int, button: str, pressed: bool):
        """Called on mouse press/release."""
        if not self.gate_on:
            return
        if pressed:
            self._press_pos = (x, y)
            self._moved_significantly = False
            self._last_move_pos = (x, y)
        else:
            if self._press_pos is not None:
                if self._moved_significantly:
                    self._flush_char_buffer()
                    self._append(render_drag(self._press_pos, (x, y)))
                    self._last_click_time = None
                    self._last_click_pos = None
                elif button == 'right':
                    self._flush_char_buffer()
                    self._append(render_right_click(x, y))
                    self._last_click_time = None
                    self._last_click_pos = None
                else:
                    now = time.monotonic()
                    if (self._last_click_time is not None
                            and now - self._last_click_time < self.DOUBLE_CLICK_THRESHOLD
                            and math.hypot(x - self._last_click_pos[0], y - self._last_click_pos[1]) < self.DOUBLE_CLICK_RADIUS):
                        self._flush_char_buffer()
                        self._remove_last_click_and_sleep()
                        self.lines.append(render_double_click(x, y))
                        self.last_event_time = now
                        self._last_click_time = None
                        self._last_click_pos = None
                    else:
                        self._flush_char_buffer()
                        self._append(render_click(x, y))
                        self._last_click_time = now
                        self._last_click_pos = (x, y)
                self._press_pos = None
                self._last_move_pos = None

    def on_mouse_move(self, x: int, y: int):
        if self._press_pos is not None and not self._moved_significantly:
            px, py = self._press_pos
            if math.hypot(x - px, y - py) >= self.DRAG_THRESHOLD:
                self._moved_significantly = True

    def on_move_marker(self, x: int, y: int):
        """Emit move() for the current cursor position (triggered by Fn+Shift)."""
        if not self.gate_on:
            return
        self._flush_char_buffer()
        self._append(render_move(x, y))
        print(f'→ move({round(x)}, {round(y)})', flush=True)

    def on_scroll(self, x: int, y: int, dx: int, dy: int):
        """Called on scroll event. dx is discarded; dy is the line count."""
        if not self.gate_on:
            return
        amount = int(dy)
        if amount != 0:
            self._flush_char_buffer()
            self._append(render_scroll(x, y, amount))

    def toggle_gate(self):
        """Toggle recording on/off."""
        self._flush_char_buffer()
        self.gate_on = not self.gate_on
        if self.gate_on:
            self.lines.append('# --- resumed ---' if self.lines else '# --- recording started ---')
            self.last_event_time = time.monotonic()
            print('● RECORDING', flush=True)
        else:
            self.lines.append('# --- paused ---')
            print('⏸ PAUSED', flush=True)

    def write_script(self) -> str:
        """Write the generated script to output_path and return the path."""
        self._flush_char_buffer()
        header = 'from scripter import *\n\n'
        content = header + '\n'.join(self.lines) + '\n'
        with open(self.output_path, 'w') as f:
            f.write(content)
        return self.output_path

    def flush_to_file(self):
        """Write the generated script and open $EDITOR (used in no-menubar mode)."""
        path = self.write_script()
        print(f'\nScript written to: {path}', flush=True)
        editor = os.environ.get('EDITOR', 'vi')
        subprocess.run(f'{editor} {shlex.quote(path)}', shell=True)
