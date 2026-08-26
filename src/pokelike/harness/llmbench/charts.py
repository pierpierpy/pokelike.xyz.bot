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
# A version needs this many recorded passes before its curve means anything.
MIN_PASSES = 3

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


def _monotone_curve(xs: list[float], ys: list[float],
                    n: int = 240) -> tuple[list[float], list[float]]:
    """Returns a dense curve through the given points that never turns back.

    The tangents come from Fritsch and Carlson, so the curve rises where the points
    rise and flattens where they flatten, and it cannot dip below a point it passes
    through. A frontier is a staircase in truth, since nothing buys a fraction of a
    badge, and this curve is the same claim drawn smoothly.
    """
    import numpy as np

    x = [float(v) for v in xs]
    y = [float(v) for v in ys]
    if len(x) < 3:
        return x, y
    h = [x[i + 1] - x[i] for i in range(len(x) - 1)]
    d = [(y[i + 1] - y[i]) / step if step else 0.0 for step, i in zip(h, range(len(h)))]
    m = [0.0] * len(x)
    m[0], m[-1] = d[0], d[-1]
    for i in range(1, len(x) - 1):
        if d[i - 1] * d[i] <= 0:
            m[i] = 0.0
        else:
            w1, w2 = 2 * h[i] + h[i - 1], h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])
    out_x: list[float] = []
    out_y: list[float] = []
    for i in range(len(h)):
        t = np.linspace(0, 1, max(2, n // len(h)))
        h00 = 2 * t ** 3 - 3 * t ** 2 + 1
        h10 = t ** 3 - 2 * t ** 2 + t
        h01 = -2 * t ** 3 + 3 * t ** 2
        h11 = t ** 3 - t ** 2
        out_x += list(x[i] + t * h[i])
        out_y += list(h00 * y[i] + h10 * h[i] * m[i]
                      + h01 * y[i + 1] + h11 * h[i] * m[i + 1])
    return out_x, out_y


def _shade(ax: object, curve_x: list[float], curve_y: list[float],
           pts: list[tuple[float, float]]) -> None:
    """Tints the plane by how a place stands against the frontier.

    A place above the frontier holds more badges than anything in the table reached at
    that price or less, so it is tinted green. A place below the frontier is beaten by
    something no dearer, so it is tinted red. The boundary between the two colours is
    the drawn line itself, which is why the field is built from the same curve rather
    than from a separate rule.

    The tint is faint on purpose, because the positions and the error bars carry the
    argument and this only says which way is better.
    """
    import numpy as np
    from matplotlib.colors import TwoSlopeNorm

    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    # The grid is even in the axis's own transformed space rather than in dollars, so
    # one pixel of the picture covers one cell of the grid. The image is then laid over
    # the axes as a whole, which leaves no quad edges to show as seams.
    tx = ax.xaxis.get_transform()
    lo, hi = tx.transform(np.array([x0, x1], dtype=float))
    gx = tx.inverted().transform(np.linspace(lo, hi, 320))
    gy = np.linspace(y0, y1, 260)
    # Outside the range the frontier covers, the nearest end of it is carried across,
    # because the cheapest pass sets what free money buys and the dearest sets the top.
    level = np.interp(gx, np.asarray(curve_x), np.asarray(curve_y))
    field = gy[:, None] - level[None, :]
    # The colour saturates at the distance most of the recorded passes sit from the
    # frontier, so the three colours carry the picture. Scaling to the whole height
    # instead would leave everything pale, since the corners are far from the line and
    # no pass lives there.
    away = [abs(b - float(np.interp(c, curve_x, curve_y))) for c, b in pts]
    reach = max(float(np.percentile(away, 85)) * 1.6, 0.3)
    ax.imshow(field, extent=(0, 1, 0, 1), transform=ax.transAxes, origin="lower",
              aspect="auto", cmap="RdYlGn", alpha=0.30, zorder=0,
              norm=TwoSlopeNorm(vcenter=0.0, vmin=-reach, vmax=reach),
              interpolation="bilinear")


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
    lo = min(y - e for y, e in zip(ys, sems))
    hi = max(y + e for y, e in zip(ys, sems))
    pad = (hi - lo) * 0.12 or 0.2
    ax.set_ylim(lo - pad, hi + pad)
    ax.errorbar(xs, ys, yerr=sems, fmt="o", color="#4c6ef5", ecolor="#adb5bd",
                elinewidth=1.2, capsize=3, markersize=7, zorder=3)

    front = _frontier(pts)
    curve: tuple[list[float], list[float]] | None = None
    if len(front) > 1:
        curve = _monotone_curve([pts[i][0] for i in front],
                               [pts[i][1] for i in front])
        ax.plot(curve[0], curve[1], color="#e8590c", linewidth=1.6, zorder=2)
    for i in front:
        ax.scatter([pts[i][0]], [pts[i][1]], s=150, facecolors="none",
                   edgecolors="#e8590c", linewidths=1.4, zorder=4)

    # Only the frontier is labelled. Eleven of these fourteen passes cost under two
    # dollars, so labelling all of them buries the picture under its own text, and
    # the table below the chart already carries every exact figure.
    for i in front:
        ax.annotate(labels[i], pts[i], textcoords="offset points", xytext=(9, 4),
                    fontsize=8, linespacing=1.2, color="#c2410c")

    ax.set_title(f"{version} - efficient frontier", fontsize=11)
    ax.set_xlabel("cost ($)", fontsize=9)
    ax.set_ylabel("badges/run", fontsize=9)
    # Linear up to a dollar and logarithmic past it, because a free model has to sit
    # at zero and the interesting crowd is all under two dollars while the dearest is
    # near nine. A plain linear axis flattens the crowd into a single column.
    ax.set_xscale("symlog", linthresh=1.0, linscale=1.4)
    ax.set_xlim(-0.06, max(xs) * 1.18)
    # The ticks double from a quarter and stop past the dearest pass, so the scale
    # covers every point rather than ending under the ones on the right.
    ticks = [0.0, 0.25, 0.5]
    while ticks[-1] < max(xs):
        ticks.append(ticks[-1] * 2)
    ax.set_xticks(ticks)
    ax.get_xaxis().set_major_formatter(
        matplotlib.ticker.FuncFormatter(lambda v, _: "free" if v == 0 else f"${v:g}"))
    ax.tick_params(labelsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(alpha=0.3, linewidth=0.6)
    ax.grid(axis="x", which="minor", alpha=0.14, linewidth=0.5)
    ax.set_axisbelow(True)
    if curve is not None:
        _shade(ax, *curve, pts)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


def _progress(version: str) -> list[dict[str, Any]]:
    """Returns each full pass of a version with its badges in the order played.

    Play order is what matters here rather than seed order, because the notes
    accumulate as the pass goes on, so this sorts the way `results.learning` does.
    """
    from .results import load
    from .versions import settings_text

    out = []
    for doc in load(version):
        for p in doc.get("passes", []):
            runs = p.get("runs") or []
            if len(runs) < 50:
                continue
            played = sorted(runs, key=lambda r: (r.get("order") is None, r.get("order"),
                                                 r.get("seed")))
            sett = settings_text(version, p.get("settings"))
            out.append({
                "model": doc.get("model") or "unknown",
                "set_short": (sett.split(",")[-1] if "," in sett else sett),
                "badges": [r.get("badges") or 0 for r in played],
            })
    return out


def badge_chart(versions: list[str], path: Path) -> Path | None:
    """Draws how far a run gets, as the share of runs ending on each badge count.

    This is the picture that says what the benchmark can and cannot measure. Most
    runs end on one badge, so the badge count carries little room to separate two
    models, and a version whose bars sit on top of another version's bars is not
    telling those two apart.

    An earlier chart here plotted badges against play position and appeared to show
    models improving over the first twenty runs and then declining. That chart was
    withdrawn, because a pass plays the fifty seeds in a fixed order, which makes
    play position and seed identity the same variable, so the curve measured the
    difficulty of the seed sequence. A version carrying no memory between runs drew
    the same curve.

    A version with fewer than MIN_PASSES recorded passes is left out.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    drawn = []
    for version in versions:
        rows = _progress(version)
        if len(rows) < MIN_PASSES:
            continue
        b = [x for r in rows for x in r["badges"]]
        total = len(b) or 1
        drawn.append((version, [100 * b.count(i) / total for i in range(BADGE_MAX + 1)],
                      len(rows), total))
    if not drawn:
        return None

    fig, ax = plt.subplots(figsize=(9.0, 5.0))
    colours = ("#4c6ef5", "#e8590c", "#0ca678", "#ae3ec9", "#f59f00",
               "#1098ad", "#e03131", "#495057")
    width = 0.8 / len(drawn)
    for i, ((version, shares, passes, total), colour) in enumerate(zip(drawn, colours)):
        offset = (i - (len(drawn) - 1) / 2) * width
        ax.bar([x + offset for x in range(BADGE_MAX + 1)], shares, width=width,
               color=colour, label=version, zorder=3)
    ax.legend(fontsize=8, frameon=False)
    ax.set_title("how far a run gets", fontsize=11)
    ax.set_xlabel("badges won in a run", fontsize=9)
    ax.set_ylabel("share of runs (%)", fontsize=9)
    ax.set_xticks(range(BADGE_MAX + 1))
    ax.tick_params(labelsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", alpha=0.3, linewidth=0.6)
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
    # One picture for every version together, because the question it answers is how
    # much room the badge count leaves to tell two models apart.
    p = badge_chart(versions, bench / "img" / "badges.png")
    if p is not None:
        out.append(p)
    return out
