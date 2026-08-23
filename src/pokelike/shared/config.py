"""Repo-wide default values that more than one module needs to agree on.

`assets/server.py` (the asset server's own default), `assets/mirror/phases.py`
(one phase that plays against the server), `core/game.py` (its default URL,
which must point at the same port), and `interfaces/cli/main.py` (the --port
flag's default) all need the same port number. Before this, each spelled
`8422` out as its own literal; a change to one without the other three would
make some callers reach a server that isn't listening.
"""

from __future__ import annotations

DEFAULT_ASSET_PORT = 8422
