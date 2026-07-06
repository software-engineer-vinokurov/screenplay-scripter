import subprocess


def test_cliclick_capability():
    """Verify cliclick supports -e easing and all required DSL commands."""
    result = subprocess.run(
        ['cliclick', '-e', '1', '-m', 'test',
         'dd:0,0', 'du:0,0', 'm:0,0',
         'kd:cmd', 't:a', 'ku:cmd', 'kp:return', 'c:0,0', 'rc:0,0'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert result.returncode == 0, f"cliclick capability check failed: {result.stderr}"
