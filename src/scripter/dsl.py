import time
import subprocess
from .backend import get_config, KP_KEYS, MODIFIER_KEYS


def click(x: float, y: float) -> None:
    dry_run, easing = get_config()
    argv = [f'-e', str(easing), f'c:{round(x)},{round(y)}']
    if dry_run:
        print(f"[DRY-RUN] cliclick {' '.join(argv)}")
    else:
        subprocess.run(['cliclick'] + argv, check=False)


def right_click(x: float, y: float) -> None:
    dry_run, easing = get_config()
    argv = ['-e', str(easing), f'rc:{round(x)},{round(y)}']
    if dry_run:
        print(f"[DRY-RUN] cliclick {' '.join(argv)}")
    else:
        subprocess.run(['cliclick'] + argv, check=False)


def drag(start: tuple[float, float], end: tuple[float, float]) -> None:
    dry_run, easing = get_config()
    x0, y0 = round(start[0]), round(start[1])
    x1, y1 = round(end[0]), round(end[1])
    argv = ['-e', str(easing), f'dd:{x0},{y0}', f'du:{x1},{y1}']
    if dry_run:
        print(f"[DRY-RUN] cliclick {' '.join(argv)}")
    else:
        subprocess.run(['cliclick'] + argv, check=False)


def scroll(x: float, y: float, amount: int) -> None:
    """Scroll at (x,y) by amount lines. Positions cursor via cliclick, posts wheel event via Quartz."""
    dry_run, easing = get_config()
    x, y, amount = round(x), round(y), int(amount)
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

    argv = []
    if modifiers:
        argv.append(f'kd:{",".join(modifiers)}')
    for tk in terminal_keys:
        argv.append(f'kp:{tk}' if tk in KP_KEYS else f't:{tk}')
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
    dry_run, easing = get_config()
    argv = ['-e', str(easing), f'm:{round(x)},{round(y)}']
    if dry_run:
        print(f"[DRY-RUN] cliclick {' '.join(argv)}")
    else:
        subprocess.run(['cliclick'] + argv, check=False)
