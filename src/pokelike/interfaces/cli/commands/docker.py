"""Docker launch for model benchmark passes.

In: the parsed args (with --docker set). Out: the container's exit code.
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path


def _in_docker(args) -> int:
    """Runs this same `model bench` inside the container, and returns.

    Exactly the documented compose command, built here so the flags cannot be got
    wrong: `--build` so the image is never stale, `--rm` so the container removes
    itself when the pass ends, `-d` because a fifty-seed pass outlives the shell.
    Compose, not `docker run`, on purpose: the mounts, the 2 GB /dev/shm and the
    env_file live in the compose file, and duplicating them here would be a second
    copy to keep in step. Behaviour is therefore identical to running it by hand.

    In: the parsed args. Out: the process exit code.
    """
    import shutil
    import subprocess

    # parents[5] from the OLD location (commands/model.py) was the repo root.
    # This file is at the same depth (commands/docker.py), so parents[5] is still correct.
    root = Path(__file__).resolve().parents[5]
    compose = root / "llm-bench" / "docker" / "docker-compose.yml"
    if not compose.exists():
        print(f"no compose file at {compose}", file=sys.stderr)
        return 2
    if not shutil.which("docker"):
        print("docker is not on PATH", file=sys.stderr)
        return 2

    # The pass's own flags, forwarded untouched, minus the ones that describe HOW to
    # launch rather than WHAT to play. `--docker` itself would otherwise recurse.
    passthru: list[str] = []
    for i, a in enumerate(sys.argv[1:]):
        if a in ("--docker",):
            continue
        if a == "--name" or (i and sys.argv[i] == "--name"):
            continue
        passthru.append(a)
    # Drop the leading `model bench` verbs: they are the image's ENTRYPOINT.
    while passthru and passthru[0] in ("model", "bench"):
        passthru.pop(0)

    tag = _image_tag(root)
    reaped = reap_exited()
    if reaped:
        print(f"  removed {len(reaped)} container(s) that had already exited: "
              f"{', '.join(reaped)}")
    # After the containers, because an image cannot go while one refers to it.
    dropped = reap_images(tag)
    if dropped:
        print(f"  removed {len(dropped)} unused image(s): {', '.join(dropped)}")

    model = (args.model or args.models or "many").replace("/", "-").replace(":", "-")
    # A short random suffix, for the same reason the pass directory carries one: two
    # passes of the same model on the same harness are a normal thing to want (a
    # --repeat, a second seed range), and without it the second launch dies on a
    # name Docker already holds.
    name = args.name or f"pk_{args.harness}_{model}_{uuid.uuid4().hex[:4]}"

    cmd = ["docker", "compose", "-f", str(compose), "run", "--build", "--rm", "-d",
           "--name", name, "bench", *passthru]
    # Echoed with the key masked. A token on a command line is already visible in
    # `ps` and saved in shell history; printing it as well would put it in whatever
    # log is capturing this. `--api-key @path`, or .env, keeps it out of all three.
    shown, mask = [], False
    for a in cmd:
        shown.append("<redacted>" if mask else a)
        mask = a == "--api-key"
    print("  " + " ".join(shown))
    # COMPOSE_IGNORE_ORPHANS: every pass is its own container in one shared compose
    # project, so the passes already running are not orphans and the warning about
    # them is noise on every launch.
    # UID/GID: the compose file runs the container as this user so that what a pass
    # writes on the mounted volume belongs to the person who launched it, not to
    # root. They are shell variables rather than environment ones, so they have to
    # be put in the environment here or compose would fall back to its default.
    env = {**os.environ, "COMPOSE_IGNORE_ORPHANS": "true",
           "UID": str(os.getuid()), "GID": str(os.getgid()),
           "PK_TAG": tag}
    r = subprocess.run(cmd, cwd=root, env=env)
    if r.returncode == 0:
        print(f"\n  {name} is playing. Follow it with:\n"
              f"    pokelike model watch\n"
              f"    docker logs -f {name}\n"
              f"  It removes itself when the pass ends; `docker stop {name}` ends it early.")
    return r.returncode


def reap_exited() -> list[str]:
    """Removes bench containers that have already finished.

    In: nothing. Out: the names removed, in the order Docker listed them.
    """
    # A pass launched with `--docker` carries `--rm` and takes itself away, but one
    # launched by hand without it stays in `docker ps -a` forever, and a list of
    # dead containers is noise that hides the live ones. Only EXITED containers of
    # this project are touched: a running pass is never at risk, and nothing a pass
    # wrote lives in the container anyway (the logs are on the mounted volume).
    ids: list[str] = []
    for flt in (["--filter", "label=com.docker.compose.project=pokelike-llm-bench"],
                ["--filter", "name=^pk_"]):
        try:
            out = subprocess.run(
                ["docker", "ps", "-a", "--filter", "status=exited", *flt,
                 "--format", "{{.Names}}"],
                capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            return []
        ids += [n for n in out.stdout.split() if n and n not in ids]
    if not ids:
        return []
    try:
        subprocess.run(["docker", "rm", *ids], capture_output=True, text=True,
                       timeout=30)
    except (OSError, subprocess.SubprocessError):
        return []
    return ids


def _image_tag(root: Path) -> str:
    """The tag to build under: the commit the image is built from.

    In: the repository root. Out: a short tag such as `b05f452` or `b05f452-dirty`,
    falling back to `latest` outside a git checkout.
    """
    # Readable, and stable for the same code, which is the point: an unchanged
    # checkout rebuilds to the same tag and no running container is orphaned. A dirty
    # tree is marked as such because the image then holds something no commit does.
    # This is for the eye only: what makes a recorded result trustworthy is the
    # seven-key fingerprint, not the tag on an image.
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=root,
                             capture_output=True, text=True, timeout=10)
        if sha.returncode != 0 or not sha.stdout.strip():
            return "latest"
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=root,
                               capture_output=True, text=True, timeout=15)
        return sha.stdout.strip() + ("-dirty" if dirty.stdout.strip() else "")
    except (OSError, subprocess.SubprocessError):
        return "latest"


def reap_images(keep: str) -> list[str]:
    """Removes our own image tags that no container is using.

    In: the tag being kept (the one about to run). Out: the tags removed.
    """
    # Only images named `pokelike-llm-bench`, so nothing else on the machine is at
    # risk, and only those no container refers to: an image in use cannot be removed
    # anyway, and a pass playing from an older commit must keep the name it shows in
    # `docker ps`. Left alone otherwise these accumulate a few GB per build.
    try:
        imgs = subprocess.run(
            ["docker", "images", "pokelike-llm-bench", "--format", "{{.Tag}} {{.ID}}"],
            capture_output=True, text=True, timeout=10)
        used = subprocess.run(["docker", "ps", "-a", "--format", "{{.Image}}"],
                              capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return []
    busy = set(used.stdout.split())
    gone = []
    for line in imgs.stdout.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        tag, ident = parts
        ref = f"pokelike-llm-bench:{tag}"
        if tag in ("<none>", keep) or ref in busy or ident in busy:
            continue
        r = subprocess.run(["docker", "rmi", ref], capture_output=True, text=True,
                           timeout=60)
        if r.returncode == 0:
            gone.append(ref)
    return gone
