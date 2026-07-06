import time
import pytest
from scripter.codegen import (
    render_click, render_drag, render_scroll, render_key, render_type_text,
    render_double_click, RecorderSession,
)


def test_render_click():
    assert render_click(760, 540) == 'click(760, 540)'


def test_render_drag():
    assert render_drag((300, 400), (500, 460)) == 'drag((300, 400), (500, 460))'


def test_render_scroll():
    assert render_scroll(100, 200, 3) == 'scroll(100, 200, 3)'


def test_render_key():
    assert render_key(['cmd', 'c']) == "key('cmd', 'c')"


def test_render_type_text():
    assert render_type_text('hello') == "type_text('hello')"


# --- RecorderSession state machine tests ---

class FakeSession(RecorderSession):
    """Subclass with controllable clock."""
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._fake_time = 0.0
        self.last_event_time = None

    def _now(self):
        return self._fake_time

    def _append(self, line):
        """Override to use fake time."""
        if not self.no_timing and self.last_event_time is not None:
            gap = self._fake_time - self.last_event_time
            if gap > self.SLEEP_THRESHOLD:
                self.lines.append(f'sleep({round(gap, 2):.2f})')
        self.lines.append(line)
        self.last_event_time = self._fake_time


def make_session(no_timing=False):
    s = FakeSession('/tmp/test_out.py', no_timing=no_timing)
    s.gate_on = True
    return s


def test_printable_keys_coalesce():
    s = make_session()
    s.on_key_press('h', False)
    s.on_key_press('i', False)
    s._flush_char_buffer()
    assert "type_text('hi')" in s.lines


def test_modifier_plus_char_no_coalesce():
    s = make_session()
    s.on_key_press('cmd', True)
    s.on_key_press('c', False)
    s._flush_char_buffer()
    assert any('key(' in line for line in s.lines)
    assert not any('type_text' in line for line in s.lines)


def test_gate_off_excludes_events():
    s = make_session()
    s.gate_on = False
    s.on_mouse_click(100, 200, 'left', True)
    s.on_mouse_click(100, 200, 'left', False)
    assert len(s.lines) == 0


def test_gate_on_off_on():
    s = make_session()
    # ON: click at (100,200)
    s.on_mouse_click(100, 200, 'left', True)
    s.on_mouse_click(100, 200, 'left', False)
    # OFF: click should not appear
    s.gate_on = False
    s.on_mouse_click(300, 400, 'left', True)
    s.on_mouse_click(300, 400, 'left', False)
    # ON: click at (500,600)
    s.gate_on = True
    s.on_mouse_click(500, 600, 'left', True)
    s.on_mouse_click(500, 600, 'left', False)
    assert len(s.lines) == 2
    assert 'click(100, 200)' in s.lines
    assert 'click(500, 600)' in s.lines


def test_ctrl_opt_excluded():
    s = make_session()
    # Simulate Ctrl+Opt toggle chord — should NOT appear in output
    s.on_key_press('ctrl', True)
    s.on_key_press('alt', True)
    s._flush_char_buffer()
    # Gate toggle is handled externally; codegen should not emit these modifiers
    # Check that no key() line was emitted for the toggle chord
    assert not any('ctrl' in line or 'alt' in line for line in s.lines)


def test_ctrl_c_excluded():
    s = make_session()
    s.on_key_press('ctrl', True)
    s.on_key_press('c', False)
    s._flush_char_buffer()
    assert s.lines == []


def test_scroll_dx_discarded():
    s = make_session()
    s.on_scroll(100, 200, dx=5, dy=3)
    assert 'scroll(100, 200, 3)' in s.lines


def test_drag_vs_click_threshold():
    s = make_session()
    # Large move → drag
    s.on_mouse_click(300, 400, 'left', True)
    s.on_mouse_move(350, 450)  # >5px
    s.on_mouse_click(350, 450, 'left', False)
    assert any('drag(' in line for line in s.lines)


def test_click_with_small_move():
    s = make_session()
    # Small move → click
    s.on_mouse_click(300, 400, 'left', True)
    s.on_mouse_move(302, 402)  # <5px
    s.on_mouse_click(302, 402, 'left', False)
    assert any('click(' in line for line in s.lines)
    assert not any('drag(' in line for line in s.lines)


def test_timing_gap_emits_sleep():
    s = make_session()
    s._fake_time = 0.0
    s.last_event_time = 0.0
    s.on_mouse_click(100, 200, 'left', True)
    s.on_mouse_click(100, 200, 'left', False)
    s._fake_time = 0.25  # 250ms gap
    s.on_mouse_click(300, 400, 'left', True)
    s.on_mouse_click(300, 400, 'left', False)
    assert any('sleep(0.25)' in line for line in s.lines)


def test_toggle_gate_comments():
    s = RecorderSession('/tmp/test.py', no_timing=True)
    # First open: "recording started"
    s.toggle_gate()
    assert s.lines[0] == '# --- recording started ---'
    s.on_mouse_click(100, 200, 'left', True)
    s.on_mouse_click(100, 200, 'left', False)
    # Pause
    s.toggle_gate()
    assert s.lines[-1] == '# --- paused ---'
    # Resume: "resumed"
    s.toggle_gate()
    assert s.lines[-1] == '# --- resumed ---'


def test_no_timing_suppresses_sleep():
    s = make_session(no_timing=True)
    s._fake_time = 0.0
    s.last_event_time = 0.0
    s.on_mouse_click(100, 200, 'left', True)
    s.on_mouse_click(100, 200, 'left', False)
    s._fake_time = 0.25
    s.on_mouse_click(300, 400, 'left', True)
    s.on_mouse_click(300, 400, 'left', False)
    assert not any('sleep' in line for line in s.lines)


def test_render_double_click():
    assert render_double_click(760, 540) == 'double_click(760, 540)'


def test_double_click_detected():
    """Two rapid clicks at the same spot → single double_click() line."""
    s = RecorderSession('/tmp/test.py', no_timing=True)
    s.gate_on = True
    s.on_mouse_click(300, 400, 'left', True)
    s.on_mouse_click(300, 400, 'left', False)
    # Second click within threshold
    s._last_click_time -= 0.1  # make sure it's well within 0.5s
    s.on_mouse_click(302, 401, 'left', True)
    s.on_mouse_click(302, 401, 'left', False)
    assert s.lines == ['double_click(302, 401)']


def test_double_click_not_detected_too_slow():
    """Two clicks too far apart in time → two separate click() lines."""
    s = RecorderSession('/tmp/test.py', no_timing=True)
    s.gate_on = True
    s.on_mouse_click(300, 400, 'left', True)
    s.on_mouse_click(300, 400, 'left', False)
    # Push first click time far into the past
    s._last_click_time -= 1.0
    s.on_mouse_click(300, 400, 'left', True)
    s.on_mouse_click(300, 400, 'left', False)
    assert s.lines.count('click(300, 400)') == 2


def test_double_click_not_detected_too_far():
    """Two clicks close in time but far apart in space → two separate click() lines."""
    s = RecorderSession('/tmp/test.py', no_timing=True)
    s.gate_on = True
    s.on_mouse_click(300, 400, 'left', True)
    s.on_mouse_click(300, 400, 'left', False)
    s._last_click_time -= 0.1
    s.on_mouse_click(400, 500, 'left', True)  # >10px away
    s.on_mouse_click(400, 500, 'left', False)
    assert 'click(300, 400)' in s.lines
    assert 'click(400, 500)' in s.lines
