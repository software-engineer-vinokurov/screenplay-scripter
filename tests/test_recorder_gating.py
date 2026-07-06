"""Additional gating tests at the recorder level."""
from scripter.codegen import RecorderSession


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
