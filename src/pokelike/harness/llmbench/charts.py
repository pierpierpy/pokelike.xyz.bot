"""The chart the llm-bench README carries: what a version's badges cost.

One image per harness version, because a version is the question a row answers
and putting two versions on one pair of axes would invite the comparison the
standings refuse to make.

The picture answers what the table cannot at a glance, since `badges~` and `$`
sit at opposite ends of a wide row: which passes nothing beats on both price and
result. Under v7 that frontier runs from a free model at 1.22 badges to
`google/gemini-3.7-flash` at 2.56 for about nine dollars, and the error bars are
half the message, because the two middle steps are a dollar apart with intervals
that overlap.

matplotlib is an optional dependency, so `available()` is asked first and every
caller carries on without charts when the answer is no.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# Badges cap at eight, because the engine has eight gym leaders and the Elite
# Four after them awards none. The axis is fixed to that range so every version's
# chart is read against the same scale.
BADGE_MAX = 8


def available() -> bool:
    """Returns whether the charts can be drawn at all."""
    try:
        import matplotlib  # noqa: F401
    except ImportError:
        return False
    return True


def _rows(version: str) -> list[dict[str, Any]]:
    """Returns one entry per recorded pass of a full fifty runs, best mean first.

    A partial pass is left out because it records no result either, so a chart
    and a table always describe the same set of measurements.
    """
    from .results import load
    from .versions import settings_text

    out = []
    for doc in load(version):
        for p in doc.get("passes", []):
            runs = p.get("runs") or []
            if len(runs) < 50:
                continue
            counts = [0] * (BADGE_MAX + 1)
            for r in runs:
                b = r.get("badges") or 0
                if 0 <= b <= BADGE_MAX:
                    counts[b] += 1
            total = sum(counts) or 1
            mean = sum(i * c for i, c in enumerate(counts)) / total
            # The standard error of the mean over the runs, which is what tells a
            # real gap from sampling noise on a game this variable.
            var = sum(c * (i - mean) ** 2 for i, c in enumerate(counts)) / total
            sett = settings_text(version, p.get("settings"))
            out.append({
                "model": doc.get("model") or "unknown",
                "set": sett,
                # Only the part that differs between passes of one model, so a
                # label on a chart stays short.
                "set_short": (sett.split(",")[-1] if "," in sett else sett),
                "mean": mean,
                "sem": (var / total) ** 0.5,
                "counts": counts,
                "runs": total,
                "tokens_in": sum(r.get("tokens_in") or 0 for r in runs),
                "tokens_out": sum(r.get("tokens_out") or 0 for r in runs),
            })
    out.sort(key=lambda r: -r["mean"])
    return out


def _frontier(points: list[tuple[float, float]]) -> list[int]:
    """Returns the indices of the points nothing else beats on both axes.

    A pass is on the frontier when no other pass costs the same or less and earns
    the same or more badges. Cheap and dear are compared inside one version only,
    because two harness versions ask different questions and their rows are never
    ranked against each other.
    """
    keep = []
    for i, (cost_i, badges_i) in enumerate(points):
        beaten = any(c <= cost_i and b >= badges_i and (c < cost_i or b > badges_i)
                     for j, (c, b) in enumerate(points) if j != i)
        if not beaten:
            keep.append(i)
    return sorted(keep, key=lambda i: points[i][0])


def cost_chart(version: str, path: Path,
               price: dict[str, dict[str, float]] | None = None) -> Path | None:
    """Draws what a version's badges cost, and the frontier of what is worth paying.

    The vertical bars are the standard error of the mean, and they are the point of
    the picture as much as the positions are: fifty runs of a game this noisy carry
    an error near a tenth of a badge, so two passes whose bars overlap are not
    reliably telling apart.

    Cost is priced from the provider's list at drawing time and is never stored, so
    this image is a snapshot of today's prices rather than a fact about the passes.
    A pass whose model the list does not know is left out, and the caption says how
    many.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from .pricing import cached_prices, cost as price_of

    rows = _rows(version)
    if not rows:
        return None
    price = price if price is not None else cached_prices()

    pts, labels, sems, unpriced = [], [], [], 0
    for r in rows:
        c = price_of(r["tokens_in"], r["tokens_out"], price.get(r["model"]))
        if c is None:
            unpriced += 1
            continue
        pts.append((c, r["mean"]))
        labels.append(r["model"].split("/")[-1] + (f"\n{r['set_short']}" if r["set_short"] else ""))
        sems.append(r["sem"])
    if not pts:
        return None

    fig, ax = plt.subplots(figsize=(9.0, 5.0))
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    ax.errorbar(xs, ys, yerr=sems, fmt="o", color="#4c6ef5", ecolor="#adb5bd",
                elinewidth=1.2, capsize=3, markersize=7, zorder=3)

    front = _frontier(pts)
    if len(front) > 1:
        ax.step([pts[i][0] for i in front], [pts[i][1] for i in front],
                where="post", color="#e8590c", linewidth=1.4, zorder=2,
                label="nothing beats these on both price and badges")
        ax.legend(fontsize=8, loc="lower right", frameon=False)
    for i in front:
        ax.scatter([pts[i][0]], [pts[i][1]], s=150, facecolors="none",
                   edgecolors="#e8590c", linewidths=1.4, zorder=4)

    # Only the frontier is labelled. Eleven of these fourteen passes cost under two
    # dollars, so labelling all of them buries the picture under its own text, and
    # the table below the chart already carries every exact figure.
    for i in front:
        ax.annotate(labels[i], pts[i], textcoords="offset points", xytext=(9, 4),
                    fontsize=8, linespacing=1.2, color="#c2410c")

    cap = (f"Badges against cost, harness {version}, {len(pts)} passes")
    if unpriced:
        cap += f" ({unpriced} left out: no published price)"
    ax.set_title(cap + "\nring and line mark what nothing beats on both price and "
                       "badges; bars are the standard error over fifty runs",
                 fontsize=11, loc="left")
    ax.set_xlabel("dollars for one pass of fifty runs, at today's list prices",
                  fontsize=9)
    ax.set_ylabel("mean badges a run", fontsize=9)
    # Linear up to a dollar and logarithmic past it, because a free model has to sit
    # at zero and the interesting crowd is all under two dollars while the dearest is
    # near nine. A plain linear axis flattens the crowd into a single column.
    ax.set_xscale("symlog", linthresh=1.0, linscale=1.4)
    ax.set_xlim(left=-0.06)
    ax.set_xticks([0, 0.25, 0.5, 1, 2, 4, 8])
    ax.get_xaxis().set_major_formatter(
        matplotlib.ticker.FuncFormatter(lambda v, _: "free" if v == 0 else f"${v:g}"))
    ax.tick_params(labelsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(alpha=0.25, linewidth=0.6)
    ax.set_axisbelow(True)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


def write_charts(bench: Path, versions: list[str]) -> list[Path]:
    """Draws every version's cost frontier under <bench>/img/ and returns what was written."""
    out = []
    for v in versions:
        p = cost_chart(v, bench / "img" / f"cost-{v}.png")
        if p is not None:
            out.append(p)
    return out
