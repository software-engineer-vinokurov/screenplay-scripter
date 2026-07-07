import ast
import sys
import time
from pathlib import Path


_DSL_NAMES = frozenset([
    'click', 'double_click', 'right_click', 'drag', 'scroll', 'key', 'type_text', 'sleep', 'move',
])


def _warn_non_dsl(source: str, script_path: Path) -> None:
    """Warn-only AST scan: flag non-DSL imports or calls."""
    try:
        tree = ast.parse(source, filename=str(script_path))
    except SyntaxError:
        return  # Syntax errors reported separately via compile()

    warnings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name != 'scripter':
                    warnings.append(f"  Line {node.lineno}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module not in (None, 'scripter'):
                warnings.append(f"  Line {node.lineno}: from {node.module} import ...")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id not in _DSL_NAMES:
                if node.func.id not in ('print', 'len', 'range', 'int', 'float', 'str'):
                    warnings.append(f"  Line {node.lineno}: non-DSL call: {node.func.id}()")

    if warnings:
        print(f"[WARNING] Non-DSL content in {script_path}:", file=sys.stderr)
        for w in warnings:
            print(w, file=sys.stderr)


def _make_dsl_namespace(script_path: str) -> dict:
    from scripter import click, double_click, right_click, drag, scroll, key, type_text, sleep, move
    return {
        'click': click, 'double_click': double_click, 'right_click': right_click, 'drag': drag,
        'scroll': scroll, 'key': key, 'type_text': type_text,
        'sleep': sleep, 'move': move,
        '__name__': '__main__', '__file__': script_path,
    }


def play_script(script_path: Path) -> None:
    """Execute a scripter DSL script with the current backend configuration."""
    source = script_path.read_text()
    _warn_non_dsl(source, script_path)
    try:
        code = compile(source, filename=str(script_path), mode='exec')
    except SyntaxError as e:
        print(f"Syntax error in {script_path}:{e.lineno}: {e.msg}", file=sys.stderr)
        sys.exit(1)
    exec(code, _make_dsl_namespace(str(script_path)))


def _get_sleep_duration(stmt) -> float | None:
    """Return the sleep duration if stmt is a bare sleep() call, else None."""
    if (isinstance(stmt, ast.Expr)
            and isinstance(stmt.value, ast.Call)
            and isinstance(stmt.value.func, ast.Name)
            and stmt.value.func.id == 'sleep'
            and stmt.value.args
            and isinstance(stmt.value.args[0], ast.Constant)):
        return float(stmt.value.args[0].value)
    return None


def play_script_stepped(
    script_path: Path,
    on_progress=None,
    on_sleep=None,
    pause_event=None,
    stop_event=None,
) -> None:
    """Execute a script statement-by-statement for review mode."""
    source = script_path.read_text()
    _warn_non_dsl(source, script_path)
    try:
        tree = ast.parse(source, filename=str(script_path))
    except SyntaxError as e:
        print(f"Syntax error in {script_path}:{e.lineno}: {e.msg}", file=sys.stderr)
        sys.exit(1)

    namespace = _make_dsl_namespace(str(script_path))
    stmts = tree.body
    total_lines = source.count('\n') + 1

    for i, stmt in enumerate(stmts):
        if stop_event and stop_event.is_set():
            break
        while pause_event and pause_event.is_set():
            if stop_event and stop_event.is_set():
                return
            time.sleep(0.05)
        if on_progress:
            on_progress(i + 1, len(stmts), stmt.lineno, total_lines)
        if on_sleep:
            dur = _get_sleep_duration(stmt)
            if dur is not None:
                on_sleep(stmt.lineno, dur)
        code = compile(ast.Module(body=[stmt], type_ignores=[]), str(script_path), 'exec')
        exec(code, namespace)
