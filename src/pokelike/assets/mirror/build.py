"""This module orchestrates the five-phase build of the offline game copy."""

from __future__ import annotations

from pathlib import Path

from .fetch import _log, clean
from .phases import (
    phase_numbered,
    phase_played,
    phase_repair,
    phase_static,
    phase_slug,
    phase_verify,
)

PHASES = ("all", "static", "numbered", "slug", "played", "verify")


def build(root: Path, phases: str = "all", log=_log) -> dict:
    """This function builds the offline copy and resumes from a given phase if specified."""
    st = nu = sl = pl = ve = None

    if phases in ("all", "static"):
        log("[1/5] static phase: index, bundle and the assets they name")
        st = phase_static(root, log=log)
        log(f"      {st['ok']} files downloaded, {st['failed']} unavailable")

    if phases in ("all", "numbered"):
        log("[2/5] numbered phase: badges and map backgrounds")
        nu = phase_numbered(root, log=log)
        log(f"      {nu['found']} numbered files")

    if phases in ("all", "slug"):
        log("[3/5] slug phase: URLs built as prefix + name")
        sl = phase_slug(root, log=log)
        log(f"      {sl['found']} found out of {sl['tried']} attempts")
        # The site answers 200 with index.html for missing files, so this step
        # removes anything that slipped past validation before verification runs.
        clean(root, log=log)

    if phases in ("all", "played"):
        log("[4/5] played phase: hunting the URLs built at runtime")
        pl = phase_played(root, log=log)
        log(f"      {pl['recovered']} files recovered by playing")

    if phases not in ("all", "verify"):
        files = sum(1 for _ in root.rglob("*") if _.is_file())
        return {"static": st, "numbered": nu, "slug": sl, "played": pl,
                "verify": None, "files": files}

    log("[5/5] verify: replaying with the network closed")
    ve = phase_verify(root, log=log)

    # The build repairs missing files and re-verifies, up to 3 rounds.
    for round_ in range(3):
        if not ve["missing"]:
            break
        log(f"      repairing {len(ve['missing'])} missing files (round {round_ + 1})")
        phase_repair(root, ve["missing"], log=log)
        ve = phase_verify(root, log=log)

    n = len(ve["missing"])
    if n == 0 and not ve["external_requests"]:
        log("      OK: nothing missing, no requests to the internet")
    else:
        log(f"      WARNING: {n} files missing, "
            f"{len(ve['external_requests'])} external requests")
        for m in ve["missing"][:20]:
            log(f"        missing {m}")

    files = sum(1 for _ in root.rglob("*") if _.is_file())
    mb = sum(p.stat().st_size for p in root.rglob("*") if p.is_file()) / 1e6
    log(f"\ncopy in {root}: {files} files, {mb:.1f} MB")
    return {"static": st, "numbered": nu, "slug": sl, "played": pl, "verify": ve,
            "files": files, "mb": round(mb, 1)}
