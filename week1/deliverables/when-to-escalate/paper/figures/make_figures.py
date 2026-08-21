import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Reliability of the needs_human marginal, all 100 cases, ECE 0.142.
# Source: results/run.json -> summaries.all.calibration.needs_human.bins
# Bins 0.5-0.6 and 0.6-0.7 contain no cases, hence the two segments.
pred_lo, obs_lo = [0.0, 0.1, 0.2, 0.3, 0.4], [0.250, 0.400, 0.171, 0.588, 0.333]
pred_hi, obs_hi = [0.7, 0.8, 0.9], [0.333, 0.800, 0.917]

THRESHOLD = 3 / 13  # 0.2308 — where escalate_notify overtakes answer

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 9, "axes.labelsize": 9,
    "xtick.labelsize": 8, "ytick.labelsize": 8, "legend.fontsize": 8,
})

fig, ax = plt.subplots(figsize=(3.375, 2.7))

ax.plot([0, 1], [0, 1], ls="--", lw=0.8, color="0.6", label="perfect calibration")
ax.axvline(THRESHOLD, ls="--", lw=1.0, color="black", label=r"threshold $3/13$")
ax.plot(pred_lo, obs_lo, marker="o", ms=4, lw=1.4, color="black", label="observed")
ax.plot(pred_hi, obs_hi, marker="o", ms=4, lw=1.4, color="black")

ax.set_xlim(-0.03, 1.03)
ax.set_ylim(-0.03, 1.03)
ax.set_xticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
ax.set_yticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
ax.set_xlabel(r"Predicted $b_h$")
ax.set_ylabel("Observed frequency")
ax.grid(True, ls=":", lw=0.5, color="0.8")
ax.set_axisbelow(True)
ax.legend(loc="upper left", frameon=False)
for side in ("top", "right"):
    ax.spines[side].set_visible(False)

fig.tight_layout(pad=0.2)
fig.savefig("reliability-needs-human.pdf", bbox_inches="tight")
fig.savefig("reliability-needs-human.png", dpi=300, bbox_inches="tight")
print("wrote reliability-needs-human.pdf and .png")