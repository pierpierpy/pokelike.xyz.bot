"""Shared pass-logging machinery, including the progress log, heartbeat, and trace enrichment.

Both `arena/` and `harness/` import from here. The writer accepts a folder, a
file stem, header lines, and a memory flag; the writer knows nothing about
harnesses or models. Domain-specific text is passed in by the caller.
"""

from .conversation import CHAT_SUFFIX, Conversations
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
