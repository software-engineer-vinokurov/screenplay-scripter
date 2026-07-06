"""Additional gating tests at the recorder level."""
from scripter.codegen import RecorderSession
from scripter.recorder import _PYNPUT_TO_CLICLICK, _key_name


def test_on_scroll_gate_off():
    s = RecorderSession('/tmp/test.py')
    s.gate_on = False
    s.on_scroll(100, 200, dx=0, dy=3)
    assert len(s.lines) == 0


def test_on_scroll_gate_on():
    s = RecorderSession('/tmp/test.py', no_timing=True)
    s.gate_on = True
    s.on_scroll(100, 200, dx=0, dy=3)
    assert 'scroll(100, 200, 3)' in s.lines


def test_scroll_dy_int_coercion():
    s = RecorderSession('/tmp/test.py', no_timing=True)
    s.gate_on = True
    s.on_scroll(100, 200, dx=0, dy=2.7)  # float dy → int
    assert 'scroll(100, 200, 2)' in s.lines


def test_pynput_key_name_translations():
    assert _PYNPUT_TO_CLICLICK['enter'] == 'return'
    assert _PYNPUT_TO_CLICLICK['escape'] == 'esc'
    assert _PYNPUT_TO_CLICLICK['up'] == 'arrow-up'
    assert _PYNPUT_TO_CLICLICK['down'] == 'arrow-down'
    assert _PYNPUT_TO_CLICLICK['left'] == 'arrow-left'
    assert _PYNPUT_TO_CLICLICK['right'] == 'arrow-right'
    assert _PYNPUT_TO_CLICLICK['backspace'] == 'delete'
    assert _PYNPUT_TO_CLICLICK['delete'] == 'fwd-delete'
    assert _PYNPUT_TO_CLICLICK['page_up'] == 'page-up'
    assert _PYNPUT_TO_CLICLICK['page_down'] == 'page-down'


def test_enter_key_recorded_as_return():
    """pynput Key.enter must produce key('return') in the script."""
    s = RecorderSession('/tmp/test.py', no_timing=True)
    s.gate_on = True
    s.on_key_press('return', is_modifier=False)  # after translation
    assert "key('return')" in s.lines
