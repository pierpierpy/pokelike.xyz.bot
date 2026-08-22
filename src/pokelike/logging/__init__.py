"""Shared pass-logging machinery: progress log, heartbeat, trace enrichment.

This package is the neutral home that both the bot competition (`arena/`) and the
model benchmark (`harness/`) import from. It lives here rather than inside either
consumer because the dependency must not point the wrong way: the arena should not
import the harness and the harness should not import the arena, but both need a log
that writes per-run progress, a per-decision JSONL trace, and a heartbeat file.

The writer takes what it needs (folder, file stem, header line, whether the thing
being logged keeps notes) rather than knowing about harnesses or models. Domain-
specific sentences (what the log says about itself) are passed in by the caller.
"""

from .conversation import Conversations
from .heartbeat import HEARTBEAT_SECS, HEARTBEAT_STALE, HeartbeatThread
from .passlog import LEARN_K, PassLog
from .trace import enrich_decision

__all__ = [
    "Conversations",
    "HEARTBEAT_SECS",
    "HEARTBEAT_STALE",
    "HeartbeatThread",
    "LEARN_K",
    "PassLog",
    "enrich_decision",
]
