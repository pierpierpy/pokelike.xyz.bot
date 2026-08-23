"""Stopping a running pass: `pokelike model stop <stamp>`.

Sends SIGTERM so the pass shuts down cleanly: the browser closes, the log flushes,
and the heartbeat file is removed. Nothing is deleted; logs, traces, and the
notebook stay in place, and seeds already played keep their rows.

The process to signal is found from the heartbeat file's `pid=... host=...` line.
When the heartbeat predates that field, the pass is matched by harness version and
model against running containers and local processes. If that match is ambiguous,
this refuses and shows the candidates.
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
    """Registers the flags for `pokelike model stop`."""
    s.add_argument("stamp", help="the pass to stop, as shown in the stamp column of "
                                 "`model watch -o`. A unique prefix is enough")
    s.add_argument("--timeout", type=int, default=30, metavar="SECONDS",
                   help="how long to let it wind down before it is killed outright "
                        "(containers only; a run needs a few seconds to close the "
                        "browser and flush its log)")
    s.set_defaults(func=cmd_stop)


def cmd_stop(args) -> int:
    """Ends one running pass gracefully, leaving everything it wrote in place."""
    folder = _folder_for(args.stamp)
    if folder is None:
        return 2

    p = watch.read(folder)
    if p is None:
        print(f"{folder.name} has nothing readable in it yet.", file=sys.stderr)
        return 2
    if p.state != "running":
        # Already finished; not an error.
        print(f"{folder.name} is not running ({p.state}), nothing to stop.")
        return 0

    print(f"stopping {p.model} @ {p.version}, {p.done}/{p.wanted or '?'} runs played")
    owner = _owner(folder)
    if owner.get("host") and _container(owner["host"]):
        return _stop_container(_container(owner["host"]), args.timeout)
    if owner.get("pid") and _mine(owner["pid"], p.version, p.model):
        return _stop_process(owner["pid"])

    # No usable owner line; match by version and model.
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
    """Resolves a stamp (or unique prefix) to a pass directory."""
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
    """Reads `pid=... host=...` from the pass's heartbeat file."""
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
    """Turns a heartbeat hostname into a running container name, or None."""
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
    """Reads a process's command line from /proc, or returns "" if gone."""
    try:
        return Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode(
            "utf-8", "replace")
    except OSError:
        return ""


def _mine(pid: str, version: str, model: str) -> bool:
    """Checks that a recorded pid is still alive and playing this pass."""
    # A pid can be reused, so only trust it when the process is still playing
    # this exact pass.
    if not pid.isdigit():
        return False
    line = _cmdline(int(pid))
    return "model bench" in line and version in line and model in line


def _container_playing(version: str, model: str) -> str | None:
    """Finds the container running this version and model, if any."""
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
    """Finds local processes playing this version and model (parents only)."""
    found = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        line = _cmdline(int(entry.name))
        if "model bench" not in line or version not in line or model not in line:
            continue
        # Skip workers (belong to their parent) and the uv wrapper.
        if "--worker" in line or "/bin/uv " in line or line.startswith("uv "):
            continue
        found.append(int(entry.name))
    return sorted(found)


# ------------------------------------------------------------------ stopping it


def _stop_container(name: str, timeout: int) -> int:
    """Asks a container to finish, giving it time to close down."""
    # SIGTERM first, SIGKILL after timeout. The CLI turns SIGTERM into a clean
    # exit (browser close, log flush). With --rm the container removes itself.
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
    """Sends SIGTERM to a local process and its workers."""
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
    """Returns the direct child pids of a process."""
    # Fields in /proc/<pid>/stat are read after the last ')' because comm can
    # contain spaces and parentheses.
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
