import math
import subprocess
import os

# Module-level config — set via configure() before exec()
_dry_run: bool = False
_easing: int | None = None

KP_KEYS = {
    'arrow-down','arrow-left','arrow-right','arrow-up',
    'brightness-down','brightness-up','delete','end','enter','esc',
    'f1','f2','f3','f4','f5','f6','f7','f8','f9','f10','f11','f12',
    'f13','f14','f15','f16','fwd-delete','home',
    'keys-light-down','keys-light-toggle','keys-light-up',
    'mute','num-0','num-1','num-2','num-3','num-4','num-5','num-6',
    'num-7','num-8','num-9','num-clear','num-divide','num-enter',
    'num-equals','num-minus','num-multiply','num-plus',
    'page-down','page-up','play-next','play-pause','play-previous',
    'return','space','tab','volume-down','volume-up',
}

MODIFIER_KEYS = {'alt','cmd','ctrl','fn','shift'}

_DEFAULT_EASING = 555


def configure(dry_run: bool = False, easing: int | None = None) -> None:
    global _dry_run, _easing
    _dry_run = dry_run
    if easing is not None:
        _easing = easing


def get_config() -> tuple[bool, int]:
    """Read config at call time (not import time)."""
    dry_run = _dry_run or os.environ.get('SCRIPTER_DRY_RUN', '0') == '1'
    easing_env = os.environ.get('SCRIPTER_EASING')
    easing = _easing if _easing is not None else (int(easing_env) if easing_env else _DEFAULT_EASING)
    return dry_run, easing


def run(args: list[str], dry_run: bool = False) -> list[str] | None:
    """Run cliclick with args. dry_run=True returns args as-is; dry_run=False prepends 'cliclick'."""
    if dry_run:
        return args
    subprocess.run(['cliclick'] + args, check=False)
    return None


def compute_easing(distance: float) -> int:
    """Constant-speed easing: factor × 1000 / distance, calibrated so factor == easing at 1000 px.
    Inverse proportionality means half the distance → 2× easing → same apparent cursor speed."""
    _, factor = get_config()
    return max(1, round(factor * 1000 / max(1.0, distance)))


def get_cursor_pos() -> tuple[int, int]:
    """Get current cursor position via cliclick p. Parses stdout, ignores stderr."""
    result = subprocess.run(
        ['cliclick', 'p'],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    raw = result.stdout.strip()
    try:
        x, y = raw.split(',')
        return int(x.strip()), int(y.strip())
    except (ValueError, AttributeError):
        return (0, 0)


def check_capability() -> bool:
    """Verify cliclick supports -e easing and all required commands."""
    result = subprocess.run(
        ['cliclick', '-e', '1', '-m', 'test',
         'dd:0,0', 'du:0,0', 'm:0,0',
         'kd:cmd', 't:a', 'ku:cmd', 'kp:return', 'c:0,0', 'rc:0,0'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.returncode == 0
