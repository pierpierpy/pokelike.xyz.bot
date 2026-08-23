"""This module defines repo-wide default values that more than one module needs to agree on.

`assets/server.py` (the asset server's own default), `assets/mirror/phases.py`
(one phase that plays against the server), `core/game.py` (the default URL,
which must point at the same port), and `interfaces/cli/main.py` (the --port
flag's default) all need the same port number. A single definition here
prevents callers from reaching a server that is not listening because one
literal was updated and the others were not.
"""

from __future__ import annotations

DEFAULT_ASSET_PORT = 8422
