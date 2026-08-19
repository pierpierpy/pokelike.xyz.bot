# A container for llm-bench runs that take hours.
#
# Lives here rather than at the repository root because this is the only thing it
# is for. Note that the BUILD CONTEXT is still the root -- the image installs the
# pokelike package from src/ -- so every COPY below is relative to the root, not
# to this directory. Build it with the compose file beside this one, or:
#
#   docker build -f llm-bench/docker/Dockerfile -t pokelike-llm-bench .
#
# WHY THIS EXISTS. A fifty-seed pass against a slow model is a long time to leave
# a browser, a Python process and eight subprocesses attached to a laptop. The
# container is not about isolation for its own sake, it is about the run being
# unable to notice anything you do to the host: no library upgrade halfway
# through, no Chromium updating under it, no sleeping laptop.
#
# WHY THIS BASE IMAGE. The Playwright image ships Chromium together with every
# system library it needs, at a version matched to the Playwright pinned in
# pyproject.toml. That is the single most fragile part of running this anywhere --
# `playwright install` exits 0 even when the host is missing libraries, which is
# how `setup` once reported success on a Raspberry Pi where every later command
# died. Here there is nothing to detect and nothing to get wrong.
#
# THE TAG MUST MATCH. v1.62.0 here is the playwright version in pyproject.toml.
# Bump one and bump the other: a mismatched image carries a browser the Python
# side does not expect to be driving.
FROM mcr.microsoft.com/playwright/python:v1.62.0-noble

# uv, the same tool used outside, so the lockfile means the same thing in here.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# PLAYWRIGHT_BROWSERS_PATH: the browsers are already in the image, so do not go
# looking for them under a home directory that may not exist for the user we run
# as. (A comment cannot sit inside a continued instruction, hence it being here.)
ENV UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PYTHONUNBUFFERED=1 \
    # `docker compose run` allocates a pseudo-tty even with -d, so from in here
    # stderr looks interactive while nobody is reading it -- and tqdm then writes
    # frames separated by carriage returns, which Docker's log driver holds as an
    # unterminated line. The result is `docker logs` showing nothing for the whole
    # run. This makes the bar write whole lines instead. Nothing in a container is
    # ever watching a cursor.
    POKELIKE_PLAIN_BAR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Dependencies first, on their own layer, so editing the source does not reinstall
# them. --frozen because a benchmark that quietly resolved a different version of
# something is not the benchmark you meant to run.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

# Then the project. `site/` is deliberately NOT copied -- it is 130 MB of someone
# else's game, it changes upstream, and its hash is recorded in every result. It
# is mounted at run time instead, so the container plays exactly the copy you
# already downloaded and verified with `pokelike mirror --phase verify`.
COPY . .
RUN uv sync --frozen

# Chromium wants far more shared memory than Docker's default 64 MB, and eight
# workers want eight times whatever one wants. Without this the browsers die
# mid-run with errors that read like the game crashed. Set on the container, not
# here, because a Dockerfile cannot: `--shm-size=2g`, or `--ipc=host`.
#
# No credentials in the image, ever: the token arrives as an environment variable
# at run time and is never part of anything anyone could pull.
#
# Scoped to the model benchmark on purpose. The image contains the whole package
# and could run any subcommand, but this container mounts only what llm-bench
# writes -- so anything else would produce output that dies with the container.
# Baking the subcommand in means `docker compose run bench --harness v0 ...`
# rather than an invitation to run something whose results would be lost.
ENTRYPOINT ["uv", "run", "--frozen", "pokelike", "llm-bench"]
CMD ["--help"]
