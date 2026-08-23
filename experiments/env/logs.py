"""This module handles writing experiment output to log files.

Every experiment gets its own `logs/` folder and writes there by itself. The
alternative of remembering to redirect to somewhere in /tmp loses the log of
exactly the run you later want to explain, and puts the interesting ones on a
disk that gets wiped.

    with tee(HERE, "sarsa_v2"):
        ...                      # stdout and stderr also land in logs/sarsa_v2.log

Progress bars go to stderr and rewrite themselves with carriage returns, so the
file keeps them as written; `tr '\\r' '\\n'` turns one back into readable lines.
"""

from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path


def log_dir(experiment: Path) -> Path:
    d = Path(experiment) / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


class _Fan:
    """A stream wrapper that writes to the terminal and to the file at once."""

    def __init__(self, stream, handle) -> None:
        self._stream, self._handle = stream, handle

    def write(self, text: str) -> int:
        self._handle.write(text)
        self._handle.flush()
        return self._stream.write(text)

    def flush(self) -> None:
        self._handle.flush()
        self._stream.flush()

    def __getattr__(self, name):
        # isatty(), fileno() and friends are delegated to the real terminal
        # because tqdm asks for them and renders as thousands of lines otherwise.
        return getattr(self._stream, name)


@contextmanager
def tee(experiment: Path, name: str):
    """Duplicates stdout and stderr into `<experiment>/logs/<name>.log`."""
    path = log_dir(experiment) / f"{name}.log"
    handle = path.open("w", encoding="utf-8")
    out, err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = _Fan(out, handle), _Fan(err, handle)
    try:
        yield path
    finally:
        sys.stdout, sys.stderr = out, err
        handle.close()
