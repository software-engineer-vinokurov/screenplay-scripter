import ast
import sys
from pathlib import Path


_DSL_NAMES = frozenset([
    'click', 'right_click', 'drag', 'scroll', 'key', 'type_text', 'sleep', 'move',
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


def play_script(script_path: Path) -> None:
    """Execute a scripter DSL script with the current backend configuration."""
    source = script_path.read_text()

    # Warn-only AST scan
    _warn_non_dsl(source, script_path)

    # Compile for file:line tracebacks (not raw runpy)
    try:
        code = compile(source, filename=str(script_path), mode='exec')
    except SyntaxError as e:
        print(f"Syntax error in {script_path}:{e.lineno}: {e.msg}", file=sys.stderr)
        sys.exit(1)

    # Build namespace with DSL names pre-bound
    from scripter import click, right_click, drag, scroll, key, type_text, sleep, move
    namespace = {
        'click': click, 'right_click': right_click, 'drag': drag,
        'scroll': scroll, 'key': key, 'type_text': type_text,
        'sleep': sleep, 'move': move,
        '__name__': '__main__', '__file__': str(script_path),
    }

    exec(code, namespace)
