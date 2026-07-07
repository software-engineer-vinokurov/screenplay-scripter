import threading
import signal
import sys
from .codegen import RecorderSession, MODIFIER_KEYS

try:
    from pynput import keyboard, mouse
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False


# pynput → cliclick key name translation
_PYNPUT_TO_CLICLICK = {
    'enter':     'return',
    'escape':    'esc',
    'backspace': 'delete',
    'delete':    'fwd-delete',
    'up':        'arrow-up',
    'down':      'arrow-down',
    'left':      'arrow-left',
    'right':     'arrow-right',
    'page_up':   'page-up',
    'page_down': 'page-down',
    'num_lock':  '',   # no cliclick equivalent, drop it
}


def _key_name(key) -> tuple[str, bool]:
    """Return (name, is_modifier) for a pynput key."""
    try:
        # Special key (e.g. Key.space, Key.cmd)
        name = key.name  # e.g. 'cmd', 'space', 'ctrl', 'alt'
        # pynput reports the Fn/Globe key as 'function' on macOS
        is_mod = name in MODIFIER_KEYS or name in {'cmd_r', 'ctrl_r', 'alt_r', 'shift_r', 'fn', 'function'}
        # Normalize right-side modifiers and pynput-specific names
        name = name.removesuffix('_r')  # cmd_r → cmd, etc.
        name = {'ctrl': 'ctrl', 'alt': 'alt', 'cmd': 'cmd', 'shift': 'shift',
                'fn': 'fn', 'function': 'fn'}.get(name, name)
        # Translate pynput names to cliclick names
        name = _PYNPUT_TO_CLICLICK.get(name, name)
        return name, is_mod
    except AttributeError:
        # Regular key with char
        try:
            char = key.char
            if char is None:
                return '', False
            return char, False
        except AttributeError:
            return '', False


def run_recording(output_path: str, no_timing: bool = False, use_menubar: bool = True):
    """Start a recording session. Blocks until stopped."""
    if not PYNPUT_AVAILABLE:
        print("ERROR: pynput not installed. Run: uv add pynput", file=sys.stderr)
        sys.exit(1)

    session = RecorderSession(output_path, no_timing=no_timing)
    stop_flag = threading.Event()

    print(f'Ready to record → {output_path}')
    print('  Ctrl+Opt:         toggle recording ON/OFF')
    print('  Ctrl+Opt+Shift:   insert move() for current cursor position')
    if use_menubar:
        print('  Menu bar: "Stop & Edit" to finish, "Quit (discard)" to abort')
    else:
        print('  Ctrl+C: end session and open script in $EDITOR')
    print('⏸ PAUSED (recording is OFF)')

    def _signal_handler(sig, frame):
        stop_flag.set()

    signal.signal(signal.SIGINT, _signal_handler)

    # Track which modifiers are currently pressed for chord detection
    _active_mods: set[str] = set()
    _gate_toggle_armed = False
    _move_marker_armed = False

    def on_key_press(key):
        nonlocal _gate_toggle_armed, _move_marker_armed
        name, is_mod = _key_name(key)
        if not name:
            return
        if is_mod:
            _active_mods.add(name)
            # Ctrl+Opt+Shift → insert move() (checked first, exact match prevents gate toggle)
            if _active_mods == {'ctrl', 'alt', 'shift'} and not _move_marker_armed:
                _move_marker_armed = True
                from .backend import get_cursor_pos
                x, y = get_cursor_pos()
                session.on_move_marker(x, y)
            # Ctrl+Opt (without Shift) → toggle gate
            elif {'ctrl', 'alt'}.issubset(_active_mods) and 'shift' not in _active_mods and not _gate_toggle_armed:
                _gate_toggle_armed = True
                session.toggle_gate()
            session.on_key_press(name, True)
        else:
            session.on_key_press(name, False)

    def on_key_release(key):
        nonlocal _gate_toggle_armed, _move_marker_armed
        name, is_mod = _key_name(key)
        if is_mod:
            _active_mods.discard(name)
            if not {'ctrl', 'alt'}.issubset(_active_mods):
                _gate_toggle_armed = False
            if _active_mods != {'ctrl', 'alt', 'shift'}:
                _move_marker_armed = False
            session.on_key_release(name, True)
        else:
            session.on_key_release(name, False)

    def on_click(x, y, button, pressed):
        btn = 'right' if button == mouse.Button.right else 'left'
        session.on_mouse_click(x, y, btn, pressed)

    def on_move(x, y):
        session.on_mouse_move(x, y)

    def on_scroll(x, y, dx, dy):
        session.on_scroll(x, y, dx, dy)

    kb_listener = keyboard.Listener(on_press=on_key_press, on_release=on_key_release)
    ms_listener = mouse.Listener(on_click=on_click, on_move=on_move, on_scroll=on_scroll)

    kb_listener.start()
    ms_listener.start()

    if use_menubar:
        from .menubar import RUMPS_AVAILABLE, run_with_menubar
        if RUMPS_AVAILABLE:
            run_with_menubar(session, kb_listener, ms_listener)
            return  # menubar app handles stop + write + editor

    # Fallback: main thread polls stop_flag — never blocks on listener.join() (SIGINT safety)
    while not stop_flag.is_set():
        stop_flag.wait(timeout=0.05)

    kb_listener.stop()
    ms_listener.stop()
    session.flush_to_file()
