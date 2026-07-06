import os
from pathlib import Path
from typing import Optional
import typer

app = typer.Typer(
    name='scripter',
    help='Record and replay macOS mouse/keyboard interactions as Python scripts.',
    no_args_is_help=True,
)


@app.command()
def record(
    output: Path = typer.Argument(..., help='Path to write the generated Python script'),
    no_timing: bool = typer.Option(False, '--no-timing', help='Suppress automatic sleep() capture between events'),
    no_menubar: bool = typer.Option(False, '--no-menubar', help='Disable menu bar indicator (use Ctrl+C instead)'),
):
    """Record mouse/keyboard interactions into a Python script file."""
    from .backend import check_capability
    if not check_capability():
        typer.echo('WARNING: Some cliclick commands may not be available.', err=True)

    from .recorder import run_recording
    run_recording(str(output), no_timing=no_timing, use_menubar=not no_menubar)


@app.command()
def play(
    script: Path = typer.Argument(..., help='Python script file to play'),
    dry_run: bool = typer.Option(False, '--dry-run', help='Print cliclick argv without executing'),
    easing: Optional[int] = typer.Option(None, '--easing', help='cliclick easing factor at 1000 px (default: 555)'),
    review: bool = typer.Option(False, '--review', help='Show menu bar progress indicator; Ctrl+Opt to pause/resume'),
):
    """Play back a recorded script with smooth mouse movement via cliclick easing."""
    if not script.exists():
        typer.echo(f'Error: script not found: {script}', err=True)
        raise typer.Exit(1)

    effective_dry_run = dry_run or os.environ.get('SCRIPTER_DRY_RUN', '0') == '1'

    from .backend import configure
    configure(dry_run=effective_dry_run, easing=easing)

    if review:
        from .menubar import RUMPS_AVAILABLE, run_with_review_menubar
        if not RUMPS_AVAILABLE:
            typer.echo('Error: rumps not installed; --review requires rumps', err=True)
            raise typer.Exit(1)
        from .player import play_script_stepped
        run_with_review_menubar(script, lambda **kw: play_script_stepped(script, **kw))
    else:
        from .player import play_script
        play_script(script)
