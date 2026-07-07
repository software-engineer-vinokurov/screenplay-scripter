import math
import time
import subprocess
from .backend import get_config, get_cursor_pos, compute_easing, KP_KEYS, MODIFIER_KEYS


def click(x: float, y: float) -> None:
    dry_run, _ = get_config()
    rx, ry = round(x), round(y)
    cx, cy = (0, 0) if dry_run else get_cursor_pos()
    easing = compute_easing(math.hypot(rx - cx, ry - cy))
    argv = ['-e', str(easing), f'c:{rx},{ry}']
    if dry_run:
        print(f"[DRY-RUN] cliclick {' '.join(argv)}")
    else:
        subprocess.run(['cliclick'] + argv, check=False)


def double_click(x: float, y: float) -> None:
    dry_run, _ = get_config()
    rx, ry = round(x), round(y)
    cx, cy = (0, 0) if dry_run else get_cursor_pos()
    easing = compute_easing(math.hypot(rx - cx, ry - cy))
    argv = ['-e', str(easing), f'dc:{rx},{ry}']
    if dry_run:
        print(f"[DRY-RUN] cliclick {' '.join(argv)}")
    else:
        subprocess.run(['cliclick'] + argv, check=False)


def right_click(x: float, y: float) -> None:
    dry_run, _ = get_config()
    rx, ry = round(x), round(y)
    cx, cy = (0, 0) if dry_run else get_cursor_pos()
    easing = compute_easing(math.hypot(rx - cx, ry - cy))
    argv = ['-e', str(easing), f'rc:{rx},{ry}']
    if dry_run:
        print(f"[DRY-RUN] cliclick {' '.join(argv)}")
    else:
        subprocess.run(['cliclick'] + argv, check=False)


def drag(start: tuple[float, float], end: tuple[float, float]) -> None:
    dry_run, _ = get_config()
    x0, y0 = round(start[0]), round(start[1])
    x1, y1 = round(end[0]), round(end[1])
    cx, cy = (0, 0) if dry_run else get_cursor_pos()
    # Easing covers the full path: approach to drag start + drag itself
    easing = compute_easing(math.hypot(x0 - cx, y0 - cy) + math.hypot(x1 - x0, y1 - y0))
    argv = ['-e', str(easing), f'dd:{x0},{y0}', f'du:{x1},{y1}']
    if dry_run:
        print(f"[DRY-RUN] cliclick {' '.join(argv)}")
    else:
        subprocess.run(['cliclick'] + argv, check=False)


def scroll(x: float, y: float, amount: int) -> None:
    """Scroll at (x,y) by amount lines. Positions cursor via cliclick, posts wheel event via Quartz."""
    dry_run, _ = get_config()
    x, y, amount = round(x), round(y), int(amount)
    cx, cy = (0, 0) if dry_run else get_cursor_pos()
    easing = compute_easing(math.hypot(x - cx, y - cy))
    if dry_run:
        print(f"[DRY-RUN] cliclick -e {easing} m:{x},{y}")
        print(f"[scroll {x},{y} amount={amount} lines]")
    else:
        subprocess.run(['cliclick', '-e', str(easing), f'm:{x},{y}'], check=False)
        try:
            from Quartz.CoreGraphics import (
                CGEventCreateScrollWheelEvent,
                CGEventPost,
                kCGHIDEventTap,
                kCGScrollEventUnitLine,
            )
            event = CGEventCreateScrollWheelEvent(None, kCGScrollEventUnitLine, 1, amount)
            CGEventPost(kCGHIDEventTap, event)
        except ImportError:
            print("[WARNING] pyobjc-framework-Quartz not available; scroll skipped", flush=True)


def key(*keys: str) -> None:
    dry_run, _ = get_config()
    modifiers = [k for k in keys if k in MODIFIER_KEYS]
    terminal_keys = [k for k in keys if k not in MODIFIER_KEYS]

    # solo esc without modifiers: pynput uses kCGSessionEventTap which routes to the
    # focused app more reliably than cliclick's kCGHIDEventTap.
    if not modifiers and terminal_keys == ['esc']:
        if dry_run:
            print('[DRY-RUN] cliclick kp:esc')
        else:
            try:
                from pynput.keyboard import Controller as _KC, Key as _K
                _c = _KC()
                _c.press(_K.esc)
                _c.release(_K.esc)
            except Exception:
                subprocess.run(['cliclick', 'kp:esc'], check=False)
        return

    argv = []
    if modifiers:
        argv.append(f'kd:{",".join(modifiers)}')
    for tk in terminal_keys:
        if tk == 'space' and not modifiers:
            # t: inserts via the text-input pathway; kp:space bypasses it in some apps.
            argv.append('t: ')
        elif tk in KP_KEYS:
            argv.append(f'kp:{tk}')
        else:
            argv.append(f't:{tk}')
    if modifiers:
        argv.append(f'ku:{",".join(modifiers)}')

    if dry_run:
        print(f"[DRY-RUN] cliclick {' '.join(argv)}")
    else:
        subprocess.run(['cliclick'] + argv, check=False)


def type_text(text: str) -> None:
    dry_run, _ = get_config()
    if dry_run:
        print(f"[DRY-RUN] cliclick t:{text}")
    else:
        subprocess.run(['cliclick', f't:{text}'], check=False)


def sleep(seconds: float) -> None:
    time.sleep(seconds)


def move(x: float, y: float) -> None:
    dry_run, _ = get_config()
    rx, ry = round(x), round(y)
    cx, cy = (0, 0) if dry_run else get_cursor_pos()
    easing = compute_easing(math.hypot(rx - cx, ry - cy))
    argv = ['-e', str(easing), f'm:{rx},{ry}']
    if dry_run:
        print(f"[DRY-RUN] cliclick {' '.join(argv)}")
    else:
        subprocess.run(['cliclick'] + argv, check=False)
