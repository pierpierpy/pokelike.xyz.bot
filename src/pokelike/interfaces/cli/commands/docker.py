"""This module handles Docker launches for model benchmark passes."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import uuid
from pathlib import Path


PROXY_URL = "http://litellm:4000"


def proxied_models(compose: Path) -> set[str]:
    """Returns the model names the translating proxy serves, read from its own config.

    The proxy's config is the registry, so adding a model there is what routes it
    and removing it is what sends it back to talking to its provider directly. A
    second list here would be one more thing to keep in step.

    The parse looks for `model_name:` lines rather than loading YAML, because
    pyyaml is not a dependency of this package and the file is one of ours.
    """
    path = compose.parent / "litellm.yaml"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return set()
    return {m.group(1).strip().strip('"\'')
            for m in re.finditer(r'^\s*-?\s*model_name:\s*(.+)$', text, re.M)}


def start_proxy(compose: Path, env: dict) -> bool:
    """Brings the translating proxy up, and returns whether it is now running.

    The call is idempotent, so a pass does not have to know whether an earlier one
    already started it.
    """
    try:
        r = subprocess.run(
            ["docker", "compose", "-f", str(compose), "--profile", "proxy",
             "up", "-d", "litellm"],
            capture_output=True, text=True, timeout=300, env=env)
    except (OSError, subprocess.SubprocessError):
        return False
    if r.returncode != 0:
        print(f"  the proxy would not start:\n{r.stderr.strip()[:400]}",
              file=sys.stderr)
        return False
    return True


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

    # COMPOSE_IGNORE_ORPHANS is set because other passes are not orphans.
    # UID/GID ensures files written on the mount belong to this user instead of root.
    env = {**os.environ, "COMPOSE_IGNORE_ORPHANS": "true",
           "UID": str(os.getuid()), "GID": str(os.getgid()),
           "PK_TAG": tag}

    # A model whose provider does not speak OpenAI goes through the translating
    # proxy, and every other model goes straight to its provider as before. The
    # endpoint and the key travel as container environment rather than as flags,
    # so the key never appears in `ps`, and they override what .env carries for
    # this container only.
    routed = (args.model or "") in proxied_models(compose)
    forward: list[str] = []
    if routed:
        if not start_proxy(compose, env):
            print("  the pass was not started, because the proxy it needs is not "
                  "running.\n  Bring it up by hand to see why:\n"
                  f"    docker compose -f {compose} --profile proxy up litellm",
                  file=sys.stderr)
            return 1
        key = os.environ.get("LITELLM_MASTER_KEY", "")
        if not key:
            print("  LITELLM_MASTER_KEY is missing from .env, and the proxy needs "
                  "it to accept the pass.", file=sys.stderr)
            return 1
        env["FW_ENDPOINT"] = PROXY_URL
        env["FW_TOKEN"] = key
        forward = ["-e", "FW_ENDPOINT", "-e", "FW_TOKEN"]
        print(f"  {args.model} goes through the proxy at {PROXY_URL}")

    cmd = ["docker", "compose", "-f", str(compose), "run", "--build", "--rm", "-d",
           *forward, "--name", name, "bench", *passthru]
    # Echo the command with the API key masked.
    shown, mask = [], False
    for a in cmd:
        shown.append("<redacted>" if mask else a)
        mask = a == "--api-key"
    print("  " + " ".join(shown))
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
