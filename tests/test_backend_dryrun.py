import os
from unittest.mock import patch
import scripter.backend as backend


def setup_function():
    backend.configure(dry_run=False, easing=None)


def test_dry_run_returns_argv():
    result = backend.run(['cliclick', 'p'], dry_run=True)
    assert result == ['cliclick', 'p']


def test_dry_run_false_returns_none():
    with patch('scripter.backend.subprocess.run') as mock_run:
        mock_run.return_value = None
        result = backend.run(['p'], dry_run=False)
        assert result is None
        mock_run.assert_called_once()


def test_config_precedence_cli_wins_over_env():
    os.environ['SCRIPTER_DRY_RUN'] = '0'
    backend.configure(dry_run=True)
    dry, _ = backend.get_config()
    assert dry is True
    del os.environ['SCRIPTER_DRY_RUN']


def test_config_precedence_env_when_not_configured():
    backend.configure(dry_run=False, easing=None)
    os.environ['SCRIPTER_DRY_RUN'] = '1'
    dry, _ = backend.get_config()
    assert dry is True
    del os.environ['SCRIPTER_DRY_RUN']


def test_config_precedence_default_false():
    backend.configure(dry_run=False, easing=None)
    dry, _ = backend.get_config()
    assert dry is False


def test_easing_default():
    backend.configure(dry_run=False, easing=None)
    _, easing = backend.get_config()
    assert easing == 555


def test_easing_override():
    backend.configure(dry_run=False, easing=10)
    _, easing = backend.get_config()
    assert easing == 10
    backend.configure(dry_run=False, easing=None)


def test_scroll_dry_run(capsys):
    backend.configure(dry_run=True)
    from scripter.dsl import scroll
    scroll(760, 540, 3)
    captured = capsys.readouterr()
    assert 'm:760,540' in captured.out
    assert '[scroll 760,540 amount=3 lines]' in captured.out
    backend.configure(dry_run=False)


def test_click_dry_run(capsys):
    backend.configure(dry_run=True)
    from scripter.dsl import click
    click(300, 400)
    captured = capsys.readouterr()
    assert 'c:300,400' in captured.out
    assert '-e' in captured.out


def test_drag_dry_run(capsys):
    backend.configure(dry_run=True)
    from scripter.dsl import drag
    drag((300, 400), (500, 460))
    captured = capsys.readouterr()
    assert 'dd:300,400' in captured.out
    assert 'du:500,460' in captured.out
    assert '-e' in captured.out


def test_key_cmd_c_dry_run(capsys):
    backend.configure(dry_run=True)
    from scripter.dsl import key
    key('cmd', 'c')
    captured = capsys.readouterr()
    assert 'kd:cmd' in captured.out
    assert 't:c' in captured.out
    assert 'ku:cmd' in captured.out
    backend.configure(dry_run=False)


def test_key_cmd_space_dry_run(capsys):
    backend.configure(dry_run=True)
    from scripter.dsl import key
    key('cmd', 'space')
    captured = capsys.readouterr()
    assert 'kd:cmd' in captured.out
    assert 'kp:space' in captured.out
    assert 'ku:cmd' in captured.out
    backend.configure(dry_run=False)


def test_key_return_dry_run(capsys):
    backend.configure(dry_run=True)
    from scripter.dsl import key
    key('return')
    captured = capsys.readouterr()
    assert 'kp:return' in captured.out
    backend.configure(dry_run=False)
