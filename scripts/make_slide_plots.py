#!/usr/bin/env python3
"""Slide figures for the Mahalanobis-vs-floor detector comparison on DS-1.

Usage: python3 scripts/make_slide_plots.py
Writes results/fig1..fig6 *.png and results/slide_plots_data.txt (the plotted numbers).

All detection and false-alarm numbers are held-out (four splits of the 300 clean boots:
two interleaved, two time-ordered). Figure 1 and the left panel of figure 2 are descriptive
and use all 300 boots.
"""
import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

SURFACE, INK, INK2, MUTED, GRID, BASE = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
# Colour follows the entity: blue = clean boots, orange = faulted boots, violet = Mahalanobis, aqua = floor.
# Aqua is 2.74:1 on the surface (validator WARN), so every aqua mark here is direct-labelled or in a legend.
BLUE, ORANGE, MAHA, FLOOR = "#2a78d6", "#eb6834", "#6250d6", "#1baf7a"
RAMP = ["#a79df0", "#6250d6", "#3b2e9a"]
plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "text.color": INK, "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.edgecolor": BASE, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "axes.grid.axis": "y", "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.axisbelow": True, "font.size": 10, "axes.titlesize": 12, "axes.titleweight": "bold",
    "axes.titlelocation": "left", "legend.frameon": False,
})

FEAT = ["sub_a", "sub_b", "sub_c"]
CPS = list(range(1, 8))
FAULTS = ["attack", "ft1", "ft2", "ft3", "ft4"]
NAME = {"attack": "Attack (CP3 b)", "ft1": "FT-1 (CP1 b)", "ft2": "FT-2 (CP3 c)", "ft3": "FT-3 (CP7 a)", "ft4": "FT-4 (CP3 a+b)", "ft5": "FT-5 (CP3 c, +84%)"}
OWN_CP = {"attack": [3], "ft1": [1], "ft2": [3], "ft3": [7], "ft4": [3], "ft5": [3]}
CELLS = {"attack": [(3, 1)], "ft1": [(1, 1)], "ft2": [(3, 2)], "ft3": [(7, 0)], "ft4": [(3, 0), (3, 1)], "ft5": [(3, 2)]}
F_FW = 0.45  # floor fraction compiled into src/floor_table.h
data_lines = []


def note(s=""):
    data_lines.append(s)


def load(k):
    df = pd.read_csv(f"data/ds1_{k}.csv").sort_values(["boot_id", "cp"])
    assert (df.cp.values.reshape(-1, 8) == np.arange(8)).all(), k
    a = df[FEAT].to_numpy(float).reshape(-1, 8, 3)
    assert a.shape[0] == 300, k
    return a


D = {k: load(k) for k in ["clean", "attack", "ft1", "ft2", "ft3", "ft4", "ft5"]}
MED = np.median(D["clean"], axis=0)
idx = np.arange(300)
SPLITS = [(idx[0::2], idx[1::2]), (idx[1::2], idx[0::2]), (idx[:150], idx[150:]), (idx[150:], idx[:150])]


def fit_md(train, trim=None):
    m = {}
    for cp in CPS:
        X = train[:, cp, :]
        if trim:
            X = X[~(X > trim * np.median(X, 0)).any(axis=1)]
        mu, ci = X.mean(0), np.linalg.inv(np.cov(X, rowvar=False))
        d = X - mu
        m[cp] = (mu, ci, 1.25 * np.sqrt(np.einsum("ij,jk,ik->i", d, ci, d)).max())
    return m


def md_alarm(m, a, cps):
    out = np.zeros(len(a), bool)
    for cp in cps:
        mu, ci, H = m[cp]
        d = a[:, cp, :] - mu
        out |= np.sqrt(np.einsum("ij,jk,ik->i", d, ci, d)) > H
    return out


def floor_alarm(L, a, cps):
    out = np.zeros(len(a), bool)
    for cp in cps:
        out |= (a[:, cp, :] < L[cp]).any(axis=1)
    return out


def save(fig, name):
    fig.savefig(f"results/{name}", dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("wrote", name)


# ------------------------------------------------------------------ fig 1
def fig1():
    fig, ax = plt.subplots(figsize=(11.5, 5.4))
    rng = np.random.default_rng(0)
    safe = np.where(MED == 0, 1, MED)
    pos = {(cp, s): i * 4 + s for i, cp in enumerate(CPS) for s in range(3)}
    for (cp, s), x in pos.items():
        r = D["clean"][:, cp, s] / safe[cp, s]
        ax.scatter(x + rng.uniform(-0.3, 0.3, len(r)), r, s=5, color=BLUE, alpha=0.35, linewidths=0, zorder=2)
    note("FIG 1. Ratio to the clean median per sub-stage (300 boots). Lowest clean ratio over the 21 cells: "
         f"{(D['clean'][:, 1:, :] / safe[1:]).min():.2f}; highest {(D['clean'][:, 1:, :] / safe[1:]).max():.2f}")
    label_at = {("attack", 3, 1): "attack\nFT-4", ("ft4", 3, 0): "FT-4", ("ft1", 1, 1): "FT-1", ("ft2", 3, 2): "FT-2", ("ft3", 7, 0): "FT-3"}
    for k, cells in CELLS.items():
        for cp, s in cells:
            r = D[k][:, cp, s] / safe[cp, s]
            x = pos[(cp, s)]
            ax.scatter(x + rng.uniform(-0.3, 0.3, len(r)), r, s=7, color=ORANGE, alpha=0.55, linewidths=0, zorder=3)
            note(f"   {k} CP{cp}.{'abc'[s]}: median ratio {np.median(r):.2f}, highest boot {r.max():.2f}")
            if (k, cp, s) in label_at:
                ax.text(x, np.quantile(r, 0.02) * 0.8, label_at[(k, cp, s)], ha="center", va="top", fontsize=8.5, color=INK2)
            if k == "ft5":
                ax.text(x, np.median(r) * 1.35, "FT-5", ha="center", va="bottom", fontsize=8.5, color=INK2,
                        bbox=dict(boxstyle="round,pad=0.15", fc=SURFACE, ec="none", alpha=0.85))
    ax.axhline(1.0, color=BASE, lw=0.8, zorder=1)
    ax.axhline(F_FW, color=INK2, lw=1.1, ls=(0, (4, 3)), zorder=4)
    ax.text(len(CPS) * 4 - 2.2, F_FW * 1.06, f"floor: {F_FW} x median", ha="right", va="bottom", fontsize=9, color=INK2)
    ax.set_yscale("log")
    ax.set_ylim(0.03, 12)
    ax.set_yticks([0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10])
    ax.set_yticklabels(["0.05x", "0.1x", "0.2x", "0.5x", "1x", "2x", "5x", "10x"])
    ax.yaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    ax.set_xticks(list(pos.values()))
    ax.set_xticklabels(["abc"[s] for (_, s) in pos])
    ax.set_xlim(-1, len(CPS) * 4 - 1.2)
    for i, cp in enumerate(CPS):
        ax.annotate(f"CP{cp}", xy=(i * 4 + 1, 0), xycoords=("data", "axes fraction"), xytext=(0, -24),
                    textcoords="offset points", ha="center", fontsize=10, color=INK2)
    ax.set_ylabel("sub-stage time / clean median")
    ax.set_title("Skipped loops fall far below the clean range; timing spikes only go up", pad=34)
    ax.legend(handles=[Line2D([], [], marker="o", ls="", color=BLUE, alpha=0.7, label="clean boots (300 per sub-stage)"),
                       Line2D([], [], marker="o", ls="", color=ORANGE, alpha=0.8, label="faulted boots, at the sub-stage they hit (300 each)")],
              loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, handlelength=1, fontsize=9.5)
    fig.text(0.01, -0.02, "Each fault build is compared with the median of the separate clean build (a different binary). DS-1, 300 boots per build.",
             fontsize=8.5, color=MUTED)
    save(fig, "fig1_clean_vs_faulted_timing.png")


# ------------------------------------------------------------------ fig 2
def fig2():
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11.5, 4.6))
    X = D["clean"][:, 3, :]
    mu, ci = X.mean(0), np.linalg.inv(np.cov(X, rowvar=False))
    md = lambda a: np.sqrt(np.einsum("ij,jk,ik->i", a - mu, ci, a - mu))
    c, f = md(X), md(D["attack"][:, 3, :])
    H = 1.25 * c.max()
    bins = np.linspace(0, 40, 41)
    a1.hist(c, bins=bins, color=BLUE, alpha=0.75, label="clean boots")
    a1.hist(f, bins=bins, color=ORANGE, alpha=0.75, label="attack boots")
    a1.axvline(H, color=INK2, lw=1.1, ls=(0, (4, 3)))
    a1.text(H + 0.6, a1.get_ylim()[1] * 0.92, f"threshold H = {H:.1f}\n(1.25 x largest clean)", fontsize=9, color=INK2, va="top")
    a1.set_xlabel("Mahalanobis distance at CP3")
    a1.set_ylabel("boots")
    a1.set_title("Mahalanobis: attack sits inside the clean range", pad=24)
    a1.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, handlelength=1, fontsize=9.5)
    note(f"FIG 2 left. CP3 Gaussian fitted on all 300 clean boots (in-sample): largest clean MD {c.max():.1f}, H {H:.1f}; "
         f"attack MD median {np.median(f):.1f}, max {f.max():.1f}; attack boots above H: {(f > H).sum()}")
    safe = MED[3, 1]
    cr, fr = D["clean"][:, 3, 1] / safe, D["attack"][:, 3, 1] / safe
    lb = np.logspace(np.log10(0.05), np.log10(8), 45)
    a2.hist(cr, bins=lb, color=BLUE, alpha=0.75, label="clean boots")
    a2.hist(fr, bins=lb, color=ORANGE, alpha=0.75, label="attack boots")
    a2.axvline(F_FW, color=INK2, lw=1.1, ls=(0, (4, 3)))
    a2.text(F_FW / 1.08, a2.get_ylim()[1] * 0.92, f"floor\n{F_FW} x median", fontsize=9, color=INK2, va="top", ha="right")
    a2.set_xscale("log")
    a2.set_xticks([0.1, 0.2, 0.5, 1, 2, 5])
    a2.set_xticklabels(["0.1x", "0.2x", "0.5x", "1x", "2x", "5x"])
    a2.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    a2.set_xlabel("CP3 sub_b / clean median")
    a2.set_ylabel("boots")
    a2.set_title("Floor: attack sits well below the clean range", pad=24)
    a2.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, handlelength=1, fontsize=9.5)
    note(f"FIG 2 right. CP3 sub_b ratio to clean median: clean min {cr.min():.2f}, attack median {np.median(fr):.2f}, "
         f"attack highest boot {fr.max():.2f}; attack boots below {F_FW}: {(fr < F_FW).sum()} of 300; clean boots below {F_FW}: {(cr < F_FW).sum()}")
    save(fig, "fig2_mahalanobis_vs_floor_cp3.png")


# ------------------------------------------------------------------ fig 3
def fig3():
    methods = ["Mahalanobis, one-shot (per-checkpoint Gaussian)", f"Floor at {F_FW} x median"]
    det = {m: {k: [] for k in FAULTS + ["ft5"]} for m in methods}
    fa = {m: 0 for m in methods}
    for tr, te in SPLITS:
        mm = fit_md(D["clean"][tr])
        L = F_FW * np.median(D["clean"][tr], axis=0)
        fa[methods[0]] += md_alarm(mm, D["clean"][te], CPS).sum()
        fa[methods[1]] += floor_alarm(L, D["clean"][te], CPS).sum()
        for k in FAULTS + ["ft5"]:
            det[methods[0]][k].append(md_alarm(mm, D[k], OWN_CP[k]).mean() * 100)
            det[methods[1]][k].append(floor_alarm(L, D[k], OWN_CP[k]).mean() * 100)
    fig, ax = plt.subplots(figsize=(10.5, 5.2))
    ks = FAULTS + ["ft5"]
    ypos = np.arange(len(ks))[::-1]
    h = 0.34
    for j, (m, col) in enumerate(zip(methods, [MAHA, FLOOR])):
        mean = np.array([np.mean(det[m][k]) for k in ks])
        lo = mean - np.array([np.min(det[m][k]) for k in ks])
        hi = np.array([np.max(det[m][k]) for k in ks]) - mean
        y = ypos + (0.19 if j == 0 else -0.19)
        ax.barh(y, mean, height=h, color=col, zorder=2)
        ax.errorbar(mean, y, xerr=[lo, hi], fmt="none", ecolor=INK2, elinewidth=0.9, capsize=2.5, zorder=3)
        for yy, v, k in zip(y, mean, ks):
            ax.text(max(v + np.max(det[m][k]) - v, v) + 2.0, yy, f"{v:.0f}%", va="center", fontsize=9, color=INK)
        note(f"FIG 3. {m}: " + ", ".join(f"{k} {np.mean(det[m][k]):.1f}% (splits {min(det[m][k]):.0f}-{max(det[m][k]):.0f})" for k in ks))
    ax.set_yticks(ypos)
    ax.set_yticklabels([NAME[k] for k in ks])
    ax.set_xlim(0, 108)
    ax.set_xlabel("faulted boots detected at the faulted checkpoint (%), mean of 4 held-out splits; whisker = lowest to highest split")
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", visible=True)
    ax.set_title("Detection per fault: the floor detects 99% or more of each skipped-loop fault; one-shot Mahalanobis 1% to 18%", pad=30, fontsize=11)
    ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=MAHA), plt.Rectangle((0, 0), 1, 1, color=FLOOR)], labels=methods,
              loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, handlelength=1, fontsize=9.5)
    ax.text(12, ypos[-1] - 0.19, "FT-5 adds work, so a lower bound cannot see it", fontsize=8.5, color=INK2, va="center")
    t = 600
    fig.text(0.01, -0.03, f"Clean false alarms on {t} held-out clean boots, monitoring CP1-7: Mahalanobis {fa[methods[0]]} ({fa[methods[0]] / t:.0%}), floor {fa[methods[1]]} ({fa[methods[1]] / t:.0%}).",
             fontsize=9, color=INK2)
    note(f"FIG 3. Clean false alarms (600 held-out boots, CP1-7): Mahalanobis {fa[methods[0]]}, floor {fa[methods[1]]}")
    save(fig, "fig3_detection_by_fault.png")


# ------------------------------------------------------------------ fig 4
def fig4():
    rs = np.arange(0, 0.951, 0.05)
    models = [(fit_md(D["clean"][tr]), F_FW * np.median(D["clean"][tr], axis=0), te) for tr, te in SPLITS]
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.6), sharey=True)
    for ax, (title, cols) in zip(axes, [("One sub-stage shortened (CP3 sub_b)", [1]), ("All three CP3 sub-stages shortened together", [0, 1, 2])]):
        res = {"md": [], "fl": []}
        for r in rs:
            hit_m = hit_f = tot = 0
            for mm, L, te in models:
                a = D["clean"][te].copy()
                a[:, 3, cols] *= 1 - r
                hit_m += md_alarm(mm, a, [3]).sum()
                hit_f += floor_alarm(L, a, [3]).sum()
                tot += len(te)
            res["md"].append(100 * hit_m / tot)
            res["fl"].append(100 * hit_f / tot)
        ax.plot(rs * 100, res["fl"], color=FLOOR, lw=2, marker="o", ms=4, mfc=SURFACE, mew=1.5, label=f"Floor at {F_FW} x median")
        ax.plot(rs * 100, res["md"], color=MAHA, lw=2, marker="o", ms=4, mfc=SURFACE, mew=1.5, label="Mahalanobis, one-shot")
        ax.set_title(title, fontsize=11, pad=8)
        ax.set_xlabel("synthetic reduction of the sub-stage time (%)")
        ax.set_ylim(-3, 103)
        ax.set_xlim(0, 96)
        ax.text(95, res["fl"][-1] - 8, "floor", color=INK2, fontsize=9, ha="right", va="top")
        ax.text(95, res["md"][-1] + 4, "Mahalanobis", color=INK2, fontsize=9, ha="right", va="bottom")
        note(f"FIG 4 ({title}). reduction % : floor / Mahalanobis detection % -> " + "; ".join(f"{int(r * 100)}: {f:.0f}/{m:.0f}" for r, f, m in zip(rs, res['fl'], res['md']) if int(round(r * 100)) % 10 == 0))
    axes[0].set_ylabel("held-out clean boots flagged (%)")
    fig.suptitle("Synthetic severity sweep: the floor needs roughly a 55% reduction; Mahalanobis stays at about 1% or less", x=0.125, ha="left", y=1.02, fontsize=12, fontweight="bold")
    fig.text(0.125, -0.02, "Held-out clean CP3 boots with the chosen sub-stages scaled by (1 - reduction), pooled over 4 splits (600 boots per point). QEMU cannot produce partial skips (ISSUE-012).",
             fontsize=8.5, color=MUTED)
    save(fig, "fig4_severity_sweep.png")


# ------------------------------------------------------------------ fig 5
def fig5():
    fs = np.round(np.arange(0.2, 0.701, 0.05), 2)
    fa, xb, miss = [], [], []
    for f in fs:
        fa_n = xb_n = 0
        ms = {k: 0 for k in FAULTS}
        for tr, te in SPLITS:
            L = f * np.median(D["clean"][tr], axis=0)
            fa_n += floor_alarm(L, D["clean"][te], CPS).sum()
            for k in FAULTS:
                xb_n += floor_alarm(L, D[k], [c for c in CPS if c not in OWN_CP[k]]).sum()
                ms[k] += (~floor_alarm(L, D[k], OWN_CP[k])).sum()
        fa.append(100 * fa_n / 600)
        xb.append(100 * xb_n / 6000)
        miss.append(100 * max(ms.values()) / 1200)
    # Three small panels with their own y scales: on one shared 0-100% axis the two
    # false-alarm curves sit on top of each other along the floor.
    fig, axes = plt.subplots(1, 3, figsize=(12.5, 4.4), sharex=True)
    panels = [("Faults missed (worst of the five)", miss, 105),
              ("Alarms at checkpoints the fault does not touch", xb, 11),
              ("False alarms on clean boots", fa, 2.2)]
    for ax, (ttl, ys, top) in zip(axes, panels):
        ax.axvspan(0.30, 0.50, color=FLOOR, alpha=0.10, lw=0)
        ax.axvline(F_FW, color=INK2, lw=1.1, ls=(0, (4, 3)))
        ax.plot(fs, ys, color=FLOOR, lw=2, marker="o", ms=4.5, mfc=SURFACE, mew=1.5)
        for fx in [0.3, 0.5, 0.7]:
            v = ys[list(fs).index(fx)]
            ax.annotate(f"{v:.1f}%", xy=(fx, v), xytext=(0, 9), textcoords="offset points", ha="center", fontsize=9, color=INK)
        ax.set_ylim(-0.04 * top, top)
        ax.set_title(ttl, fontsize=10.5, pad=8)
        ax.set_xlabel("floor fraction f")
        ax.set_xticks([0.2, 0.3, 0.4, 0.5, 0.6, 0.7])
    axes[0].set_ylabel("boots (%)")
    fig.suptitle("Choosing f: below 0.3 faults slip through, above 0.5 untouched checkpoints start to alarm", x=0.07, ha="left", y=1.03, fontsize=12, fontweight="bold")
    for f, a, b, c in zip(fs, fa, xb, miss):
        note(f"FIG 5. f={f:.2f}: clean FA {a:.1f}% | untouched-checkpoint alarms {b:.1f}% | worst-fault miss {c:.1f}%")
    fig.text(0.07, -0.04, f"Shaded: f = 0.30 to 0.50. Dashed line: f = {F_FW}, the value compiled into the firmware. "
             "Held-out, pooled over 4 splits (600 clean boots; 6000 boots from the 5 fault builds; 1200 per fault).", fontsize=8.5, color=MUTED)
    save(fig, "fig5_floor_fraction_sweep.png")


# ------------------------------------------------------------------ fig 6
def fig6():
    trims = [(None, "no trimming"), (3.0, "trim training boots > 3x median"), (1.5, "trim training boots > 1.5x median")]
    det = {t: {k: [] for k in FAULTS} for t, _ in trims}
    fa3 = {t: 0 for t, _ in trims}
    faa = {t: 0 for t, _ in trims}
    for tr, te in SPLITS:
        for t, _ in trims:
            m = fit_md(D["clean"][tr], t)
            fa3[t] += md_alarm(m, D["clean"][te], [3]).sum()
            faa[t] += md_alarm(m, D["clean"][te], CPS).sum()
            for k in FAULTS:
                det[t][k].append(100 * md_alarm(m, D[k], OWN_CP[k]).mean())
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.8), gridspec_kw={"width_ratios": [2.3, 1]})
    w = 0.26
    x = np.arange(len(FAULTS))
    for j, ((t, lab), col) in enumerate(zip(trims, RAMP)):
        v = [min(det[t][k]) for k in FAULTS]
        a1.bar(x + (j - 1) * w, v, w * 0.92, color=col, zorder=2, label=lab)
        for xx, vv in zip(x + (j - 1) * w, v):
            a1.text(xx, vv + 1.5, f"{vv:.0f}", ha="center", va="bottom", fontsize=8, color=INK)
        note(f"FIG 6A. {lab}: worst-split detection % " + ", ".join(f"{k} {min(det[t][k]):.0f}" for k in FAULTS))
    a1.set_xticks(x)
    a1.set_xticklabels([NAME[k].replace(" (", "\n(") for k in FAULTS], fontsize=9)
    a1.set_ylim(0, 112)
    a1.set_ylabel("faulted boots detected, worst split (%)")
    a1.set_title("Detection (monitored checkpoint of each fault)", fontsize=11, pad=8)
    a1.grid(axis="x", visible=False)
    a1.legend(loc="lower left", bbox_to_anchor=(0, 1.09), ncol=3, handlelength=1, fontsize=9)
    fig.suptitle("Mahalanobis with spiked training boots removed: revived at one checkpoint, not across all seven", x=0.07, ha="left", y=1.12, fontsize=12, fontweight="bold")
    xs = np.arange(2)
    for j, ((t, lab), col) in enumerate(zip(trims, RAMP)):
        v = [100 * fa3[t] / 600, 100 * faa[t] / 600]
        a2.bar(xs + (j - 1) * w, v, w * 0.92, color=col, zorder=2)
        for xx, vv in zip(xs + (j - 1) * w, v):
            a2.text(xx, vv + 0.5, f"{vv:.1f}", ha="center", va="bottom", fontsize=8, color=INK)
        note(f"FIG 6B. {lab}: clean false alarms CP3 only {v[0]:.1f}%, CP1-7 {v[1]:.1f}% (of 600)")
    a2.set_xticks(xs)
    a2.set_xticklabels(["monitor CP3 only", "monitor CP1-7"], fontsize=9)
    a2.set_ylim(0, 20)
    a2.set_ylabel("clean boots with a false alarm (%)")
    a2.set_title("False alarms", fontsize=11, pad=8)
    a2.grid(axis="x", visible=False)
    fig.text(0.07, -0.03, "Per-checkpoint Gaussian, H = 1.25 x largest training distance. Held-out, 4 splits. A 3x trim leaves the 1.5x to 3x spikes in, so it changes nothing.",
             fontsize=8.5, color=MUTED)
    save(fig, "fig6_mahalanobis_with_trimming.png")


fig1(); fig2(); fig3(); fig4(); fig5(); fig6()
open("results/slide_plots_data.txt", "w").write("\n".join(data_lines) + "\n")
