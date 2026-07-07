"""Tests for the review-mode Previous Pauses feature and related fixes."""
import threading
from pathlib import Path
import pytest
from scripter.player import play_script_stepped, _get_sleep_duration
import ast


# --- _get_sleep_duration unit tests ---

def _stmt(src):
    return ast.parse(src).body[0]


def test_get_sleep_duration_basic():
    assert _get_sleep_duration(_stmt('sleep(7.38)')) == pytest.approx(7.38)


def test_get_sleep_duration_int():
    assert _get_sleep_duration(_stmt('sleep(2)')) == pytest.approx(2.0)


def test_get_sleep_duration_non_sleep():
    assert _get_sleep_duration(_stmt('click(100, 200)')) is None


def test_get_sleep_duration_non_call():
    assert _get_sleep_duration(_stmt('x = 1')) is None


# --- on_sleep callback integration via play_script_stepped ---

def _write_script(tmp_path: Path, lines: list[str]) -> Path:
    p = tmp_path / 'script.py'
    p.write_text('from scripter import *\n' + '\n'.join(lines) + '\n')
    return p


def test_on_sleep_fires_for_sleep_stmts(tmp_path):
    script = _write_script(tmp_path, ['sleep(1.50)', 'sleep(0.25)'])
    collected = []
    play_script_stepped(script, on_sleep=lambda ln, s: collected.append((ln, s)))
    assert len(collected) == 2
    assert collected[0][1] == pytest.approx(1.50)
    assert collected[1][1] == pytest.approx(0.25)


def test_on_sleep_not_fired_for_non_sleep(tmp_path):
    script = _write_script(tmp_path, ['click(100, 200)'])
    collected = []
    play_script_stepped(script, on_sleep=lambda ln, s: collected.append(s),
                        stop_event=threading.Event())
    assert collected == []


def test_on_sleep_lineno_matches_file(tmp_path):
    script = _write_script(tmp_path, ['click(1, 1)', 'sleep(3.00)', 'click(2, 2)'])
    collected = []
    play_script_stepped(script, on_sleep=lambda ln, s: collected.append(ln))
    assert len(collected) == 1
    # 'from scripter import *' is line 1, 'click(1,1)' is line 2, 'sleep' is line 3
    assert collected[0] == 3


# --- comment-toggle logic (file editing) ---

def _make_pause(lineno, seconds, commented=False):
    return {'lineno': lineno, 'seconds': seconds, 'commented': commented}


def test_comment_toggle_comments_line(tmp_path):
    script = tmp_path / 's.py'
    script.write_text('from scripter import *\nsleep(7.38)\n')
    pause = _make_pause(lineno=2, seconds=7.38)

    # Simulate _toggle_pause_comment logic
    lines = script.read_text().splitlines(keepends=True)
    idx = pause['lineno'] - 1
    lines[idx] = '# ' + lines[idx]
    script.write_text(''.join(lines))
    pause['commented'] = True

    assert script.read_text().splitlines()[1] == '# sleep(7.38)'
    assert pause['commented'] is True


def test_comment_toggle_uncomments_line(tmp_path):
    script = tmp_path / 's.py'
    script.write_text('from scripter import *\n# sleep(7.38)\n')
    pause = _make_pause(lineno=2, seconds=7.38, commented=True)

    lines = script.read_text().splitlines(keepends=True)
    idx = pause['lineno'] - 1
    line = lines[idx]
    lines[idx] = line[2:] if line.startswith('# ') else line
    script.write_text(''.join(lines))
    pause['commented'] = False

    assert script.read_text().splitlines()[1] == 'sleep(7.38)'
    assert pause['commented'] is False


def test_prescan_ignores_active_sleeps(tmp_path):
    """Pre-scan only returns commented sleeps; active ones come in via on_sleep."""
    script = _write_script(tmp_path, ['sleep(7.38)', 'sleep(1.00)'])
    from scripter.menubar import _prescan_sleeps
    assert _prescan_sleeps(script) == []


def test_prescan_finds_commented_sleeps(tmp_path):
    script = tmp_path / 'script.py'
    script.write_text('from scripter import *\n# sleep(7.38)\nsleep(1.00)\n')
    from scripter.menubar import _prescan_sleeps
    pauses = _prescan_sleeps(script)
    assert len(pauses) == 1
    assert pauses[0]['seconds'] == pytest.approx(7.38)
    assert pauses[0]['commented'] is True


def test_prescan_returns_all_commented_no_cap(tmp_path):
    lines = [f'# sleep({i}.00)' for i in range(15)]
    script = _write_script(tmp_path, lines)
    from scripter.menubar import _prescan_sleeps
    pauses = _prescan_sleeps(script)
    assert len(pauses) == 15  # no cap — all kept for progressive flush


def test_prescan_ascending_order(tmp_path):
    script = tmp_path / 's.py'
    script.write_text('# sleep(1.00)\n# sleep(2.00)\n# sleep(3.00)\n')
    from scripter.menubar import _prescan_sleeps
    pauses = _prescan_sleeps(script)
    assert [p['seconds'] for p in pauses] == pytest.approx([1.0, 2.0, 3.0])


def test_prescan_ignores_non_sleep_comments(tmp_path):
    script = tmp_path / 's.py'
    script.write_text('# click(1, 1)\n# --- section ---\n# sleep(1.00)\n')
    from scripter.menubar import _prescan_sleeps
    pauses = _prescan_sleeps(script)
    assert len(pauses) == 1
    assert pauses[0]['seconds'] == pytest.approx(1.00)


def test_flush_commented_before_lineno(tmp_path):
    """Commented sleeps appear in _pauses only after the player walks past them."""
    script = tmp_path / 's.py'
    # lines: 1=import, 2=# sleep(1.00), 3=# sleep(2.00), 4=# sleep(3.00)
    script.write_text('from scripter import *\n# sleep(1.00)\n# sleep(2.00)\n# sleep(3.00)\n')
    from scripter.menubar import ReviewMenuBarApp
    import threading
    app = ReviewMenuBarApp.__new__(ReviewMenuBarApp)
    app._script_path = script
    from scripter.menubar import _prescan_sleeps
    app._pending_commented = _prescan_sleeps(script)
    app._pauses = []
    app._pauses_lock = threading.Lock()
    app._pauses_dirty = False
    app._MAX_PAUSES = 10

    # At lineno=2 (about to execute line 2): nothing has been passed yet
    app._flush_commented_before(2)
    assert app._pauses == []

    # At lineno=3: line 2 (sleep 1.00) has been passed
    app._flush_commented_before(3)
    assert len(app._pauses) == 1
    assert app._pauses[0]['seconds'] == pytest.approx(1.00)

    # At lineno=5: lines 3 and 4 both passed
    app._flush_commented_before(5)
    assert len(app._pauses) == 3
    # Newest first (highest lineno first)
    assert [p['seconds'] for p in app._pauses] == pytest.approx([3.0, 2.0, 1.0])


def test_add_sleep_caps_at_ten(tmp_path):
    """add_sleep should keep only the 10 most recent pauses."""
    # Simulate ReviewMenuBarApp._pauses logic directly
    pauses = []
    MAX = 10

    def add_sleep(lineno, seconds):
        pauses.insert(0, {'lineno': lineno, 'seconds': seconds, 'commented': False})
        if len(pauses) > MAX:
            del pauses[MAX:]

    for i in range(15):
        add_sleep(i + 1, float(i))

    assert len(pauses) == 10
    # Most recent (lineno=15, seconds=14.0) should be first
    assert pauses[0]['lineno'] == 15
    assert pauses[-1]['lineno'] == 6
