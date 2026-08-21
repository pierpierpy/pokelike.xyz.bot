"""Stopping a running pass on purpose: `pokelike model stop <stamp>`.

Ends the pass the way `docker stop` and Ctrl-C already end one, by asking it to
finish rather than killing it: SIGTERM travels through the same shutdown the CLI
installs, so the browser closes, the log is flushed and the heartbeat file is
removed. NOTHING is deleted. The logs, the trace and the notebook stay exactly
where they are, and the seeds already played keep their rows, which is the whole
reason to stop politely instead of `kill -9`.

Finding WHICH process to signal is the interesting part, and there are two ways:

  1. The pass says so. Its heartbeat file carries `pid=... host=...`, so the pass
     names itself and there is nothing to guess.
  2. It does not, because it started before that existed (or under an older
     image). Then the pass is matched by what it is playing, the harness version
     and the model id, against the running containers and the processes on this
     machine. If that is ambiguous, two passes of the same model on the same
     version, this refuses and shows the candidates rather than stopping the
     wrong one.
"""

from __future__ import annotations

import os
import re
import signal
import subprocess
import sys
from pathlib import Path

from ....harness import watch


def model_stop_args(s) -> None:
    """Registers the flags of `model stop`.

    In: the subparser. Out: nothing, the parser is mutated.
    """
    s.add_argument("stamp", help="the pass to stop, as shown in the stamp column of "
                                 "`model watch -o`. A unique prefix is enough")
    s.add_argument("--timeout", type=int, default=30, metavar="SECONDS",
                   help="how long to let it wind down before it is killed outright "
                        "(containers only; a run needs a few seconds to close the "
                        "browser and flush its log)")
    s.set_defaults(func=cmd_stop)


def cmd_stop(args) -> int:
    """Ends one running pass gracefully, leaving everything it wrote in place.

    In: the parsed args (a stamp, or a unique prefix of one). Out: the exit code.
    """
    folder = _folder_for(args.stamp)
    if folder is None:
        return 2

    p = watch.read(folder)
    if p is None:
        print(f"{folder.name} has nothing readable in it yet.", file=sys.stderr)
        return 2
    if p.state != "running":
        # Not an error worth a non-zero code: asking a finished pass to stop got
        # you what you wanted, and this is the answer to "why did nothing happen".
        print(f"{folder.name} is not running ({p.state}), nothing to stop.")
        return 0

    print(f"stopping {p.model} @ {p.version}, {p.done}/{p.wanted or '?'} runs played")
    owner = _owner(folder)
    if owner.get("host") and _container(owner["host"]):
        return _stop_container(_container(owner["host"]), args.timeout)
    if owner.get("pid") and _mine(owner["pid"], p.version, p.model):
        return _stop_process(owner["pid"])

    # No usable owner line: this pass predates it. Match it by what it plays.
    name = _container_playing(p.version, p.model)
    if name is not None:
        return _stop_container(name, args.timeout)
    pids = _processes_playing(p.version, p.model)
    if len(pids) == 1:
        return _stop_process(pids[0])
    if len(pids) > 1:
        print(f"  several processes are playing {p.model} @ {p.version}: "
              f"{', '.join(str(x) for x in pids)}.\n"
              f"  This pass is too old to name its own process, so which one is "
              f"yours cannot be told from here.\n"
              f"  Stop it by hand: kill {pids[0]}", file=sys.stderr)
        return 2
    print(f"  its heartbeat is fresh, but no container or process on this machine "
          f"is playing {p.model} @ {p.version}.\n"
          f"  It is probably running on another machine: stop it there.",
          file=sys.stderr)
    return 2


# ------------------------------------------------------------------ finding it


def _folder_for(stamp: str) -> Path | None:
    """Resolves a stamp, or a unique prefix of one, to a pass directory.

    In: what the user typed. Out: the directory, or None after explaining why not.
    """
    hits = [d for d in watch.folders(None) if stamp in d.name]
    if not hits:
        print(f"no pass here matches {stamp}.\n"
              f"  what is on this machine:  pokelike model watch --all",
              file=sys.stderr)
        return None
    if len(hits) > 1:
        print(f"{stamp} matches {len(hits)} passes: "
              f"{', '.join(d.name for d in hits)}.\n"
              f"  Give more of the stamp.", file=sys.stderr)
        return None
    return hits[0]


def _owner(folder: Path) -> dict[str, str]:
    """Reads `pid=... host=...` out of the pass's heartbeat file.

    In: the pass directory. Out: dict with pid and host when present, else empty.
    """
    for alive in sorted(folder.glob("*.alive")):
        try:
            text = alive.read_text(encoding="utf-8")
        except OSError:
            continue
        got = dict(re.findall(r"(pid|host)=(\S+)", text))
        if got:
            return got
    return {}


def _container(host: str) -> str | None:
    """Turns a hostname written by a pass into a running container name.

    In: the hostname from the heartbeat (Docker sets it to the container id).
    Out: the container's name, or None when no such container is up.
    """
    for name in watch._containers():
        if name == host:
            return name
        try:
            out = subprocess.run(["docker", "inspect", "--format", "{{.Id}}", name],
                                 capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.SubprocessError):
            return None
        if out.stdout.strip().startswith(host):
            return name
    return None


def _cmdline(pid: int) -> str:
    """Reads a process's command line.

    In: a pid. Out: the command line with NULs as spaces, or "" if it is gone.
    """
    try:
        return Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode(
            "utf-8", "replace")
    except OSError:
        return ""


def _mine(pid: str, version: str, model: str) -> bool:
    """Checks a recorded pid is still the pass that wrote it.

    In: the pid string from the heartbeat, the pass's version and model. Out: True
    when that process is alive and playing this pass.
    """
    # A pid is reused once the machine has been up long enough, so it is only
    # trusted when the process behind it is still playing this exact pass. Without
    # this, a stale heartbeat could point at somebody's editor.
    if not pid.isdigit():
        return False
    line = _cmdline(int(pid))
    return "model bench" in line and version in line and model in line


def _container_playing(version: str, model: str) -> str | None:
    """Finds the container running this version and model, when there is one.

    In: harness version and model id. Out: the container name, or None.
    """
    for name in watch._containers():
        try:
            out = subprocess.run(
                ["docker", "inspect", "--format", "{{join .Args \" \"}}", name],
                capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.SubprocessError):
            return None
        args = out.stdout
        if version in args and model in args:
            return name
    return None


def _processes_playing(version: str, model: str) -> list[int]:
    """Finds processes on THIS machine playing this version and model.

    In: harness version and model id. Out: the pids, parents only (a fan-out's
    workers are stopped with their parent).
    """
    found = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        line = _cmdline(int(entry.name))
        if "model bench" not in line or version not in line or model not in line:
            continue
        # The `uv run` wrapper and the python process it spawns both match. Signal
        # the one actually playing, and skip a worker: it belongs to its parent.
        if "--worker" in line or "/bin/uv " in line or line.startswith("uv "):
            continue
        found.append(int(entry.name))
    return sorted(found)


# ------------------------------------------------------------------ stopping it


def _stop_container(name: str, timeout: int) -> int:
    """Asks a container to finish, giving it time to close down.

    In: the container name and how many seconds to allow. Out: the exit code.
    """
    # `docker stop` is SIGTERM first and SIGKILL only after the timeout, and the
    # CLI turns SIGTERM into a normal exit, so the browser closes and the log is
    # flushed on the way out. With `--rm` the container then removes itself.
    print(f"  docker stop -t {timeout} {name}")
    try:
        r = subprocess.run(["docker", "stop", "-t", str(timeout), name],
                           capture_output=True, text=True, timeout=timeout + 30)
    except (OSError, subprocess.SubprocessError) as e:
        print(f"  could not stop the container: {e}", file=sys.stderr)
        return 1
    if r.returncode != 0:
        print(f"  docker refused: {r.stderr.strip()}", file=sys.stderr)
        return 1
    print("  stopped. Its logs, trace and notebook are untouched.")
    return 0


def _stop_process(pid: int | str) -> int:
    """Asks a process on this machine to finish, and its workers with it.

    In: the pid. Out: the exit code.
    """
    pid = int(pid)
    kids = [k for k in _children(pid) if "--worker" in _cmdline(k)]
    print(f"  SIGTERM to {pid}" + (f" and its workers {kids}" if kids else ""))
    for target in [pid, *kids]:
        try:
            os.kill(target, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except PermissionError:
            print(f"  not allowed to signal {target}: it belongs to another user.",
                  file=sys.stderr)
            return 1
    print("  asked to finish. Its logs, trace and notebook are untouched.")
    return 0


def _children(parent: int) -> list[int]:
    """Finds the direct children of a process.

    In: the parent pid. Out: the pids whose parent it is.
    """
    # /proc/<pid>/stat is "pid (comm) state ppid ...", and comm can itself contain
    # spaces and parentheses, so the fields are read after the LAST ')' rather than
    # by splitting the whole line.
    out = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            stat = (entry / "stat").read_text(encoding="utf-8")
        except OSError:
            continue
        tail = stat.rpartition(")")[2].split()
        if len(tail) >= 2 and tail[1] == str(parent):
            out.append(int(entry.name))
    return sorted(out)
