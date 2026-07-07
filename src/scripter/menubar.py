import os
import re
import shlex
import subprocess
import threading
from pathlib import Path

try:
    import rumps
    from rumps import events as rumps_events
    RUMPS_AVAILABLE = True
except ImportError:
    RUMPS_AVAILABLE = False

_SLEEP_LINE_RE = re.compile(r'^sleep\((\d+(?:\.\d+)?)\)\s*$')


def _prescan_sleeps(script_path: Path) -> list[dict]:
    """Return all commented-out sleep lines, sorted ascending by lineno.

    Active sleeps surface dynamically via on_sleep as they execute.  This
    pre-scan only collects previously-commented ones so they can be revealed
    progressively as the player walks past their line numbers.
    """
    pauses = []
    try:
        lines = script_path.read_text().splitlines()
    except OSError:
        return []
    for lineno, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith('#'):
            m = _SLEEP_LINE_RE.match(stripped[1:].strip())
            if m:
                pauses.append({'lineno': lineno, 'seconds': float(m.group(1)), 'commented': True})
    pauses.sort(key=lambda p: p['lineno'])  # ascending — flushed progressively
    return pauses


_TITLE_PAUSED = '○ rec'
_TITLE_REC_A  = '● REC'
_TITLE_REC_B  = '○ REC'


class RecordingMenuBarApp(rumps.App):

    def __init__(self, session, kb_listener, ms_listener):
        super().__init__(_TITLE_PAUSED, quit_button=None)
        self.session = session
        self.kb_listener = kb_listener
        self.ms_listener = ms_listener
        self._blink_state = False
        self._done = False        # True once cleanup has been performed
        self._open_editor = True  # False only for "Quit (discard)"

        self._status_item = rumps.MenuItem('⏸  Paused')
        self.menu = [
            self._status_item,
            None,
            rumps.MenuItem('Stop & Edit', callback=self._stop_and_edit),
            rumps.MenuItem('Quit (discard)', callback=self._quit_discard),
        ]

        self._timer = rumps.Timer(self._tick, 0.5)
        self._timer.start()

        # Ctrl+C → machInterrupt → NSApp.terminate_() → applicationWillTerminate_
        # → before_quit fires here, giving us a chance to save before the process exits.
        rumps_events.before_quit.register(self._on_before_quit)

    def _on_before_quit(self):
        """Runs from applicationWillTerminate_ before any exit (Ctrl+C or menu quit)."""
        if self._done:
            return
        self._done = True
        self._timer.stop()
        self.kb_listener.stop()
        self.ms_listener.stop()
        if self._open_editor:
            path = self.session.write_script()
            print(f'\nScript written to: {path}', flush=True)
            _open_in_iterm(path)

    def _tick(self, _):
        if self.session.gate_on:
            self._blink_state = not self._blink_state
            self.title = _TITLE_REC_A if self._blink_state else _TITLE_REC_B
            self._status_item.title = '🔴  Recording…'
        else:
            self.title = _TITLE_PAUSED
            self._status_item.title = '⏸  Paused'

    def _stop_and_edit(self, _):
        self._finish(open_editor=True)

    def _quit_discard(self, _):
        self._finish(open_editor=False)

    def _finish(self, open_editor: bool):
        if self._done:
            return
        self._open_editor = open_editor
        # _on_before_quit will do the actual work when terminate_() fires it
        rumps.quit_application()


def _open_in_iterm(path: str):
    editor = os.environ.get('EDITOR', 'vi')
    # Build the shell command: editor string + quoted path.
    # The shell (not exec) will parse it, so options and empty-string args work.
    cmd = f'{editor} {shlex.quote(path)}'
    # Escape for AppleScript double-quoted string (" → \")
    cmd_as = cmd.replace('\\', '\\\\').replace('"', '\\"')

    # Open a normal login-shell window, then send the command via write text.
    # write text goes through the shell so quoting is interpreted correctly.
    # (Using "command" in create window execs the string directly, bypassing quoting.)
    iterm_script = (
        'tell application "iTerm"\n'
        '    activate\n'
        '    set newWindow to (create window with default profile)\n'
        '    tell current session of newWindow\n'
        f'        write text "{cmd_as}"\n'
        '    end tell\n'
        'end tell'
    )
    result = subprocess.run(['osascript', '-e', iterm_script], capture_output=True)
    if result.returncode != 0:
        terminal_script = (
            'tell application "Terminal"\n'
            '    activate\n'
            f'    do script "{cmd_as}"\n'
            'end tell'
        )
        subprocess.run(['osascript', '-e', terminal_script], check=False)


class ReviewMenuBarApp(rumps.App):
    """Menu bar indicator for script playback review mode."""

    _PLAY  = '▶'
    _PAUSE = '⏸'
    _MAX_PAUSES = 10

    def __init__(self, script_path: Path, pause_event, stop_event):
        super().__init__(f'{self._PLAY} {script_path.name}', quit_button=None)
        self._script_path = script_path
        self._pause_event = pause_event
        self._stop_event  = stop_event
        self._current_line = 0
        self._total_lines  = 0
        self._done = False
        self.player_done = threading.Event()

        # Commented sleeps pending revelation (flushed as player walks past them)
        self._pending_commented: list[dict] = _prescan_sleeps(script_path)  # ascending
        self._pauses: list[dict] = []   # [{lineno, seconds, commented}], newest first
        self._pauses_lock = threading.Lock()
        self._pauses_dirty = False

        self._status_item = rumps.MenuItem('Starting…')
        self._pauses_menu = rumps.MenuItem('Previous Pauses')

        self.menu = [
            self._status_item,
            None,
            rumps.MenuItem('Pause / Resume  (Ctrl+Opt)', callback=self._toggle_pause),
            rumps.MenuItem('Stop', callback=self._stop_playback),
            None,
            self._pauses_menu,
        ]

        self._timer = rumps.Timer(self._tick, 0.2)
        self._timer.start()
        rumps_events.before_quit.register(self._on_before_quit)

    def update_progress(self, stmt_idx: int, total_stmts: int, lineno: int, total_lines: int):
        """Thread-safe; called from the player thread between statements."""
        self._current_line = lineno
        self._total_lines  = total_lines
        self._flush_commented_before(lineno)

    def _flush_commented_before(self, current_lineno: int) -> None:
        """Move pre-scanned commented sleeps whose line < current_lineno into _pauses."""
        with self._pauses_lock:
            to_add = [s for s in self._pending_commented if s['lineno'] < current_lineno]
            if not to_add:
                return
            self._pending_commented = [s for s in self._pending_commented
                                       if s['lineno'] >= current_lineno]
            combined = self._pauses + to_add
            combined.sort(key=lambda p: p['lineno'], reverse=True)
            self._pauses = combined[:self._MAX_PAUSES]
            self._pauses_dirty = True

    def add_sleep(self, lineno: int, seconds: float):
        """Thread-safe; called from the player thread when a sleep() executes."""
        with self._pauses_lock:
            if any(p['lineno'] == lineno for p in self._pauses):
                return  # already revealed by _flush_commented_before
            # Remove from pending in case this sleep was pre-scanned as commented
            # but was uncommented between sessions and is now active
            self._pending_commented = [s for s in self._pending_commented
                                       if s['lineno'] != lineno]
            self._pauses.insert(0, {'lineno': lineno, 'seconds': seconds, 'commented': False})
            if len(self._pauses) > self._MAX_PAUSES:
                self._pauses = self._pauses[:self._MAX_PAUSES]
            self._pauses_dirty = True

    def toggle_pause_flag(self):
        """Thread-safe pause toggle (safe to call from pynput thread)."""
        if self._pause_event.is_set():
            self._pause_event.clear()
        else:
            self._pause_event.set()

    def _toggle_pause(self, _):
        self.toggle_pause_flag()

    def _stop_playback(self, _):
        self._stop_event.set()

    def _make_pause_callback(self, pause: dict):
        def cb(_):
            self._toggle_pause_comment(pause)
            self._rebuild_pauses_menu()
        return cb

    def _toggle_pause_comment(self, pause: dict):
        """Comment or uncomment the sleep() line in the script file."""
        lines = self._script_path.read_text().splitlines(keepends=True)
        idx = pause['lineno'] - 1
        line = lines[idx]
        if pause['commented']:
            lines[idx] = line[2:] if line.startswith('# ') else line
        else:
            lines[idx] = '# ' + line
        self._script_path.write_text(''.join(lines))
        pause['commented'] = not pause['commented']
        self._pauses_dirty = True

    def _rebuild_pauses_menu(self):
        """Rebuild the Previous Pauses submenu (must be called from the main thread)."""
        if self._pauses_menu._menu is not None:
            for key in list(self._pauses_menu.keys()):
                del self._pauses_menu[key]

        with self._pauses_lock:
            pauses = list(self._pauses)

        if not pauses:
            self._pauses_menu.add(rumps.MenuItem('(none yet)'))
            return

        seen: set[str] = set()
        for pause in pauses:
            base = f'# {pause["seconds"]:.2f}' if pause['commented'] else f'{pause["seconds"]:.2f}'
            # Append invisible word-joiners to disambiguate duplicate durations
            label = base
            while label in seen:
                label += '⁠'
            seen.add(label)
            item = rumps.MenuItem(label, callback=self._make_pause_callback(pause))
            if label != base:
                item._menuitem.setTitle_(base)
            self._pauses_menu.add(item)

    def _tick(self, _):
        if self._pauses_dirty:
            self._pauses_dirty = False
            self._rebuild_pauses_menu()

        paused = self._pause_event.is_set()
        icon   = self._PAUSE if paused else self._PLAY
        line   = self._current_line
        total  = self._total_lines
        if total:
            self.title = f'{icon} {line}/{total}'
            self._status_item.title = '⏸ Paused' if paused else f'▶ Line {line} of {total}'
        if self.player_done.is_set() and not self._done:
            self._done = True
            self._timer.stop()
            rumps.quit_application()

    def _on_before_quit(self):
        if not self._done:
            self._done = True
            self._stop_event.set()
            self._timer.stop()


def run_with_review_menubar(script_path, play_fn) -> None:
    """Run the player with a menu-bar progress indicator and Ctrl+Opt pause/resume."""
    _name = script_path.name
    _ln_play  = f'▶ Playing {_name}  —  Ctrl+Opt: pause/resume'
    _ln_pause = f'⏸ Paused  {_name}  —  Ctrl+Opt: pause/resume'
    print(_ln_play, end='', flush=True)

    from pynput import keyboard as kb

    pause_event = threading.Event()
    stop_event  = threading.Event()
    app = ReviewMenuBarApp(script_path, pause_event, stop_event)

    _active_mods   = set()
    _toggle_armed  = False

    def on_key_press(key):
        nonlocal _toggle_armed
        try:
            name = key.name.removesuffix('_r')
            if name in ('ctrl', 'alt'):
                _active_mods.add(name)
            if {'ctrl', 'alt'}.issubset(_active_mods) and not _toggle_armed:
                _toggle_armed = True
                app.toggle_pause_flag()
                status = _ln_pause if app._pause_event.is_set() else _ln_play
                print(f'\r{status}', end='', flush=True)
        except AttributeError:
            pass

    def on_key_release(key):
        nonlocal _toggle_armed
        try:
            name = key.name.removesuffix('_r')
            _active_mods.discard(name)
            if not {'ctrl', 'alt'}.issubset(_active_mods):
                _toggle_armed = False
        except AttributeError:
            pass

    kb_listener = kb.Listener(on_press=on_key_press, on_release=on_key_release)
    kb_listener.start()

    def _player():
        play_fn(on_progress=app.update_progress, on_sleep=app.add_sleep,
                pause_event=pause_event, stop_event=stop_event)
        app.player_done.set()

    t = threading.Thread(target=_player, daemon=True)
    t.start()

    app.run()
    print(flush=True)  # terminate the status line

    if not app._done:
        app._done = True
        stop_event.set()

    kb_listener.stop()
    t.join(timeout=2)


def run_with_killswitch(play_fn) -> None:
    """Run the player with a Ctrl+Opt kill-switch that aborts playback.

    No menu bar required.  The player runs on the main thread; a background
    pynput listener sets stop_event the moment Ctrl+Opt is pressed.
    """
    _ln_play = '▶ Playing  —  Ctrl+Opt: stop'
    _ln_stop = '⏹ Stopped  —  Ctrl+Opt: stop'
    print(_ln_play, end='', flush=True)

    from pynput import keyboard as kb

    stop_event   = threading.Event()
    _active_mods = set()
    _armed       = False

    def on_key_press(key):
        nonlocal _armed
        try:
            name = key.name.removesuffix('_r')
            if name in ('ctrl', 'alt'):
                _active_mods.add(name)
            if {'ctrl', 'alt'}.issubset(_active_mods) and not _armed:
                _armed = True
                stop_event.set()
                print(f'\r{_ln_stop}', end='', flush=True)
        except AttributeError:
            pass

    def on_key_release(key):
        nonlocal _armed
        try:
            name = key.name.removesuffix('_r')
            _active_mods.discard(name)
            if not {'ctrl', 'alt'}.issubset(_active_mods):
                _armed = False
        except AttributeError:
            pass

    kb_listener = kb.Listener(on_press=on_key_press, on_release=on_key_release)
    kb_listener.start()
    try:
        play_fn(stop_event=stop_event)
    finally:
        print(flush=True)  # terminate the status line
        kb_listener.stop()


def run_with_menubar(session, kb_listener, ms_listener):
    """Run the recording session with a menu bar indicator. Blocks until stopped."""
    app = RecordingMenuBarApp(session, kb_listener, ms_listener)
    app.run()

    # Fallback: if machInterrupt called stopper.stop() instead of terminate_(),
    # app.run() returns here without applicationWillTerminate_ firing.
    if not app._done:
        app._done = True
        app._timer.stop()
        kb_listener.stop()
        ms_listener.stop()
        path = session.write_script()
        print(f'\nScript written to: {path}', flush=True)
        _open_in_iterm(path)
