"""
make_figures.py — the reliability diagram for the needs_human marginal.

Reads results/run.json. Nothing in this file is transcribed by hand: an earlier
version pasted the bin values in as literals, which meant the figure could silently
disagree with the results it claimed to plot.

Three things the previous version left out, each of which changes how the figure
should be read:

1. Bin sizes. The eight bins hold between 4 and 35 cases. A diagram that draws
   them as identical markers invites the reader to weight a 5-case bin the same as
   a 35-case bin, which is exactly the misreading that produced the claim that
   under-confidence near the threshold explains all sixteen missed escalations.

2. Uncertainty. With n between 4 and 35, most of these bins are consistent with
   perfect calibration. Wilson intervals are drawn so the reader can see which
   deviations are real and which are sampling noise.

3. What the threshold can actually resolve. The elicited marginal only ever takes
   values at one decimal place, so no case falls in (0.2, 0.3). Every threshold in
   that interval yields identical decisions, and 3/13 is simply one point inside
   it. The interval is shaded; drawing the single line implies a precision the
   elicitation does not have.

Usage
    python paper/figures/make_figures.py            # render pdf + png
    python paper/figures/make_figures.py --check    # print the data, no rendering
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUN_JSON = ROOT / "results" / "run.json"

THRESHOLD = 3 / 13          # where escalate_notify overtakes answer


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for an observed frequency.

    Preferred over the normal approximation because several bins sit at or near an
    observed frequency of 0, where the normal interval extends below zero and is
    not usable.
    """
    if n == 0:
        return (0.0, 1.0)
    p, z2 = k / n, z * z
    denom = 1 + z2 / n
    centre = (p + z2 / (2 * n)) / denom
    half = (z / denom) * ((p * (1 - p) / n + z2 / (4 * n * n)) ** 0.5)
    return (max(0.0, centre - half), min(1.0, centre + half))


def figure_data() -> dict:
    """Everything the plot draws, derived from run.json. No matplotlib needed.

    Kept separate from rendering so the numbers can be checked in an environment
    without a plotting library, and so the paper's caption can be verified against
    the same function that draws the figure.
    """
    payload = json.loads(RUN_JSON.read_text())
    cal = payload["summaries"]["all"]["calibration"]["needs_human"]

    bins = []
    for b in cal["bins"]:
        n = b["n"]
        k = round(b["observed_frequency"] * n)
        lo, hi = wilson(k, n)
        edge_lo = float(b["bin"].split("-")[0])
        edge_hi = float(b["bin"].split("-")[1])
        bins.append({
            "bin": b["bin"],
            "n": n,
            "predicted": b["mean_predicted"],
            "observed": b["observed_frequency"],
            "gap": b["gap"],
            "ci": [round(lo, 4), round(hi, 4)],
            "consistent_with_calibrated": lo <= b["mean_predicted"] <= hi,
            "contains_threshold": edge_lo <= THRESHOLD < edge_hi,
        })

    # The interval of thresholds that cannot be distinguished from 3/13, given what
    # the elicitation actually emits.
    values = sorted({row["belief"]["needs_human"] for row in payload["rows"]})
    below = max((v for v in values if v <= THRESHOLD), default=THRESHOLD)
    above = min((v for v in values if v > THRESHOLD), default=THRESHOLD)

    # The diagram is drawn as separate segments wherever a bin is empty, so the
    # line never implies data in a range that has none.
    segments, current = [], []
    expected = None
    for b in bins:
        idx = int(round(b["predicted"] * 10))
        if expected is not None and idx != expected:
            segments.append(current)
            current = []
        current.append(b)
        expected = idx + 1
    if current:
        segments.append(current)

    return {
        "ece": cal["ece"],
        "n": cal["n"],
        "threshold": THRESHOLD,
        "indistinguishable_interval": [below, above],
        "bins": bins,
        "segments": [[b["bin"] for b in seg] for seg in segments],
        "_segments": segments,
        "empty_bins": [f"{i / 10:.1f}-{(i + 1) / 10:.1f}" for i in range(10)
                       if not any(int(round(b["predicted"] * 10)) == i for b in bins)],
    }


def render(data: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Times New Roman", "DejaVu Serif"],
        "font.size": 9, "axes.labelsize": 9,
        "xtick.labelsize": 8, "ytick.labelsize": 8, "legend.fontsize": 7,
    })

    fig, ax = plt.subplots(figsize=(3.375, 2.9))

    ax.plot([0, 1], [0, 1], ls="--", lw=0.8, color="0.6",
            label="perfect calibration", zorder=1)

    lo, hi = data["indistinguishable_interval"]
    ax.axvspan(lo, hi, color="0.88", zorder=0,
               label=f"thresholds equivalent to $3/13$\n(no case in ({lo:g}, {hi:g}])")
    ax.axvline(data["threshold"], ls="--", lw=1.0, color="black",
               label=r"threshold $3/13$", zorder=2)

    # Error bars first so the markers sit on top of them.
    for b in data["bins"]:
        ax.plot([b["predicted"]] * 2, b["ci"], lw=0.9, color="0.35",
                solid_capstyle="butt", zorder=3)

    for seg in data["_segments"]:
        ax.plot([b["predicted"] for b in seg], [b["observed"] for b in seg],
                lw=1.3, color="black", zorder=4)

    # Marker area proportional to bin count, so a 35-case bin cannot be read as
    # equal in weight to a 4-case bin.
    ax.scatter([b["predicted"] for b in data["bins"]],
               [b["observed"] for b in data["bins"]],
               s=[8 + 3.2 * b["n"] for b in data["bins"]],
               facecolor="white", edgecolor="black", lw=1.0, zorder=5,
               label="observed (area $\\propto$ bin count)")

    for b in data["bins"]:
        ax.annotate(f"{b['n']}", (b["predicted"], b["observed"]),
                    textcoords="offset points", xytext=(0, -3.2),
                    ha="center", va="center", fontsize=5.2, zorder=6)

    ax.set_xlim(-0.04, 1.04)
    ax.set_ylim(-0.04, 1.04)
    ax.set_xticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_xlabel(r"Predicted $b_h$")
    ax.set_ylabel("Observed frequency")
    ax.grid(True, ls=":", lw=0.5, color="0.85")
    ax.set_axisbelow(True)
    ax.legend(loc="upper left", frameon=False, handlelength=1.4,
              borderpad=0.2, labelspacing=0.35)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)

    fig.tight_layout(pad=0.2)
    for ext in ("pdf", "png"):
        out = HERE / f"reliability-needs-human.{ext}"
        fig.savefig(out, dpi=300, bbox_inches="tight")
        print(f"wrote {out.relative_to(ROOT)}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="print the plotted values and exit; no plotting library needed")
    args = ap.parse_args()

    data = figure_data()

    print(f"ECE {data['ece']} over n={data['n']}; "
          f"threshold 3/13 = {data['threshold']:.4f}")
    print(f"no case in ({data['indistinguishable_interval'][0]:g}, "
          f"{data['indistinguishable_interval'][1]:g}] -> every threshold in that "
          f"interval decides identically")
    print(f"empty bins: {', '.join(data['empty_bins']) or 'none'}")
    print(f"segments drawn: {data['segments']}")
    print(f"\n  {'bin':>9} {'n':>4} {'pred':>6} {'obs':>6} {'gap':>7} "
          f"{'95% CI':>16}  calibrated?  threshold?")
    for b in data["bins"]:
        print(f"  {b['bin']:>9} {b['n']:>4} {b['predicted']:>6.3f} "
              f"{b['observed']:>6.3f} {b['gap']:>+7.3f} "
              f"[{b['ci'][0]:.3f}, {b['ci'][1]:.3f}]"
              f"   {'yes' if b['consistent_with_calibrated'] else 'no':>9}"
              f"   {'<-- contains 3/13' if b['contains_threshold'] else ''}")

    if args.check:
        return 0
    try:
        render(data)
    except ModuleNotFoundError as exc:
        print(f"\ncannot render ({exc}); the values above are still correct. "
              f"Install matplotlib and re-run without --check.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
