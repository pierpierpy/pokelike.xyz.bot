"""The heartbeat timeout, one number shared by the writer and the reader.

`logging/heartbeat.py` (a running pass, touching its `.alive` file) and
`harness/watch/liveness.py` (a watcher, deciding whether a pass is still
alive) both need the exact same cutoff; if they used two independent
definitions, changing one without the other would make the writer's idea of
"still alive" and the reader's idea of "gone silent" disagree. Neither module
imports from the other, both import this.
"""

from __future__ import annotations

# Seconds after which a pass whose .alive file has not been touched is
# considered dead.
HEARTBEAT_STALE = 300.0
