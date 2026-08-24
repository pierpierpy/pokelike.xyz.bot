"""This module handles Docker launches for model benchmark passes."""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from pathlib import Path


def _in_docker(args) -> int:
    """Runs the same `model bench` command inside the container.

    Uses docker compose so that mounts, /dev/shm sizing, and env_file stay in
    one place. The container is built fresh, runs detached, and removes itself
    when the pass ends.
    """
    import shutil
    import subprocess

    # parents[5] is the repo root from this file's depth.
    root = Path(__file__).resolve().parents[5]
    compose = root / "llm-bench" / "docker" / "docker-compose.yml"
    if not compose.exists():
        print(f"no compose file at {compose}", file=sys.stderr)
        return 2
    if not shutil.which("docker"):
        print("docker is not on PATH", file=sys.stderr)
        return 2

    # Forward all flags except those that describe how to launch (--docker).
    passthru: list[str] = []
    for i, a in enumerate(sys.argv[1:]):
        if a in ("--docker",):
            continue
        if a == "--name" or (i and sys.argv[i] == "--name"):
            continue
        passthru.append(a)
    # Drop the leading `model bench` verbs because they are the image's ENTRYPOINT.
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
    # A short random suffix so two passes of the same model can run at once.
    name = args.name or f"pk_{args.harness}_{model}_{uuid.uuid4().hex[:4]}"

    build = _needs_build(tag)
    if not build:
        print(f"  reusing pokelike-llm-bench:{tag}, already built from this commit")
    cmd = ["docker", "compose", "-f", str(compose), "run",
           *(["--build"] if build else []), "--rm", "-d",
           "--name", name, "bench", *passthru]
    # Echo the command with the API key masked.
    shown, mask = [], False
    for a in cmd:
        shown.append("<redacted>" if mask else a)
        mask = a == "--api-key"
    print("  " + " ".join(shown))
    # COMPOSE_IGNORE_ORPHANS is set because other passes are not orphans.
    # UID/GID ensures files written on the mount belong to this user instead of root.
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
    """Removes bench containers that have already exited."""
    # Only EXITED containers of this project; running passes and mounted data
    # are never at risk.
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


def _needs_build(tag: str) -> bool:
    """Returns whether the image has to be built before this pass can run.

    A build is skipped only when an image already carries this exact tag and the
    tag names a commit, because a clean tree at that commit is the only thing that
    produces such a tag, so the image on disk holds that code by construction. A
    dirty tree gets a `-dirty` tag, which names no particular content and is always
    rebuilt, and so is `latest` outside git.

    Rebuilding every time was what made `docker ps` stop naming the image of
    passes already running: two passes launched from one commit ask for the same
    tag, and the second build moves that tag onto a fresh image, leaving the first
    pass on an image that no longer has a name.
    """
    if tag == "latest" or tag.endswith("-dirty"):
        return True
    try:
        r = subprocess.run(["docker", "image", "inspect",
                            f"pokelike-llm-bench:{tag}"],
                           capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return True
    return r.returncode != 0


def _image_tag(root: Path) -> str:
    """Returns the Docker image tag, which is the short commit hash or `latest` outside git."""
    # Stable for the same code; a dirty tree is marked so the image holds
    # something no commit does.
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
    """Removes pokelike-llm-bench image tags that no container is using."""
    # This removes only `pokelike-llm-bench` images not in use by any container.
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
