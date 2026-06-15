from __future__ import annotations

import sys

from pheragent.process import run_command


def test_run_command_streams_and_captures_output(capsys) -> None:
    result = run_command(
        [
            sys.executable,
            "-c",
            "import sys; print('out-line'); print('err-line', file=sys.stderr)",
        ],
        timeout=10,
        stream_output=True,
    )

    captured = capsys.readouterr()
    assert result.ok
    assert "out-line" in captured.out
    assert "err-line" in captured.err
    assert "out-line" in result.stdout
    assert "err-line" in result.stderr
