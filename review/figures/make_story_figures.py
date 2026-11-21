#!/usr/bin/env python3
"""Figures for the story-style review deck (review/STORY_DECK_GUIDE.md).

Usage, from pmu_bootrom/:   python3 review/figures/make_story_figures.py [name-prefix ...]
Reads data/*.csv, data/model.npz; writes review/figures/slideNN_*.png and backupBN_*.png (NN = slide number in STORY_DECK_GUIDE.md).
Diagram numbers are copied from STATUS.md, FAULT_MODELS.md and results/*.txt.
Data plots are computed here from the CSV files.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse, FancyArrowPatch, FancyBboxPatch, Polygon

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "data"

SURFACE, INK, INK2, MUTED, GRID, BASE = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
# Colour follows the entity: blue = clean boots, orange = faulted boots / the fault,
# violet = Mahalanobis rule, aqua = floor rule. Aqua is 2.74:1 on the surface, so every aqua mark is labelled.
BLUE, ORANGE, MAHA, FLOOR = "#2a78d6", "#eb6834", "#6250d6", "#1baf7a"
T_BLUE, T_ORANGE, T_MAHA, T_FLOOR, T_GREY = "#e3eefb", "#fdebe3", "#ebe8fb", "#e1f4ec", "#efeee9"
plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "text.color": INK, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "axes.edgecolor": BASE, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "axes.grid.axis": "y", "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.axisbelow": True, "font.size": 12, "axes.titlesize": 14, "axes.titleweight": "bold",
    "axes.titlelocation": "left", "legend.frameon": False,
})
MONO = "DejaVu Sans Mono"

FIGS = []


def fig(name):
    def deco(fn):
        FIGS.append((name, fn))
        return fn
    return deco


def save(f, name):
    f.savefig(HERE / f"{name}.png", dpi=150, facecolor=SURFACE)
    plt.close(f)


def canvas(w=13.0, h=6.0):
    """Blank drawing area, 10 units per inch, origin bottom-left."""
    f = plt.figure(figsize=(w, h))
    ax = f.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, w * 10)
    ax.set_ylim(0, h * 10)
    ax.axis("off")
    return f, ax


def box(ax, x, y, w, h, text="", fc=SURFACE, ec=BASE, lw=1.5, fs=12, weight="normal", tc=INK,
        ls="-", r=1.2, ha="center", pad=1.5, family=None, z=2):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}",
                                fc=fc, ec=ec, lw=lw, ls=ls, zorder=z))
    if text:
        tx = x + w / 2 if ha == "center" else x + pad
        ax.text(tx, y + h / 2, text, ha=ha, va="center", fontsize=fs, fontweight=weight, color=tc,
                zorder=z + 1, family=family, linespacing=1.3)


def arrow(ax, p, q, color=INK2, lw=2.0, ls="-", rad=0.0, ms=16, z=1, style="-|>"):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle=style, mutation_scale=ms, color=color, lw=lw, ls=ls,
                                 connectionstyle=f"arc3,rad={rad}", zorder=z, shrinkA=0, shrinkB=0))


def bolt(ax, cx, cy, s=3.0, color=ORANGE, z=5):
    pts = [(0.18, 1.0), (-0.45, -0.05), (-0.05, -0.05), (-0.22, -1.0), (0.45, 0.18), (0.05, 0.18)]
    ax.add_patch(Polygon([(cx + px * s, cy + py * s) for px, py in pts], closed=True, fc=color, ec=INK,
                         lw=0.8, zorder=z))


def diamond(ax, cx, cy, w, h, text, fc=SURFACE, ec=BASE, lw=1.5, fs=12):
    ax.add_patch(Polygon([(cx, cy + h / 2), (cx + w / 2, cy), (cx, cy - h / 2), (cx - w / 2, cy)],
                         closed=True, fc=fc, ec=ec, lw=lw, zorder=2))
    ax.text(cx, cy, text, ha="center", va="center", fontsize=fs, zorder=3, linespacing=1.25)


def journey(ax, results):
    """Four-stage chain: roadmap (questions only) and summary (with results)."""
    stages = [
        ("STAGE 1", "Python simulation", "Can timing alone\nreveal a skipped loop?",
         "ROC AUC 0.9933 on\nsimulated faults\n(in-sample)",
         "Faults were Python\nsubtraction; the detector\nmust run in the boot ROM"),
        ("STAGE 2", "Port to firmware", "Can it run with no\nfloating point?",
         "1000 / 1000 attacks caught\n14 / 1000 false alarms\nsqrt, threshold, overflow\nbugs fixed",
         "One fault, one checkpoint;\nfalse alarms came from\ntiming spikes"),
        ("STAGE 3", "Widen the test", "Does it hold with 8\ncheckpoints and 6 faults?",
         "It broke: 0 to 3 of 300\nfaults seen; 14% of clean\nboots had timing spikes",
         "A two-sided score cannot\ntell slow spikes from\nfast faults"),
        ("STAGE 4", "One-sided floor", "Is any stage\nsuspiciously short?",
         "0 / 300 false alarms\n298 to 300 / 300 on five\nskipped-loop faults",
         "Real glitches, hardware\ncounters and more\ncheckpoints (Phase 2)"),
    ]
    w, gap, top = 27.0, 6.6, 55.0
    for i, (tag, name, q, res, why) in enumerate(stages):
        x = 1.0 + i * (w + gap)
        hot = i == 2 and results
        h = 32 if results else 24
        box(ax, x, top - h, w, h, fc=T_ORANGE if hot else T_GREY, ec=ORANGE if hot else BASE,
            lw=2.5 if hot else 1.5)
        ax.text(x + 2, top - 3.2, tag, fontsize=10.5, fontweight="bold", color=INK2, va="center")
        ax.text(x + 2, top - 8.0, name, fontsize=15, fontweight="bold", va="center")
        ax.text(x + 2, top - 15.5, q, fontsize=11, color=INK2, va="center", linespacing=1.3)
        if results:
            ax.plot([x + 2, x + w - 2], [top - 20.5, top - 20.5], color=BASE, lw=1)
            ax.text(x + 2, top - 26.2, res, fontsize=10.5, va="center", linespacing=1.35)
        ybox = top - h - 2.0
        ax.text(x + 0.6, ybox - 1.5, "WHAT WENT WRONG" if i < 3 else "WHAT IS STILL OPEN",
                fontsize=9.5, fontweight="bold", color=ORANGE if i < 3 else INK2, va="center")
        ax.text(x + 0.6, ybox - 8.0, why, fontsize=10.5, color=INK, va="center", linespacing=1.3)
        if i < 3:
            arrow(ax, (x + w + 0.6, top - 12), (x + w + gap - 0.6, top - 12))


# ───────────────────────── Part A: introduction ─────────────────────────
@fig("slide02_problem_boot_chain")
def s02():
    f, ax = canvas(13, 6.0)
    names = ["Power on\nor reset", "Boot ROM starts\nand sets up the\nhardware", "Verify the\nsignature of the\nnext stage",
             "Load and run\nthe next stage", "Application\nor OS"]
    w, g, x0, y, h = 20, 6, 3, 34, 13
    for i, t in enumerate(names):
        x = x0 + i * (w + g)
        hot = i == 2
        box(ax, x, y, w, h, t, fc=T_ORANGE if hot else T_GREY, ec=ORANGE if hot else BASE, lw=3 if hot else 1.5,
            fs=13, weight="bold" if hot else "normal")
        if i < 4:
            arrow(ax, (x + w + 0.6, y + h / 2), (x + w + g - 0.6, y + h / 2))
    vx = x0 + 2 * (w + g) + w / 2
    bolt(ax, vx + 14, y + h + 8, 4.0)
    arrow(ax, (vx + 11.5, y + h + 5.2), (vx + 6.5, y + h + 0.6), color=ORANGE, lw=2.5)
    ax.text(vx + 19.5, y + h + 8.5, "voltage or clock glitch\nat exactly this instant", fontsize=12, color=INK2,
            va="center", linespacing=1.3)
    box(ax, 22, 8, 42, 14, "Bad signature: the boot stops\n(what the check is for)", fc=T_GREY, fs=12.5)
    box(ax, 70, 8, 56, 14, "Check skipped: unsigned or malicious code\nruns with full trust at the root of trust",
        fc=T_ORANGE, ec=ORANGE, lw=2.5, fs=12.5, weight="bold")
    arrow(ax, (vx - 4, y - 0.6), (43, 22.8))
    arrow(ax, (vx + 4, y - 0.6), (98, 22.8), color=ORANGE, lw=2.5)
    ax.text(50.5, 28.3, "normal", fontsize=12, color=INK2, ha="center")
    ax.text(91.5, 28.3, "glitched", fontsize=12, color=INK, ha="center", fontweight="bold")
    ax.text(65, 2.4, "Our Phase 1 stub has one such check and no redundancy (anti-pattern A7 in the literature).",
            fontsize=11.5, color=INK2, ha="center")
    return f


@fig("slide03_literature_defences")
def s03():
    f, ax = canvas(13, 5.8)
    cards = [
        ("HARDWARE SENSOR", "92.82%", "detection, ring-oscillator\nsensor on a Virtex-5\nFPGA",
         "Limit: needs FPGA or\nASIC primitives", "He et al., ASP-DAC 2017", False),
        ("HARDWARE SENSOR", "0.4%", "of the FPGA's LUTs (Zynq);\ncovers glitch, laser,\noptical, EM",
         "Limit: silicon area and\nper-platform calibration", "Muttaki et al., HOST 2022", False),
        ("SOFTWARE REDUNDANCY", "0.21 to 484%", "overhead, selective to full\ncoverage; no remaining\nsuccessful attacks",
         "Limit: prevents rather\nthan detects; RISC-V", "Geier et al., ICCAD 2023", False),
        ("ALGORITHM CHECK", "92.56%", "detection on an\nSTM32F303",
         "Limit: works one\nfunction at a time", "Lee et al., Sensors 2025", False),
        ("THIS PROJECT", "firmware only", "statistical timing\ndetector inside the\nboot ROM",
         "Limit: QEMU and one\nsimulated fault family", "Phase 1", True),
    ]
    w, g, x0 = 23.0, 3.2, 1.1
    for i, (grp, big, desc, lim, cite, me) in enumerate(cards):
        x = x0 + i * (w + g)
        ax.text(x + 0.5, 49.5, grp, fontsize=10.5, fontweight="bold", color=INK2, va="center")
        box(ax, x, 12, w, 34, fc=T_BLUE if me else SURFACE, ec=BLUE if me else BASE, lw=2.5 if me else 1.5,
            ls="--" if me else "-")
        ax.text(x + w / 2, 38, big, fontsize=24 if len(big) <= 7 else 16, fontweight="bold", ha="center", va="center")
        ax.text(x + w / 2, 29, desc, fontsize=10.5, ha="center", va="center", linespacing=1.3)
        ax.text(x + w / 2, 20.0, lim, fontsize=10, ha="center", va="center", color=INK2, linespacing=1.3)
        ax.text(x + w / 2, 14.6, cite, fontsize=10.5, ha="center", va="center", color=INK2, style="italic")
    ax.text(65, 5.5, "Numbers are as each paper reports them, on different platforms and fault models.\n"
            "They are not comparable with each other or with our results.", fontsize=11.5, color=INK2,
            ha="center", va="center", linespacing=1.4)
    return f


@fig("slide04_idea_timeline")
def s04():
    f, ax = canvas(13, 5.6)
    sc, x0 = 0.044, 20.0
    a, b, c, bs = 742.5, 828.0, 572.5, 92.0   # clean CP3 medians and the skipped sub_b median (FAULT_MODELS.md)
    labels = [("sub_a", "hash"), ("sub_b", "key load"), ("sub_c", "compare")]

    def row(y, widths, title):
        ax.text(1.5, y + 4, title, fontsize=12.5, fontweight="bold", va="center", linespacing=1.3)
        x = x0
        for k, (wd, (n, d)) in enumerate(zip(widths, labels)):
            hot = widths[1] == bs and k == 1
            if hot:
                box(ax, x, y, max(wd * sc, 0.6), 8, fc=ORANGE, ec=INK, lw=1, r=0.2)
                ax.text(x + wd * sc + 1.0, y + 8.9, "sub_b = 92", fontsize=12, fontweight="bold", va="center")
            else:
                box(ax, x, y, wd * sc, 8, f"{n}  {d}\n{int(wd)}", fc=T_BLUE, ec=BLUE, lw=1.3, fs=11, r=0.6)
            x += wd * sc
        for xx in [x0] + [x0 + sum(widths[:i + 1]) * sc for i in range(3)]:
            ax.plot([xx, xx], [y - 1.2, y + 9.2], color=INK, lw=1.4, zorder=4)
        return x

    ax.text(x0, 50.6, "t0", ha="center", fontsize=11, color=INK2)
    ax.text(x0 + a * sc, 50.6, "t1", ha="center", fontsize=11, color=INK2)
    ax.text(x0 + (a + b) * sc, 50.6, "t2", ha="center", fontsize=11, color=INK2)
    ax.text(x0 + (a + b + c) * sc, 50.6, "t3", ha="center", fontsize=11, color=INK2)
    ax.text(1.5, 50.6, "timer read at:", fontsize=11, color=INK2, va="center")
    end1 = row(35, [a, b, c], "Clean boot,\nsignature verify")
    end2 = row(14, [a, bs, c], "Skipped loop,\nsame stage")
    ax.add_patch(plt.Rectangle((end2, 12.8), end1 - end2, 10.4, fc="none", ec=ORANGE, lw=2, ls="--", zorder=2))
    ax.text((end1 + end2) / 2, 18, "736 cycles\nsaved", fontsize=11, ha="center", va="center", color=INK, linespacing=1.2)
    ax.text(end1 + 1.5, 39, "time", fontsize=11, color=INK2, va="center")
    arrow(ax, (x0 + 30, 31.5), (x0 + 30, 24.5), color=ORANGE, lw=1.8, ms=12, ls="--")
    ax.text(x0 + 32, 28, "fault hits sub_b", fontsize=11, color=INK2, va="center")
    ax.text(65, 5.5, "Learn how long each block normally takes. Raise an alarm when a block is wrong.",
            fontsize=13, ha="center", color=INK)
    ax.text(65, 1.5, "Widths use the clean medians of the final firmware at CP3 (742, 828, 572 cycles) "
            "and the measured median of the skipped sub_b (92).", fontsize=10, ha="center", color=INK2)
    return f


@fig("slide05_testbed")
def s05():
    f, ax = canvas(13, 6.0)
    w, h, g = 26, 13, 8
    xs = [1 + i * (w + g) for i in range(4)]
    top = [("main.c", "clean build plus 6 fault\nmacros (ATTACK, FT-1 to FT-5)"),
           ("arm-none-eabi-gcc", "7 data builds (no halt)\n+ halting builds"),
           ("QEMU 8.2.2", "mps2-an505, Cortex-M33\nSysTick timer"),
           ("UART text output", "cp, elapsed, sub_a,\nsub_b, sub_c per checkpoint")]
    bot = [("Python scripts", "calibrate, validate,\nplot (scripts/)"),
           ("CSV files", "data/*.csv\n300 boots per build"),
           ("UART capture", "one boot per QEMU run")]
    yt, yb = 40, 17
    for i, (a, b) in enumerate(top):
        box(ax, xs[i], yt, w, h, fc=T_GREY)
        ax.text(xs[i] + w / 2, yt + h - 3.6, a, fontsize=12.5, fontweight="bold", ha="center", va="center")
        ax.text(xs[i] + w / 2, yt + 4.2, b, fontsize=10.5, ha="center", va="center", color=INK2, linespacing=1.3)
        if i < 3:
            arrow(ax, (xs[i] + w + 0.6, yt + h / 2), (xs[i + 1] - 0.6, yt + h / 2))
    # bottom row runs right to left: capture -> CSV -> Python -> tables back into firmware
    order = [(3, "Shell script", "one QEMU run per boot,\nparsed into rows"),
             (2, "CSV files", "data/*.csv\n300 boots per build"),
             (1, "Python scripts", "calibrate and validate\n(scripts/)"),
             (0, "Tables back into C", "floor_table.h and the\nMahalanobis constants")]
    for col, a, b in order:
        box(ax, xs[col], yb, w, h, fc=T_BLUE if col != 0 else T_MAHA, ec=BLUE if col != 0 else MAHA, lw=1.5)
        ax.text(xs[col] + w / 2, yb + h - 3.6, a, fontsize=12.5, fontweight="bold", ha="center", va="center")
        ax.text(xs[col] + w / 2, yb + 4.2, b, fontsize=10.5, ha="center", va="center", color=INK2, linespacing=1.3)
    arrow(ax, (xs[3] + w / 2, yt - 0.6), (xs[3] + w / 2, yb + h + 0.6))
    for col in (3, 2, 1):
        arrow(ax, (xs[col] - 0.6, yb + h / 2), (xs[col - 1] + w + 0.6, yb + h / 2))
    arrow(ax, (xs[0] + w / 2, yb + h + 0.6), (xs[0] + w / 2, yt - 0.6), color=MAHA, lw=2.4)
    ax.text(xs[0] + w / 2 + 2, 33.5, "rebuild", fontsize=11, color=INK2, va="center")
    ax.text(1, 6.2, "Limits to keep in mind:", fontsize=12, fontweight="bold", va="center")
    ax.text(26, 6.2, "faults are compile-time macros, not electrical glitches   |   QEMU's SysTick follows "
            "host time, so partial skips are invisible (ISSUE-012)", fontsize=11, color=INK2, va="center")
    return f


@fig("slide06_roadmap")
def s06():
    f, ax = canvas(13, 5.2)
    journey(ax, results=False)
    ax.text(65, 3.2, "Each stage ends with something that did not work, and that is what starts the next one.",
            fontsize=13, ha="center", color=INK)
    return f


# ───────────────────────── Stage 1: Python simulation ─────────────────────────
@fig("slide07_stage1_main_flow")
def s07():
    f, ax = canvas(13, 7.8)
    steps = [("systick_init()", "start the cycle counter"),
             ("uart_init() and banner", "UART0 is the only output"),
             ("pmu_checkpoint(0)", "time origin"),
             ("stage_memory_init(1)", "then pmu_checkpoint(1)"),
             ("stage_signature_verify(2)", "then pmu_checkpoint(2)"),
             ("stage_key_derivation(3)", "then pmu_checkpoint(3)"),
             ("print the log", "CSV rows between DATA_START and DATA_END"),
             ("BOOT COMPLETE", "while (1)")]
    bw, bh, gap, x0, top = 46, 6.2, 2.2, 3, 75.0
    ys = []
    for i, (fn, d) in enumerate(steps):
        y = top - (i + 1) * bh - i * gap
        ys.append(y)
        hot = i == 4
        box(ax, x0, y, bw, bh, fc=T_ORANGE if hot else T_GREY, ec=ORANGE if hot else BASE, lw=3 if hot else 1.5, r=0.9)
        ax.text(x0 + 2, y + bh * 0.66, fn, fontsize=12.5, fontweight="bold", family=MONO, va="center")
        ax.text(x0 + 2, y + bh * 0.26, d, fontsize=10.5, color=INK2, va="center")
        if i:
            arrow(ax, (x0 + bw / 2, ys[i - 1] - 0.1), (x0 + bw / 2, y + bh + 0.1), lw=1.6, ms=11)
    cx, cy, cw, ch = 58, 9, 70, 66
    box(ax, cx, cy, cw, ch, fc=SURFACE, ec=BASE, lw=1.5, ls="--", r=1.5, z=1)
    ax.text(cx + 2, cy + ch - 3.2, "stage_signature_verify(2), the primary glitch target", fontsize=13,
            fontweight="bold", va="center")
    yc = ys[4] + bh / 2
    arrow(ax, (x0 + bw + 0.4, yc), (cx - 0.4, yc), color=ORANGE, lw=2.2, ls="--")
    iw, ix = 38, cx + 2.5
    items = [("chip", "t0 = systick_elapsed()"),
             ("loop", "sub_a: hash loop, 500 iterations", T_BLUE, BLUE),
             ("chip", "t1 = systick_elapsed()"),
             ("loop", "sub_b: key-load loop, 300 iterations", T_ORANGE, ORANGE),
             ("chip", "t2 = systick_elapsed()"),
             ("loop", "sub_c: signature compare, 200 iterations", T_BLUE, BLUE),
             ("chip", "t3 = systick_elapsed()"),
             ("log", "boot_log[2] = { t1-t0, t2-t1, t3-t2 }")]
    y = cy + ch - 8.5
    for it in items:
        if it[0] == "chip":
            hh = 3.8
            y -= hh
            box(ax, ix, y, 25, hh, it[1], fc=T_GREY, fs=10.5, r=0.6, family=MONO)
        elif it[0] == "loop":
            hh = 6.6
            y -= hh
            hot = it[3] == ORANGE
            box(ax, ix, y, iw, hh, it[1], fc=it[2], ec=it[3], lw=3 if hot else 1.3, fs=11, r=0.8, ha="left")
            if hot:
                bolt(ax, ix + iw - 3.2, y + hh / 2, 2.6)
                yb = y + hh / 2
                arrow(ax, (cx + cw - 3, yb), (ix + iw + 0.6, yb), color=ORANGE, lw=2.2)
                ax.text(ix + iw + 1.8, yb + 5.4, "-DGLITCH_ATTACK", fontsize=11, fontweight="bold", va="center")
                ax.text(ix + iw + 1.8, yb - 6.0, "loop cut short or\nskipped: sub_b\nshrinks a lot", fontsize=10.5,
                        color=INK2, va="center", linespacing=1.25)
        else:
            hh = 5.0
            y -= hh
            box(ax, ix, y, iw, hh, it[1], fc=T_GREY, fs=10.5, r=0.8, family=MONO)
        y -= 1.4
    ax.text(x0, 4.5, "No detector in this firmware yet: the Python scripts read the CSV afterwards.",
            fontsize=11.5, color=INK2, va="center")
    return f



# ───────────────────────── Stage 1 figures ─────────────────────────
def _stage1_model():
    m = np.load(DATA / "model.npz")
    return m["mu"], m["cov_inv"], m["X"], float(m["K_SLACK"]), float(m["H_99"])


def _md(Z, mu, Si):
    d = Z - mu
    return np.sqrt(np.einsum("ij,jk,ik->i", d, Si, d))


@fig("slide08_stage1_why_mahalanobis")
def s08():
    mu, Si, X, k, H = _stage1_model()
    f, (a1, a2) = plt.subplots(1, 2, figsize=(13, 5.6), gridspec_kw={"width_ratios": [1.15, 1]})
    f.subplots_adjust(left=0.07, right=0.98, top=0.84, bottom=0.14, wspace=0.28)
    a1.set_axisbelow(True)
    a1.grid(True, axis="both")
    a1.scatter(X[:, 0], X[:, 1], s=14, color=BLUE, alpha=0.45, lw=0, label="496 clean boots")
    A = X[:, :2]
    m2, S2 = A.mean(0), np.cov(A.T)
    w, v = np.linalg.eigh(S2)
    ang = np.degrees(np.arctan2(v[1, 1], v[0, 1]))
    for nsd, ls in ((2, "-"),):
        a1.add_patch(Ellipse(m2, 2 * nsd * np.sqrt(w[1]), 2 * nsd * np.sqrt(w[0]), angle=ang, fc="none", ec=BLUE,
                             lw=1.8, ls=ls))
    x0 = np.array([782.0, 680.0])
    cut = np.array([782.0, 680.0 - 0.2 * mu[1]])
    a1.scatter(*x0, s=90, color=BLUE, ec=INK, zorder=5)
    a1.scatter(*cut, s=110, color=ORANGE, ec=INK, zorder=5, marker="D")
    a1.annotate("", xy=cut, xytext=x0, arrowprops=dict(arrowstyle="-|>", color=ORANGE, lw=2))
    a1.text(x0[0] + 12, x0[1] + 12, "a clean boot", fontsize=11)
    a1.text(cut[0] + 12, cut[1] - 8, "same boot, sub_b cut 20%", fontsize=11, color=INK, fontweight="bold")
    a1.axhline(mu[1] - 2 * np.sqrt(S2[1, 1]), color=MUTED, lw=1, ls=":")
    a1.text(545, mu[1] - 2 * np.sqrt(S2[1, 1]) + 8, "plain 2-sigma limit on sub_b alone", fontsize=10, color=INK2)
    a1.set_xlabel("sub_a (cycles)")
    a1.set_ylabel("sub_b (cycles)")
    a1.set_title("The timings rise and fall together", loc="left")
    a1.set_xlim(500, 950)
    a1.set_ylim(380, 780)
    a1.legend(loc="upper left", fontsize=10)
    a2.axis("off")
    r = np.corrcoef(X.T)
    z_cut = (cut[1] - mu[1]) / np.sqrt(S2[1, 1])
    z_a = (x0[0] - mu[0]) / np.sqrt(S2[0, 0])
    z_c = (559 - mu[2]) / np.sqrt(np.cov(X.T)[2, 2])
    md0 = _md(np.array([[782, 680, 559.0]]), mu, Si)[0]
    md1 = _md(np.array([[782, cut[1], 559.0]]), mu, Si)[0]
    rows = [("", "sub_a", "sub_b", "sub_c", "MD"),
            ("clean boot", "782", "680", "559", f"{md0:.2f}"),
            ("sub_b cut 20%", "782", f"{cut[1]:.0f}", "559", f"{md1:.2f}")]
    y = 0.90
    a2.text(0.0, 1.02, "What each test sees for that boot", fontsize=14, fontweight="bold", transform=a2.transAxes)
    for i, row in enumerate(rows):
        for j, t in enumerate(row):
            a2.text([0.0, 0.40, 0.55, 0.70, 0.86][j], y, t, fontsize=12, transform=a2.transAxes,
                    fontweight="bold" if i == 0 or j == 4 else "normal", va="center",
                    color=ORANGE if (i == 2 and j in (2, 4)) else INK)
        y -= 0.09
    a2.plot([0, 1], [0.83, 0.83], color=BASE, lw=1, transform=a2.transAxes)
    a2.text(0.0, 0.64, f"Plain threshold on sub_b: after the cut\nit sits only {abs(z_cut):.1f} standard deviations below\n"
            "its mean. Nothing looks wrong.", fontsize=12, transform=a2.transAxes, va="top",
            linespacing=1.4)
    a2.text(0.0, 0.40, "Mahalanobis distance (MD): sub_a and\nsub_c are above average, so sub_b should\nbe too. A low sub_b beside two high ones\n"
            f"breaks the pattern: MD rises from\n{md0:.2f} to {md1:.2f}.", fontsize=12, transform=a2.transAxes, va="top", linespacing=1.4)
    a2.text(0.0, 0.03, f"Correlation between sub-stages: {r[0,1]:.2f}, {r[0,2]:.2f}, {r[1,2]:.2f}.\n"
            "The plot shows two of the three timings; MD uses all three.",
            fontsize=10.5, color=INK2, transform=a2.transAxes, linespacing=1.4)
    f.text(0.07, 0.94, "Why Mahalanobis distance and not a plain threshold", fontsize=15, fontweight="bold")
    return f


@fig("slide09_stage1_cusum")
def s09():
    mu, Si, X, k, H = _stage1_model()
    c = X[:10]
    g = X[10:20].copy()
    g[:, 1] -= 0.2 * mu[1]
    d = _md(np.vstack([c, g]), mu, Si)
    S, out = 0.0, []
    for v in d:
        S = max(0.0, S + v - k)
        out.append(S)
    out = np.array(out)
    first = int(np.argmax(out > H))
    f, (a1, a2) = plt.subplots(1, 2, figsize=(13, 5.6), gridspec_kw={"width_ratios": [1.25, 1]})
    f.subplots_adjust(left=0.065, right=0.98, top=0.82, bottom=0.14, wspace=0.22)
    t = np.arange(20)
    a1.axvspan(9.5, 19.5, color=T_ORANGE, zorder=0)
    a1.text(14.5, 41, "sub_b cut by 20% from here", ha="center", fontsize=11, color=INK2)
    a1.plot(t, d, color=BLUE, lw=1.4, marker="o", ms=5, label="MD of each boot")
    a1.plot(t, out, color=MAHA, lw=2.4, marker="o", ms=6, label="CUSUM total S")
    a1.axhline(H, color=INK, ls="--", lw=1.5)
    a1.text(0.2, H + 1.0, f"alarm threshold H = {H:.2f}", fontsize=11)
    a1.axhline(k, color=MUTED, ls=":", lw=1.3)
    a1.text(19.3, k + 1.0, f"slack k = {k:.3f}", fontsize=10.5, color=INK2, ha="right")
    a1.scatter([first], [out[first]], s=170, color=ORANGE, ec=INK, zorder=6)
    a1.annotate(f"alarm at boot {first}\n(the 3rd faulted boot)", xy=(first, out[first]), xytext=(first - 6.8, 30),
                fontsize=11, arrowprops=dict(arrowstyle="-|>", color=INK2, lw=1.4))
    a1.set_ylim(0, 44)
    a1.set_xlim(-0.5, 19.5)
    a1.set_xlabel("boot number in the stream")
    a1.set_ylabel("MD or S")
    a1.set_title("One simulated stream: 10 clean boots, then 10 with sub_b cut 20%", loc="left", fontsize=12.5)
    a1.legend(loc="upper left", bbox_to_anchor=(0.0, 0.93), fontsize=10.5)
    # right: how H was chosen
    rng = np.random.default_rng(42)
    n = len(X)
    mds = _md(X, mu, Si)
    mx = np.empty(10000)
    for i in range(10000):
        sS, mm = 0.0, 0.0
        for v in mds[rng.choice(n, 20)]:
            sS = max(0.0, sS + v - k)
            mm = max(mm, sS)
        mx[i] = mm
    h99 = float(np.percentile(mx, 99))
    a2.hist(mx, bins=np.arange(0, 22, 0.5), color=MAHA, alpha=0.75, lw=0)
    a2.axvline(h99, color=INK, ls="--", lw=1.5)
    a2.text(h99 + 0.3, a2.get_ylim()[1] * 0.80, f"99th percentile\n= {h99:.2f}\nthis is H", fontsize=11)
    a2.set_xlabel("highest S reached in a clean 20-boot sequence")
    a2.set_ylabel("sequences (of 10,000)")
    a2.set_title("How H was chosen", loc="left", fontsize=12.5)
    a2.grid(False)
    f.text(0.065, 0.93, "Stage 1: the CUSUM running total", fontsize=15, fontweight="bold")
    f.text(0.065, 0.885, "S = max(0, S + MD - k):  below k the total drifts back to 0; above k, boot after boot, it climbs.   "
           "(Stream: the first 20 rows of the training file; the cut is applied in Python.)", fontsize=10.5, color=INK2)
    return f


@fig("slide10_stage1_results")
def s10():
    f = plt.figure(figsize=(13, 6.6))
    a1 = f.add_axes([0.07, 0.34, 0.40, 0.46])
    a2 = f.add_axes([0.58, 0.34, 0.38, 0.46])
    sev = ["5%", "10%", "20%", "30%", "50%"]
    det = [4.5, 86.2, 99.7, 99.6, 99.6]
    bars = a1.bar(sev, det, color=BLUE, width=0.62)
    for b_, v in zip(bars, det):
        a1.text(b_.get_x() + b_.get_width() / 2, v + 2, f"{v:.1f}%", ha="center", fontsize=11)
    a1.set_ylim(0, 112)
    a1.set_xlabel("cut applied to sub_b")
    a1.set_ylabel("streams where the alarm fired (%)")
    a1.set_title("Detection by severity (10 faulted boots in a row)", loc="left", fontsize=12.5)
    a1.text(-0.42, 34, "false alarms\n0.1 to 0.5%\nat every level", ha="left", fontsize=10.5, color=INK2, linespacing=1.4)
    n = [1, 3, 10]
    d2 = [2.3, 83, 100]
    b2 = a2.bar([str(x) for x in n], d2, color=ORANGE, width=0.55)
    for b_, v in zip(b2, d2):
        a2.text(b_.get_x() + b_.get_width() / 2, v + 2, f"{v:g}%", ha="center", fontsize=11)
    a2.set_ylim(0, 112)
    a2.set_xlabel("faulted boots in a row (cut = 20%)")
    a2.set_ylabel("detected (%)")
    a2.set_title("But a real boot decides once", loc="left", fontsize=12.5)
    f.text(0.07, 0.94, "Stage 1 result: it works on simulated faults, but only when the fault repeats", fontsize=15, fontweight="bold")
    f.text(0.07, 0.895, "ROC AUC 0.9933 at 20%. Test streams were resampled from the same 496 boots that fitted the model (in-sample).",
           fontsize=11.5, color=INK2)
    f.text(0.07, 0.235, "Why this was not enough", fontsize=12.5, fontweight="bold")
    xs = [0.07, 0.30, 0.53, 0.76]
    items = [("1  Faults were not real", "Python subtracted cycles\nfrom the data (ISSUE-007)."),
             ("2  Test is in-sample", "Streams came from the\nsame 496 boots as the model."),
             ("3  Needs repeated faults", "One faulted boot at 20%:\n2.3% detected."),
             ("4  Exists only in Python", "A defence must run inside the\nboot ROM and halt it (ISSUE-008).")]
    for x, (t, d) in zip(xs, items):
        hot = t[0] in "34"
        f.patches.append(FancyBboxPatch((x - 0.01, 0.025), 0.215, 0.17, boxstyle="round,pad=0,rounding_size=0.01",
                                        transform=f.transFigure, fc=T_ORANGE if hot else T_GREY, ec=ORANGE if hot else BASE, lw=1.6, zorder=1))
        f.text(x, 0.165, t, fontsize=11, fontweight="bold", va="center")
        f.text(x, 0.088, d, fontsize=10.2, color=INK2, va="center", linespacing=1.35)
    return f


# ───────────────────────── Stage 2 figures ─────────────────────────
@fig("slide11_stage2_main_flow")
def s12():
    f, ax = canvas(13, 6.6)
    ax.text(2, 63, "main() in the frozen firmware: the detector is called once, right after checkpoint 2", fontsize=13.5,
            fontweight="bold", va="center")
    cx = 24
    steps = [(54, "pmu_checkpoint(2)", "timer read at the end of stage 2", T_GREY, BASE),
             (45.5, "build features", "f = { sub_a, sub_b, sub_c } of CP2", T_GREY, BASE),
             (37, "cusum_update(&detector, f, 2)", "fixed-point MD, S = S + MD - k, compare with H", T_MAHA, MAHA)]
    for y, t, d, fc, ec in steps:
        box(ax, 2, y, 44, 6.6, fc=fc, ec=ec, lw=2 if ec == MAHA else 1.5, r=0.9)
        ax.text(4, y + 4.6, t, fontsize=12, fontweight="bold", family=MONO, va="center")
        ax.text(4, y + 1.9, d, fontsize=10.5, color=INK2, va="center")
    arrow(ax, (cx, 53.9), (cx, 52.2), lw=1.6, ms=11)
    arrow(ax, (cx, 45.4), (cx, 43.7), lw=1.6, ms=11)
    arrow(ax, (cx, 36.9), (cx, 33.6), lw=1.6, ms=11)
    diamond(ax, cx, 28.6, 36, 9.6, "alarm?\nS > H", fc=SURFACE, ec=INK)
    ax.text(cx + 19.5, 29.8, "no", fontsize=11.5, color=INK2)
    arrow(ax, (cx + 18, 28.6), (62, 28.6), lw=1.6)
    box(ax, 62, 23.4, 30, 10.4, "", fc=T_GREY)
    ax.text(64, 30.7, "stage_key_derivation(3)", fontsize=11.5, fontweight="bold", family=MONO, va="center")
    ax.text(64, 26.4, "boot continues, CSV printed,\nBOOT COMPLETE", fontsize=10.5, color=INK2, va="center", linespacing=1.3)
    ax.text(cx + 2, 20.5, "yes", fontsize=11.5, color=INK2)
    arrow(ax, (cx, 23.7), (cx, 16.6), color=ORANGE, lw=2.4)
    box(ax, 2, 4.8, 44, 11.6, "", fc=T_ORANGE, ec=ORANGE, lw=2.5, r=0.9)
    ax.text(4, 13.7, "!!! ATTACK DETECTED at CP2 !!!", fontsize=11.5, fontweight="bold", family=MONO, va="center")
    ax.text(4, 9.9, "print ALARM_FEATURES, then\nwhile (1) { }   <- the boot halts", fontsize=10.5, family=MONO, va="center",
            linespacing=1.3)
    ax.text(4, 6.1, "(COLLECT_MODE skips the halt so data can be recorded)", fontsize=9.5, color=INK2, va="center")
    # code facts
    box(ax, 98, 4.8, 30, 49.4, "", fc=SURFACE, ec=BASE, ls="--", r=1.2, z=1)
    ax.text(100, 51.2, "Where this lives", fontsize=12, fontweight="bold", va="center")
    facts = ["src/cusum_detector.c\n  fixed_sqrt()\n  mahalanobis_distance()\n  cusum_update()",
             "scripts/calibrate_firmware.py\n  prints mu, cov_inv, k, H\n  as C code",
             "frozen tag:\n  phase1-review-freeze-2"]
    for t, yy in zip(facts, (43.0, 29.0, 15.0)):
        ax.text(100, yy, t, fontsize=10, family=MONO, va="center", linespacing=1.35, color=INK)
    return f


@fig("slide12_stage2_fixed_point")
def s13():
    mu, Si, X, k, H = _stage1_model()
    obs = np.array([690.0, 88.0, 500.0])
    dl = obs - mu
    y = Si @ dl
    q = float(dl @ y)
    f, ax = canvas(13, 6.4)
    ax.text(2, 61, "No floating point in a boot ROM: numbers are stored as whole numbers in 1/65536ths (Q16.16)",
            fontsize=13.5, fontweight="bold", va="center")
    # 32-bit register
    x0, y0, bw = 6, 47, 3.0
    for i in range(32):
        hot = i < 16
        ax.add_patch(plt.Rectangle((x0 + i * bw, y0), bw, 6, fc=T_BLUE if hot else T_MAHA, ec=BASE, lw=0.8))
    ax.text(x0 + 8 * bw, y0 + 8.4, "16 bits: whole part (range about +/- 32,768)", ha="center", fontsize=11)
    ax.text(x0 + 24 * bw, y0 + 8.4, "16 bits: fraction, in steps of 1/65536 = 0.0000153", ha="center", fontsize=11)
    ax.text(x0 + 32 * bw + 3, y0 + 3, "1.5  is stored as  98,304\n0.001665  is stored as  109\n"
            "(reads back as 0.001663)", fontsize=11, va="center", linespacing=1.4)
    ax.plot([x0 + 16 * bw] * 2, [y0 - 1.5, y0 + 7.5], color=INK, lw=2)
    # pipeline
    stage = [("1  Difference", "x - mu", f"[{dl[0]:.1f}, {dl[1]:.1f}, {dl[2]:.1f}]"),
             ("2  Multiply", "y = cov_inv * delta", f"[{y[0]:.3f}, {y[1]:.3f}, {y[2]:.3f}]"),
             ("3  Dot product", "q = delta . y", f"q = {q:.1f}"),
             ("4  Square root", "MD = sqrt(q)", f"MD = {np.sqrt(q):.1f}"),
             ("5  Compare", "MD > H ?", "22.3 > 10.84: alarm")]
    w, g = 22.0, 3.6
    ax.text(2, 38.5, "One attack boot (sub_a, sub_b, sub_c = 690, 88, 500) through the C code", fontsize=12.5,
            fontweight="bold", va="center")
    for i, (a, b, c) in enumerate(stage):
        x = 2 + i * (w + g)
        last = i == 4
        box(ax, x, 12, w, 21, fc=T_ORANGE if last else T_GREY, ec=ORANGE if last else BASE, lw=2.5 if last else 1.5)
        ax.text(x + 1.8, 29.2, a, fontsize=12.5, fontweight="bold", va="center")
        ax.text(x + 1.8, 23.5, b, fontsize=11, family=MONO, va="center")
        ax.text(x + 1.8, 16.4, c, fontsize=10.5, va="center", fontweight="bold" if last else "normal")
        if i < 4:
            arrow(ax, (x + w + 0.4, 22.5), (x + w + g - 0.4, 22.5), lw=1.8, ms=13)
    ax.text(2, 5.5, "Square root with no division: built one bit at a time with compare, subtract and shift only.   "
            "Firmware MD for this boot: 22.29; H = 10.84.", fontsize=11.5, color=INK2, va="center")
    return f


@fig("slide13_stage2_bugs")
def s14():
    f, ax = canvas(13, 6.4)
    ax.text(2, 61, "Two silent failures in the C port, and the fixes", fontsize=13.5, fontweight="bold", va="center")
    # panel 1: sqrt truncation, number line
    box(ax, 1, 6, 41, 50, fc=SURFACE, ec=BASE, ls="--", r=1.2, z=1)
    ax.text(3, 52.5, "1  Square root threw away the decimals", fontsize=12, fontweight="bold", va="center")
    ax.text(3, 46.2, "First version returned 0: nothing alarmed.\nThe first fix kept only the whole part, so\nclose calls rounded down.",
            fontsize=10.5, color=INK2, va="center", linespacing=1.35)
    lx0, lx1, ly = 5, 39, 28
    lo, hi = 14.8, 16.4
    X_ = lambda v: lx0 + (v - lo) / (hi - lo) * (lx1 - lx0)
    ax.plot([lx0, lx1], [ly, ly], color=INK2, lw=2)
    for v in (15, 16):
        ax.plot([X_(v)] * 2, [ly - 1.2, ly + 1.2], color=INK2, lw=1.5)
        ax.text(X_(v), ly - 3.8, str(v), ha="center", fontsize=10.5, color=INK2)
    ax.plot([X_(15.37)] * 2, [ly - 7, ly + 8.5], color=INK, lw=2.4, ls="--")
    ax.text(X_(15.37), ly + 11.0, "alarm line\nMD above 15.37", ha="center", fontsize=10.5, linespacing=1.2)
    for v in (15.5, 15.9):
        ax.scatter([X_(v)], [ly], s=120, color=ORANGE, ec=INK, zorder=5)
        ax.text(X_(v), ly + 3.8, f"{v}", ha="center", fontsize=10.5, fontweight="bold")
        arrow(ax, (X_(v), ly - 1.8), (X_(15.0) + 0.3, ly - 1.8), color=ORANGE, lw=1.6, ms=11, rad=-0.35)
    ax.text(3, 16.6, "True MD 15.5 and 15.9 both became 15,\nunder the line: missed.", fontsize=10.5, va="center", linespacing=1.3)
    ax.text(3, 10.8, "Fix: root in 64-bit, decimals kept. Within one step\nover 2 million test values.", fontsize=10.5,
            color=INK2, va="center", linespacing=1.3)
    # panel 2: overflow, table
    box(ax, 44, 6, 41, 50, fc=SURFACE, ec=BASE, ls="--", r=1.2, z=1)
    ax.text(46, 52.5, "2  Overflow failed open (ISSUE-014)", fontsize=12, fontweight="bold", va="center")
    ax.text(46, 47.3, "Old code, one sub-stage set to a huge value:", fontsize=10.5, color=INK2, va="center")
    rows = [("3,000 cycles", "alarm", False), ("16,000,000 cycles", "alarm", False),
            ("40,000 cycles", "NO ALARM", True), ("4,294,967,295 (wrapped timer)", "NO ALARM", True)]
    yy = 41
    for t, r, bad in rows:
        box(ax, 46, yy - 2.6, 37, 5.4, fc=T_ORANGE if bad else T_GREY, ec=ORANGE if bad else BASE, lw=1.8 if bad else 1.2, r=0.6)
        ax.text(48, yy + 0.1, t, fontsize=10.5, va="center")
        ax.text(81.5, yy + 0.1, r, fontsize=10.5, va="center", ha="right", fontweight="bold" if bad else "normal")
        yy -= 6.6
    ax.text(46, 14.5, "Found by reading the code, not by a failing test.", fontsize=10.5, color=INK2, va="center")
    ax.text(46, 9.8, "Looks fine in casual testing; fails for some values.", fontsize=10.5, color=INK2, va="center")
    # panel 3: three layers
    box(ax, 87, 6, 41, 50, fc=SURFACE, ec=BASE, ls="--", r=1.2, z=1)
    ax.text(89, 52.5, "3  The fix: three layers", fontsize=12, fontweight="bold", va="center")
    layers = [("cap every input", "at 32,767"), ("saturate the distance", "MD tops out at 181.02"),
              ("alarm outright", "if any sub-stage > 4,096 cycles")]
    yy = 44
    for i, (a, b) in enumerate(layers):
        box(ax, 89, yy - 5.4, 37, 9.2, fc=T_FLOOR, ec=FLOOR, lw=1.6, r=0.8)
        ax.text(91, yy + 1.0, f"{i + 1}  {a}", fontsize=11, fontweight="bold", va="center")
        ax.text(91, yy - 2.6, b, fontsize=10.5, color=INK2, va="center")
        if i < 2:
            arrow(ax, (107.5, yy - 5.5), (107.5, yy - 8.2), lw=1.4, ms=10)
        yy -= 12.4
    ax.text(89, 9.6, "Also: the 20-boot window became a one-boot\nrule: k = 0, H = 1.25 x max clean MD = 10.84.",
            fontsize=10, color=INK2, va="center", linespacing=1.3)
    return f


@fig("slide14_stage2_results")
def s15():
    mu, Si, X, k, H = _stage1_model()
    m = np.load(DATA / "model.npz")
    clean = m["MD_nom"]
    att = pd.read_csv(DATA / "attack_boots.csv")
    att = att[att.cp == 2][["sub_a", "sub_b", "sub_c"]].to_numpy(float)
    amd = _md(att, mu, Si)
    fa = pd.read_csv(ROOT / "results" / "false_alarms.csv")[["sub_a", "sub_b", "sub_c"]].to_numpy(float)
    fmd = _md(fa, mu, Si)
    Hfw = 1.25 * clean.max()
    f = plt.figure(figsize=(13, 5.8))
    ax = f.add_axes([0.20, 0.16, 0.48, 0.64])
    rng = np.random.default_rng(1)
    ax.set_xscale("log")
    ax.scatter(clean, 2 + rng.uniform(-0.3, 0.3, len(clean)), s=14, color=BLUE, alpha=0.5, lw=0)
    ax.scatter(amd, 1 + rng.uniform(-0.3, 0.3, len(amd)), s=26, color=ORANGE, alpha=0.85, lw=0)
    ax.scatter(fmd, 3 + rng.uniform(-0.15, 0.15, len(fmd)), s=40, color=BLUE, ec=INK, lw=1.2, zorder=4)
    ax.axvline(Hfw, color=INK, ls="--", lw=1.6)
    ax.text(Hfw * 1.04, 3.62, f"H = {Hfw:.2f}", fontsize=11)
    ax.set_yticks([1, 2, 3])
    ax.set_yticklabels(["50 attack boots\n(sub_b skipped)", "496 clean boots\n(training set)",
                        "the 14 clean boots that\nfalse-alarmed in the\n1000-boot test"], fontsize=11)
    ax.set_ylim(0.4, 3.9)
    ax.set_xlim(0.2, 220)
    ax.set_xlabel("Mahalanobis distance (log scale)")
    ax.grid(True, axis="x")
    ax.grid(False, axis="y")
    ax.set_title("Distance of each boot from normal, frozen 4-checkpoint firmware", loc="left", fontsize=12.5)
    t = f.add_axes([0.72, 0.16, 0.26, 0.64])
    t.axis("off")
    rows = [("1000 attack boots", "1000 detected", True), ("1000 clean boots", "14 false alarms (1.4%)", False),
            ("Largest clean MD", f"{clean.max():.1f}", None), ("Attack MD", f"{amd.min():.1f} to {amd.max():.1f}", None),
            ("Detector code", "1,060 bytes", None), ("Whole firmware", "3,152 bytes", None)]
    y = 0.96
    for a, b, good in rows:
        t.text(0, y, a, fontsize=11, color=INK2, va="center")
        t.text(0, y - 0.065, b, fontsize=13.5, fontweight="bold", va="center")
        y -= 0.165
    f.text(0.04, 0.93, "Stage 2 result: a clean gap between clean and attacked boots, and 14 outliers on the clean side",
           fontsize=14.5, fontweight="bold")
    f.text(0.04, 0.875, "Detection was easy because the fault is large. The 14 false alarms were slow boots, not fast ones (backup slide B1).",
           fontsize=11.5, color=INK2)
    return f


@fig("backupB1_stage2_slow_boots")
def s16():
    mu, Si, X, k, H = _stage1_model()
    fa = pd.read_csv(ROOT / "results" / "false_alarms.csv")
    R = fa[["sub_a", "sub_b", "sub_c"]].to_numpy(float) / mu
    f, ax = plt.subplots(figsize=(13, 5.8))
    f.subplots_adjust(left=0.10, right=0.60, top=0.80, bottom=0.12)
    ax.grid(False)
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list("blu", ["#ffffff", "#cde2fb", "#3987e5", "#104281"])
    ax.imshow(np.clip(R, 0, 6), cmap=cmap, vmin=0.5, vmax=4.0, aspect="auto")
    for i in range(R.shape[0]):
        for j in range(3):
            v = R[i, j]
            ax.text(j, i, f"{v:.1f}x", ha="center", va="center", fontsize=10.5,
                    color="white" if v > 2.4 else INK, fontweight="bold" if v > 1.5 else "normal")
    ax.set_xticks(range(3))
    ax.set_xticklabels(["sub_a", "sub_b", "sub_c"], fontsize=12)
    ax.xaxis.tick_top()
    ax.set_yticks(range(len(fa)))
    ax.set_yticklabels([f"boot {int(b)}" for b in fa.boot], fontsize=10)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.tick_params(length=0)
    f.text(0.10, 0.93, "Stage 2 warning sign: the false alarms are slow boots", fontsize=15, fontweight="bold")
    f.text(0.10, 0.875, "Each cell = that sub-stage's time divided by the training mean. The 14 false-alarming boots of the final run.",
           fontsize=11.5, color=INK2)
    lo = R.min()
    f.text(0.64, 0.76, f"Lowest cell anywhere: {lo:.2f}x", fontsize=13, fontweight="bold", va="top")
    f.text(0.64, 0.70, "The slowest sub-stage of each alarming boot\nis 1.5x to 6.2x its normal time. No cell is\nbelow 0.9x, so none of these boots was fast.",
           fontsize=11.5, linespacing=1.4, va="top")
    f.text(0.64, 0.52, "Likely cause: the host pausing QEMU (not confirmed).", fontsize=11.5, va="top")
    f.text(0.64, 0.45, "Why the training set missed this: it held 0 spiked\nboots in 496. The halting build probably dropped\nits own alarm boots (fits the data, not proven).",
           fontsize=11, color=INK2, linespacing=1.4, va="top")
    f.text(0.64, 0.25, "The detector was only ever shown\na tidy world. Stage 3 tests it on\na messier one.", fontsize=12.5,
           fontweight="bold", linespacing=1.4, va="top")
    return f


# ───────────────────────── Stage 3 figures ─────────────────────────
CP_NAMES = {1: "memory init", 2: "boot mode", 3: "signature\nverify", 4: "decrypt", 5: "integrity", 6: "memory\nsetup", 7: "handoff"}
LOOPS = {1: (200, 200, 200), 2: (150, 150, 150), 3: (500, 300, 200), 4: (250, 250, 250), 5: (300, 300, 300),
         6: (180, 180, 180), 7: (120, 120, 120)}
FAULT_AT = {(1, 1): ["FT-1"], (3, 0): ["FT-4"], (3, 1): ["Attack", "FT-4"], (3, 2): ["FT-2", "FT-5 (+50)"], (7, 0): ["FT-3"]}


@fig("slide15_stage3_flow_faults")
def s17():
    f, ax = canvas(13, 6.6)
    ax.text(1.5, 63.5, "main() in the 8-checkpoint firmware: seven stages, three timed blocks each; orange = blocks the six fault builds change",
            fontsize=13.2, fontweight="bold", va="center")
    ax.text(1.5, 58.5, "pmu_checkpoint(0) starts the clock, then:  stage_*(n)  ->  pmu_checkpoint(n)  ->  check_checkpoint(n)",
            fontsize=11, family=MONO, color=INK2, va="center")
    widths = {3: 25.0}
    x = 1.5
    for cp in range(1, 8):
        w = widths.get(cp, 14.4)
        hot = cp in (1, 3, 7)
        ax.text(x + w / 2, 52.8, f"CP{cp}", fontsize=12.5, fontweight="bold", ha="center", va="center")
        ax.text(x + w / 2, 48.6, CP_NAMES[cp], fontsize=10.2, color=INK2, ha="center", va="center", linespacing=1.15)
        for k, lab in enumerate("abc"):
            y = 36.5 - k * 9.0
            tags = FAULT_AT.get((cp, k), [])
            bad = bool(tags)
            box(ax, x, y, w, 7.4, fc=T_ORANGE if bad else T_BLUE, ec=ORANGE if bad else BLUE, lw=2.4 if bad else 1.2, r=0.7)
            ax.text(x + 1.0, y + 3.7, f"sub_{lab}  {LOOPS[cp][k]}", fontsize=10, va="center", fontweight="bold" if bad else "normal")
            if bad:
                ax.text(x + w - 1.0, y + 3.7, ", ".join(tags), fontsize=10, va="center", ha="right", fontweight="bold")
        x += w + 1.8
    ax.text(1.5, 11.5, "Loop counts are iterations of a volatile busy loop. Orange = a compile-time macro changes this block:",
            fontsize=10.8, color=INK2, va="center")
    items = ["Attack (GLITCH_ATTACK): CP3 sub_b skipped", "FT-1: CP1 sub_b skipped", "FT-2: CP3 sub_c skipped",
             "FT-3: CP7 sub_a skipped", "FT-4: CP3 sub_a and sub_b skipped", "FT-5: CP3 sub_c runs 50 extra iterations (+84%)"]
    for i, t in enumerate(items):
        ax.text(2.0 + (i % 3) * 42, 6.2 - (i // 3) * 4.6, t, fontsize=10.5, va="center")
    return f


def _ds1(name):
    d = pd.read_csv(DATA / f"ds1_{name}.csv").sort_values(["boot_id", "cp"])
    return d


@fig("slide16_stage3_collapse")
def s19():
    f, ax = plt.subplots(figsize=(13, 5.6))
    f.subplots_adjust(left=0.30, right=0.93, top=0.80, bottom=0.14)
    rows = [("Stage 2 result\n(4-checkpoint, 1000 boots)", 100.0, "1000 / 1000", BLUE),
            ("Attack (CP3)", 100 / 300, "1 / 300", MAHA), ("FT-1 (CP1)", 0.0, "0 / 300", MAHA),
            ("FT-2 (CP3)", 0.0, "0 / 300", MAHA), ("FT-3 (CP7)", 100 * 3 / 300, "3 / 300", MAHA),
            ("FT-4 (CP3)", 0.0, "0 / 300", MAHA), ("FT-5 (CP3, extra work)", 0.0, "0 / 300", MAHA)]
    ys = np.arange(len(rows))[::-1]
    ax.grid(False)
    ax.grid(True, axis="x")
    for y, (n, v, lab, c) in zip(ys, rows):
        ax.barh(y, max(v, 0.0), color=c, height=0.62)
        ax.text(max(v, 0.0) + 1.2, y, lab, va="center", fontsize=12, fontweight="bold")
    ax.axhline(5.5, color=BASE, lw=1.2, ls="--")
    ax.set_yticks(ys)
    ax.set_yticklabels([r[0] for r in rows], fontsize=11.5)
    ax.set_xlim(0, 112)
    ax.set_xlabel("faulted boots the Mahalanobis rule flagged (%)")
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    f.text(0.03, 0.93, "Stage 3 result: the same rule, on 8 checkpoints, sees almost nothing", fontsize=15, fontweight="bold")
    f.text(0.03, 0.875, "Same method as Stage 2: one Gaussian per checkpoint, H = 1.25 x largest clean distance. Offline, in-sample, 300 boots per build.",
           fontsize=11.2, color=INK2)
    f.text(0.60, 0.40, "The faults are as large as before:\neach skipped loop removes 78 to 89%\nof that sub-stage's time.\n"
           "The detector simply stopped seeing them.", fontsize=12.5, linespacing=1.45, va="top")
    f.text(0.03, 0.045, "The top bar is a different test (frozen firmware, 1000 boots); the other bars are the 8-checkpoint data.",
           fontsize=10.5, color=INK2)
    return f


@fig("slide17_stage3_why_failed")
def s20():
    d = _ds1("clean")
    c3 = d[d.cp == 3].set_index("boot_id")[["sub_a", "sub_b", "sub_c"]].astype(float)
    X = c3.to_numpy()
    mu, Si = X.mean(0), np.linalg.inv(np.cov(X.T))
    md = _md(X, mu, Si)
    att = _ds1("attack")
    A = att[att.cp == 3].sort_values("boot_id")[["sub_a", "sub_b", "sub_c"]].to_numpy(float)
    amed = float(np.median(_md(A, mu, Si)))
    H = 1.25 * md.max()
    f, (a1, a2) = plt.subplots(1, 2, figsize=(13, 5.8), gridspec_kw={"width_ratios": [1.15, 1]})
    f.subplots_adjust(left=0.06, right=0.97, top=0.78, bottom=0.14, wspace=0.22)
    order = np.argsort(md)[::-1]
    a1.bar(np.arange(300), md[order], color=BLUE, width=1.0, lw=0)
    a1.axhline(amed, color=ORANGE, lw=2.2)
    a1.text(298, amed + 0.5, f"attack boots, median MD = {amed:.1f}", color=INK, ha="right", fontsize=11, fontweight="bold")
    a1.axhline(H, color=INK, ls="--", lw=1.5)
    a1.text(298, H + 0.5, f"threshold H = {H:.1f}", ha="right", fontsize=11)
    ids = c3.index.to_numpy()
    for bid in (280, 203):
        r = int(np.where(ids[order] == bid)[0][0])
        a1.annotate(f"boot {bid}\nMD {md[ids == bid][0]:.1f}", xy=(r, md[ids == bid][0]), xytext=(r + 22, md[ids == bid][0] + (1.0 if bid == 280 else 3.6)),
                    fontsize=10.5, arrowprops=dict(arrowstyle="-", color=INK2))
    n_above = int((md > amed).sum())
    a1.text(150, 8.0, f"{n_above} of 300 clean boots score\nhigher than the attack's median", fontsize=11.5, linespacing=1.35)
    a1.set_xlim(-3, 300)
    a1.set_ylim(0, 22)
    a1.set_xlabel("the 300 clean boots at CP3, sorted by distance")
    a1.set_ylabel("Mahalanobis distance")
    a1.set_title("A harmless spike scores higher than the attack", loc="left", fontsize=12.5)
    a1.set_xticks([])
    # right: direction
    a2.set_xscale("log")
    med = np.median(X, axis=0)
    rng = np.random.default_rng(3)
    rat = (X / med).ravel()
    a2.scatter(rat, rng.uniform(-0.35, 0.35, rat.size) + 1.0, s=10, color=BLUE, alpha=0.4, lw=0)
    ar = (A / med).ravel()
    a2.scatter(ar, rng.uniform(-0.35, 0.35, ar.size) + 0.0, s=10, color=ORANGE, alpha=0.5, lw=0)
    for b, col, lab, dy, ha in ((203, 1, "boot 203, sub_b", 0.42, "right"), (280, 2, "boot 280, sub_c", 0.95, "right")):
        v = c3.loc[b].to_numpy()[col] / med[col]
        a2.scatter([v], [1.0], s=90, color=BLUE, ec=INK, lw=1.2, zorder=5)
        a2.text(v * 1.12, 1.0 + dy, f"{lab}\n{v:.1f}x normal", fontsize=10.5, ha=ha, va="bottom")
    a2.scatter([np.median(A[:, 1] / med[1])], [0.0], s=90, color=ORANGE, ec=INK, lw=1.2, zorder=5)
    a2.text(0.115, -0.62, "attack boots, sub_b\n0.11x normal", fontsize=10.5, ha="center", va="top")
    a2.text(1.9, -0.62, "the attack boots' other two sub-stages\nstay near 1x (up to +24% build effect)", fontsize=10.5, ha="center", va="top", color=INK2)
    a2.axvline(1.0, color=MUTED, lw=1.2, ls=":")
    a2.annotate("", xy=(0.06, 2.35), xytext=(1.0, 2.35), arrowprops=dict(arrowstyle="<|-|>", color=INK2, lw=1.8, shrinkA=0, shrinkB=0))
    a2.annotate("", xy=(1.0, 2.35), xytext=(9.5, 2.35), arrowprops=dict(arrowstyle="<|-|>", color=INK2, lw=1.8, shrinkA=0, shrinkB=0))
    a2.text(0.8, 2.62, "Mahalanobis asks only: how far from the middle?", fontsize=10.8, ha="center", va="bottom")
    a2.set_ylim(-1.5, 3.2)
    a2.set_xlim(0.05, 10)
    a2.set_yticks([0, 1])
    a2.set_yticklabels(["attack\nboots", "clean\nboots"], fontsize=11)
    a2.set_xticks([0.1, 0.2, 0.5, 1, 2, 5])
    a2.set_xticklabels(["0.1x", "0.2x", "0.5x", "1x", "2x", "5x"])
    a2.set_xlabel("sub-stage time / clean median")
    a2.grid(True, axis="x")
    a2.grid(False, axis="y")
    a2.set_title("It cannot tell which side the boot is on", loc="left", fontsize=12.5)
    f.text(0.06, 0.93, "Stage 3: why the detector stopped working", fontsize=15, fontweight="bold")
    f.text(0.06, 0.885, "Fitted on all 300 clean boots at CP3 (in-sample). Spikes also inflate the spread: sub_b std is 286 cycles with them, 113 without.",
           fontsize=11, color=INK2)
    return f


@fig("slide18_stage3_spikes_accumulate")
def s21():
    d = _ds1("clean")
    F3 = ["sub_a", "sub_b", "sub_c"]
    spk = np.zeros((300, 8), bool)
    for cp in range(1, 8):
        x = d[d.cp == cp].sort_values("boot_id")[F3].to_numpy(float)
        spk[:, cp] = (x > 1.5 * np.median(x, axis=0)).any(1)
    cum = [spk[:, 1:k + 1].any(1).sum() / 3.0 for k in range(1, 8)]
    f, (a1, a2) = plt.subplots(1, 2, figsize=(13, 5.8), gridspec_kw={"width_ratios": [1, 1]})
    f.subplots_adjust(left=0.07, right=0.97, top=0.78, bottom=0.14, wspace=0.24)
    ks = np.arange(1, 8)
    a1.plot(ks, cum, color=ORANGE, lw=2.6, marker="o", ms=7)
    for k, v in zip(ks, cum):
        a1.text(k, v + 0.9, f"{v:.0f}%" if v >= 10 else f"{v:.1f}%", ha="center", fontsize=10.5)
    a1.set_ylim(0, 20)
    a1.set_xlim(0.6, 7.4)
    a1.set_xticks(ks)
    a1.set_xticklabels(["CP1", "CP1-2", "CP1-3", "CP1-4", "CP1-5", "CP1-6", "CP1-7"], fontsize=10)
    a1.set_xlabel("checkpoints watched")
    a1.set_ylabel("clean boots with a spike somewhere (%)")
    a1.set_title("Every checkpoint adds its own chance of a spike", loc="left", fontsize=12.5)
    a1.text(0.7, 17.8, "spike = a sub-stage above 1.5x its median", fontsize=10.5, color=INK2)
    # right: rescues
    labs = ["no trimming", "trim training boots\nabove 3x median", "trim training boots\nabove 1.5x median"]
    cp3 = [0.8, 1.8, 2.3]
    all7 = [9.0, 13.0, 15.7]
    x = np.arange(2)
    w = 0.26
    cols = ["#a79df0", "#6250d6", "#3b2e9a"]
    for i in range(3):
        b = a2.bar(x + (i - 1) * (w + 0.03), [cp3[i], all7[i]], width=w, color=cols[i], label=labs[i])
        for xx, v in zip(x + (i - 1) * (w + 0.03), [cp3[i], all7[i]]):
            a2.text(xx, v + 0.4, f"{v:.1f}", ha="center", fontsize=10.5)
    a2.set_xticks(x)
    a2.set_xticklabels(["monitor CP3 only", "monitor CP1 to CP7"], fontsize=11.5)
    a2.set_ylim(0, 20)
    a2.set_ylabel("clean boots falsely alarmed (%)")
    a2.set_title("Trimming spikes: detection returns, false alarms grow", loc="left", fontsize=12.5)
    a2.legend(loc="upper left", fontsize=9.8)
    f.text(0.07, 0.93, "Stage 3: watching more checkpoints multiplies the false alarms", fontsize=15, fontweight="bold")
    f.text(0.07, 0.885, "300 clean boots, per-checkpoint Gaussian, held-out over four splits. Trimming spiked training boots helps detection at CP3, but false alarms stay.",
           fontsize=11, color=INK2)
    return f


# ───────────────────────── Stage 4 figures ─────────────────────────
@fig("slide19_stage4_direction")
def s22():
    d = _ds1("clean")
    c3 = d[d.cp == 3].sort_values("boot_id")["sub_b"].to_numpy(float)
    med = float(np.median(c3))
    a3 = _ds1("attack")
    av = a3[a3.cp == 3]["sub_b"].to_numpy(float)
    f, ax = plt.subplots(figsize=(13, 5.8))
    f.subplots_adjust(left=0.09, right=0.97, top=0.76, bottom=0.17)
    ax.set_xscale("log")
    rng = np.random.default_rng(5)
    ax.scatter(c3 / med, rng.uniform(-0.25, 0.25, c3.size), s=16, color=BLUE, alpha=0.55, lw=0, label="300 clean boots")
    ax.scatter(av / med, rng.uniform(-0.25, 0.25, av.size), s=16, color=ORANGE, alpha=0.6, lw=0, label="300 attack boots (sub_b skipped)")
    ax.axvline(0.45, color=INK, ls="--", lw=2)
    ax.axvspan(0.05, 0.45, color=T_FLOOR, zorder=0)
    ax.text(0.15, 1.78, "floor alarm zone: below 0.45 x median", ha="center", fontsize=11.5, fontweight="bold", color=INK)
    ax.annotate("", xy=(0.052, 1.42), xytext=(0.44, 1.42), arrowprops=dict(arrowstyle="-|>", color=FLOOR, lw=2.6))
    ax.text(0.15, 1.2, "floor asks: is any sub-stage\nsuspiciously short?", fontsize=11.5, ha="center", va="center")
    ax.annotate("", xy=(0.07, 0.58), xytext=(1.0, 0.58), arrowprops=dict(arrowstyle="<|-|>", color=MAHA, lw=2.0, shrinkA=0, shrinkB=0))
    ax.annotate("", xy=(1.0, 0.58), xytext=(8.0, 0.58), arrowprops=dict(arrowstyle="<|-|>", color=MAHA, lw=2.0, shrinkA=0, shrinkB=0))
    ax.text(2.2, 0.78, "Mahalanobis asks: how far from the middle?\n(either side counts)", fontsize=11, ha="center", va="bottom", color=MAHA, fontweight="bold")
    ax.annotate("timing spikes\nonly go up", xy=(4.6, -0.05), xytext=(3.4, -0.80), fontsize=11.5, ha="center",
                arrowprops=dict(arrowstyle="-|>", color=INK2))
    ax.annotate("skipped loops\nonly go down", xy=(0.11, -0.2), xytext=(0.2, -0.80), fontsize=11.5, ha="center",
                arrowprops=dict(arrowstyle="-|>", color=INK2))
    ax.set_ylim(-1.15, 2.0)
    ax.set_xlim(0.05, 10)
    ax.set_yticks([])
    ax.set_xticks([0.1, 0.2, 0.5, 1, 2, 5])
    ax.set_xticklabels(["0.1x", "0.2x", "0.5x", "1x", "2x", "5x"])
    ax.set_xlabel("CP3 sub_b time / clean median")
    ax.grid(True, axis="x")
    ax.grid(False, axis="y")
    ax.legend(loc="upper right", fontsize=10.5)
    f.text(0.09, 0.93, "Stage 4: skipped loops only go down, spikes only go up, so test the down side", fontsize=15, fontweight="bold")
    f.text(0.09, 0.885, "Skipped loops make a stage shorter and spikes make it longer. A one-sided floor ignores the spikes entirely.\nException: FT-5 adds an extra loop (+84%), and only Mahalanobis detects it.",
           fontsize=11.5, color=INK2, linespacing=1.4)
    return f


@fig("slide20_stage4_floor_table")
def s23():
    tab = np.array([[297, 305, 274], [257, 251, 240], [310, 300, 234], [255, 261, 231], [252, 224, 237],
                    [257, 220, 214], [219, 207, 212]])
    f = plt.figure(figsize=(13, 6.4))
    f.text(0.04, 0.95, "The floor rule: 21 numbers and one comparison", fontsize=15, fontweight="bold")
    f.text(0.04, 0.905, "floor = 0.45 x the median of that sub-stage over 300 clean calibration boots (rounded down). Spikes barely move a median.",
           fontsize=11.2, color=INK2)
    f.text(0.04, 0.025, "The floors come from the calibration run. On the fresh validation boots the medians were 1 to 25% higher, so the same floors acted as 0.36 to 0.44 of\n"
           "the fresh median (still inside the usable 0.30 to 0.50).", fontsize=9.5, color=INK2, linespacing=1.4)
    ax = f.add_axes([0.05, 0.12, 0.40, 0.64])
    ax.grid(False)
    cm = matplotlib.colors.LinearSegmentedColormap.from_list("fl", ["#ffffff", "#cfeee1", "#1baf7a"])
    ax.imshow(tab, cmap=cm, vmin=150, vmax=420, aspect="auto")
    for i in range(7):
        for j in range(3):
            ax.text(j, i, str(tab[i, j]), ha="center", va="center", fontsize=13, fontweight="bold" if i == 2 else "normal")
    ax.set_xticks(range(3))
    ax.set_xticklabels(["sub_a", "sub_b", "sub_c"], fontsize=12)
    ax.xaxis.tick_top()
    ax.set_yticks(range(7))
    ax.set_yticklabels([f"CP{i}" for i in range(1, 8)], fontsize=12)
    ax.tick_params(length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.add_patch(plt.Rectangle((-0.5, 1.5), 3, 1, fc="none", ec=ORANGE, lw=3))
    f.text(0.05, 0.835, "FLOOR_TABLE (cycles), src/floor_table.h", fontsize=12.5, fontweight="bold")
    r = f.add_axes([0.50, 0.12, 0.47, 0.72])
    r.axis("off")
    r.set_xlim(0, 10)
    r.set_ylim(0, 10)
    r.add_patch(FancyBboxPatch((0, 6.9), 10, 3.0, boxstyle="round,pad=0,rounding_size=0.15", fc=T_GREY, ec=BASE, lw=1.4))
    r.text(0.3, 9.45, "floor_check(cp, sub[3])   in src/floor_detector.c", fontsize=11.5, fontweight="bold", va="center")
    r.text(0.3, 8.1, "for (i = 0; i < 3; i++)\n    if (sub[i] < FLOOR_TABLE[cp][i])  return 1;\nreturn 0;",
           fontsize=11.5, family=MONO, va="center", linespacing=1.5)
    r.text(0.1, 6.15, "Worked example, CP3", fontsize=12.5, fontweight="bold", va="center")
    rows = [("", "sub_a", "sub_b", "sub_c"), ("clean median (cal. boots)", "690.5", "668", "522"), ("x 0.45, rounded down", "310", "300", "234"),
            ("clean boot", "783", "860", "656"), ("clean, spiked (boot 203)", "764", "3790", "579"), ("attack boot", "583", "93", "542")]
    for i, row in enumerate(rows):
        yy = 5.3 - i * 0.70
        for j, t in enumerate(row):
            hot = i == 5 and j == 2
            r.text([0.1, 5.3, 6.9, 8.5][j], yy, t, fontsize=11, va="center", fontweight="bold" if (i == 0 or hot) else "normal",
                   color=ORANGE if hot else INK)
    r.text(0.1, 0.55, "Attack: 93 < 300, so the floor halts the boot.", fontsize=11, va="center", fontweight="bold")
    r.text(0.1, -0.1, "Spiked boot: every value above its floor, so it continues.", fontsize=11, va="center", fontweight="bold")
    r.text(0.1, -0.85, "Size: code 92 bytes + table 48 bytes = 140 bytes. No multiplies, no square root.", fontsize=11, color=INK2, va="center")
    return f


@fig("slide21_stage4_tiered_flow")
def s24():
    f, ax = canvas(13, 6.8)
    ax.text(1.5, 65, "check_checkpoint(cp) in main.c: what runs after each stage, and what each alarm does", fontsize=13.5, fontweight="bold", va="center")
    cx = 22
    box(ax, 4, 53, 36, 7, "check_checkpoint(cp)", fc=T_GREY, fs=12, weight="bold", family=MONO)
    arrow(ax, (cx, 52.8), (cx, 49.6), lw=1.6, ms=11)
    diamond(ax, cx, 44.5, 36, 9.6, "timer_ok(cp)?\nelapsed rises, < 2^24,\ncovers the 3 sub-stages", fs=10)
    ax.text(cx + 19.5, 46.2, "no", fontsize=11, color=INK2)
    arrow(ax, (cx + 18, 44.5), (50, 44.5), lw=1.6)
    box(ax, 50, 39.6, 36, 9.8, "", fc=T_GREY, ls="--")
    ax.text(52, 46.3, "print TIMER_INVALID,cp", fontsize=11, family=MONO, va="center", fontweight="bold")
    ax.text(52, 42.4, "skip both checks for this CP\n(fails open, untested: ISSUE-019)", fontsize=10, color=INK2, va="center", linespacing=1.3)
    ax.text(cx + 1.5, 36.8, "yes", fontsize=11, color=INK2)
    arrow(ax, (cx, 39.6), (cx, 35.6), lw=1.6, ms=11)
    diamond(ax, cx, 30.5, 36, 9.6, "cp == 3 and\nMahalanobis alarm?", fs=10.5)
    ax.text(cx + 19.5, 32.2, "yes", fontsize=11, color=INK2)
    arrow(ax, (cx + 18, 30.5), (50, 30.5), color=MAHA, lw=2.2)
    box(ax, 50, 25.8, 44, 12.4, "", fc=T_MAHA, ec=MAHA, lw=2.2)
    ax.text(52, 35.6, "report_alarm(\"mahalanobis\", halt = 0)", fontsize=10.8, family=MONO, va="center", fontweight="bold")
    ax.text(52, 32.0, "WARNING ONLY - boot continues", fontsize=10.8, family=MONO, va="center")
    ax.text(52, 28.2, "17 / 300 clean boots false-alarm (5.7%), so halting here\nwould stop about 1 in 18 good boots. Floor check still runs.", fontsize=10, color=INK2, va="center", linespacing=1.3)
    ax.text(cx + 1.5, 22.8, "then (both checks run)", fontsize=11, color=INK2)
    arrow(ax, (cx, 25.6), (cx, 21.8), lw=1.6, ms=11)
    diamond(ax, cx, 17.0, 36, 9.0, "floor_check(cp, f)?\nany sub-stage < floor", fs=10.5)
    ax.text(cx + 19.5, 18.6, "yes", fontsize=11, color=INK2)
    arrow(ax, (cx + 18, 17.0), (50, 17.0), color=ORANGE, lw=2.6)
    box(ax, 50, 9.0, 44, 14.2, "", fc=T_ORANGE, ec=ORANGE, lw=3)
    ax.text(52, 20.6, "report_alarm(\"floor\", halt = 1)", fontsize=10.8, family=MONO, va="center", fontweight="bold")
    ax.text(52, 16.6, "HALTING BOOT - Security violation\nwhile (1) { }", fontsize=10.8, family=MONO, va="center", linespacing=1.3)
    ax.text(52, 11.0, "clean boots: 0 / 300 false alarms (upper bound 1.3%)", fontsize=10, color=INK2, va="center")
    arrow(ax, (cx, 12.4), (cx, 8.0), lw=1.6, ms=11)
    box(ax, 4, 2.0, 36, 6, "next stage", fc=T_GREY, fs=11.5)
    box(ax, 99, 10.4, 29, 40, "", fc=SURFACE, ec=BASE, ls="--", r=1.2, z=1)
    ax.text(100.8, 47.2, "Rule of thumb", fontsize=12, fontweight="bold", va="center")
    ax.text(100.8, 43.6, "A halt must be safe.\n\nThe floor has no measured\nfalse alarms, so it may\nhalt.\n\nMahalanobis has 5.7%,\nso it may only warn.\n\nIt stays because it is\nthe only rule that sees\nFT-5 (extra work).",
            fontsize=10.8, va="top", linespacing=1.3)
    return f


@fig("slide22_stage4_results")
def s25():
    f, (a1, a2) = plt.subplots(1, 2, figsize=(13, 6.0), gridspec_kw={"width_ratios": [1.65, 1]})
    f.subplots_adjust(left=0.13, right=0.97, top=0.78, bottom=0.34, wspace=0.28)
    names = ["Attack (CP3)", "FT-1 (CP1)", "FT-2 (CP3)", "FT-3 (CP7)", "FT-4 (CP3)", "FT-5 (extra work)"]
    floor = [299, 299, 300, 298, 300, 0]
    maha = [300, None, 300, None, 300, 300]
    ys = np.arange(len(names))[::-1]
    a1.grid(False)
    a1.grid(True, axis="x")
    h = 0.34
    for y, fl, ma in zip(ys, floor, maha):
        a1.barh(y + h / 2 + 0.02, fl, height=h, color=FLOOR)
        a1.text(fl + 4, y + h / 2 + 0.02, f"{fl}", va="center", fontsize=11, fontweight="bold")
        if ma is None:
            a1.text(4, y - h / 2 - 0.02, "not watched at this checkpoint", va="center", fontsize=10, color=INK2, style="italic")
        else:
            a1.barh(y - h / 2 - 0.02, ma, height=h, color=MAHA)
            a1.text(ma + 4, y - h / 2 - 0.02, f"{ma}", va="center", fontsize=11, fontweight="bold")
    a1.set_yticks(ys)
    a1.set_yticklabels(names, fontsize=11.5)
    a1.set_xlim(0, 345)
    a1.set_xlabel("faulted boots detected, of 300 fresh boots (firmware's own alarm)")
    a1.spines["left"].set_visible(False)
    a1.tick_params(axis="y", length=0)
    a1.set_title("Faults detected", loc="left", fontsize=12.5)
    a1.legend(handles=[plt.Rectangle((0, 0), 1, 1, color=FLOOR), plt.Rectangle((0, 0), 1, 1, color=MAHA)],
              labels=["floor rule (halts)", "Mahalanobis at CP3 (warns)"], loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=2, fontsize=10.5)
    a2.bar(["floor", "Mahalanobis"], [0, 17], color=[FLOOR, MAHA], width=0.55)
    a2.text(0, 0.8, "0 / 300\n(upper bound 1.3%)", ha="center", fontsize=11, fontweight="bold")
    a2.text(1, 17.8, "17 / 300\n(5.7%)", ha="center", fontsize=11, fontweight="bold")
    a2.set_ylim(0, 24)
    a2.set_ylabel("clean boots falsely alarmed, of 300")
    a2.set_title("False alarms", loc="left", fontsize=12.5)
    f.text(0.04, 0.93, "Stage 4 result: the floor halts on faults and never on clean boots", fontsize=15, fontweight="bold")
    f.text(0.04, 0.885, "300 fresh boots per build, final binary, host load 1.0 to 1.5. The Python mirror agreed with the firmware on all 2,100 boots.",
           fontsize=11.2, color=INK2)
    f.text(0.04, 0.085, "Real halting builds (the boot truly stops), 300 boots each. Clean: 0 halted, 293 completed, 7 completed after a warning.\n"
           "Attack, FT-1, FT-2, FT-4: 300 / 300 halted. FT-3: 299 / 300. FT-5: none halted, all 300 warned.\n"
           "Detected = the firmware itself printed the alarm at the checkpoint the fault hits.",
           fontsize=10.5, color=INK, linespacing=1.55)
    return f


@fig("backupB2_stage4_choosing_f")
def s26():
    f, (a1, a2, a3) = plt.subplots(1, 3, figsize=(13, 5.6), gridspec_kw={"width_ratios": [1, 1, 1]})
    f.subplots_adjust(left=0.06, right=0.98, top=0.74, bottom=0.17, wspace=0.30)
    fs = np.array([0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70])
    miss = [94.2, 36.2, 1.7, 1.7, 0.7, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3]
    untouched = [0, 0, 0, 0, 0, 0, 0, 1.0, 5.1, 7.4, 9.2]
    for a, y, t, yl in ((a1, miss, "Faults missed (worst of five)", 105), (a2, untouched, "Alarms at untouched checkpoints", 11)):
        a.axvspan(0.30, 0.50, color=T_FLOOR, zorder=0)
        a.plot(fs, y, color=FLOOR, lw=2.6, marker="o", ms=5, mfc=SURFACE, mew=1.6)
        a.axvline(0.45, color=INK, ls="--", lw=1.4)
        a.set_ylim(-yl * 0.04, yl)
        a.set_xlabel("floor fraction F")
        a.set_title(t, loc="left", fontsize=12)
    a1.set_ylabel("held-out boots (%)")
    a1.text(0.205, 70, "faults slip\nthrough", fontsize=10.5)
    a2.text(0.205, 5.6, "healthy\ncheckpoints\nalarm above\nF = 0.50", fontsize=10.5)
    a1.text(0.455, 52, "F = 0.45\n(in firmware)", fontsize=10.5)
    red = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90]
    det = [0, 0, 0, 0, 26, 33, 96, 98, 99, 100]
    a3.plot(red, det, color=FLOOR, lw=2.6, marker="o", ms=5, mfc=SURFACE, mew=1.6)
    a3.set_ylim(-4, 105)
    a3.set_xlabel("synthetic cut to CP3 sub_b (%)")
    a3.set_title("Floor detection vs size of the cut", loc="left", fontsize=12)
    a3.text(2, 80, "reliable from\nabout a 60% cut", fontsize=10.5)
    a3.text(2, 56, "misses cuts\nbelow about 35%", fontsize=10.5)
    f.text(0.06, 0.93, "Stage 4: how far can 0.45 be trusted?", fontsize=15, fontweight="bold")
    f.text(0.06, 0.885, "Shaded: usable F, 0.30 to 0.50. F was chosen after seeing the fault data; the fresh boots check the calibration, not the choice of rule.\n"
           "The right-hand cut is synthetic because QEMU cannot do partial skips (ISSUE-012).", fontsize=10.5, color=INK2, linespacing=1.5, va="top")
    return f


# ───────────────────────── Phase 2 and summary ─────────────────────────
@fig("slide24_phase2_plan")
def s27():
    f, ax = canvas(13, 6.2)
    ax.text(1.5, 59, "Phase 2 replaces the stand-ins of Phase 1 one by one", fontsize=14.5, fontweight="bold", va="center")
    ax.text(14, 53.5, "PHASE 1 (done)", fontsize=11.5, fontweight="bold", color=INK2, ha="center")
    ax.text(97, 53.5, "PHASE 2 (planned, about 400 hours)", fontsize=11.5, fontweight="bold", color=BLUE, ha="center")
    rows = [("Platform", "QEMU 8.2.2, mps2-an505", "STM32L552 (Cortex-M33, TrustZone-M)"),
            ("Counter", "SysTick: follows host time", "DWT: cycle, CPI, load-store and fold counters"),
            ("Faults", "compile-time macros, whole loops", "debugger-based injection, optionally voltage glitching"),
            ("Detection", "one rule per checkpoint,\nno fusion", "multi-checkpoint fusion; revisit Stein's Lemma bounds"),
            ("Alarm response", "infinite loop", "TrustZone-M lockout"),
            ("Data", "7 builds x 300 boots", "larger glitched-boot datasets"),
            ("Comparison", "none", "against redundant execution")]
    y = 48.5
    for name, a, b in rows:
        ax.text(1.5, y, name, fontsize=11.5, fontweight="bold", va="center")
        box(ax, 21, y - 2.9, 38, 5.8, a, fc=T_GREY, fs=10.8, r=0.8)
        arrow(ax, (59.6, y), (66.4, y), lw=2.0, ms=14)
        box(ax, 67, y - 2.9, 61, 5.8, b, fc=T_BLUE, ec=BLUE, lw=1.6, fs=10.8, r=0.8)
        y -= 7.4
    return f


@fig("slide23_phase2_questions")
def s28():
    f, ax = canvas(13, 6.8)
    ax.text(1.5, 66, "Every Phase 1 limit becomes a Phase 2 question", fontsize=14.5, fontweight="bold", va="center")
    ax.text(3, 61.2, "WHAT PHASE 1 COULD NOT SHOW", fontsize=10.5, fontweight="bold", color=INK2, va="center")
    ax.text(72, 61.2, "WHAT PHASE 2 WILL MEASURE", fontsize=10.5, fontweight="bold", color=BLUE, va="center")
    rows = [("Faults were compile-time macros", "Does a real glitch change timing like a skipped loop?"),
            ("QEMU timer hides partial skips (ISSUE-012)", "The real severity curve, with DWT counters (*)"),
            ("Floor needs about a 60% cut; blind to extra work (FT-5)", "The mildest fault caught on hardware; a test for longer stages (*)"),
            ("Host timing spikes broke Mahalanobis (ISSUE-013, 017)", "Do spikes exist on silicon? If not, does Mahalanobis recover? (*)"),
            ("Faults only at CP1, CP3, CP7", "Inject at every checkpoint, CP1 to CP7"),
            ("Same code ran up to 28% differently across builds (ISSUE-016)", "Whether recalibrating per build is enough on hardware"),
            ("Per-checkpoint rules only", "Multi-checkpoint fusion that does not multiply false alarms")]
    y = 55.5
    for a, b in rows:
        box(ax, 1.5, y - 3.1, 62, 6.2, a, fc=T_GREY, fs=10.8, r=0.8, ha="left", pad=1.5)
        arrow(ax, (64.0, y), (70.0, y), lw=2.0, ms=14)
        box(ax, 70.5, y - 3.1, 58, 6.2, b, fc=T_BLUE, ec=BLUE, lw=1.6, fs=10.8, r=0.8, ha="left", pad=1.5)
        y -= 7.6
    f.text(0.04, 0.025, "(*) proposed addition: follows from the Phase 1 limits but is not yet written in STATUS.md Section 7. Confirm with your mentor.",
           fontsize=9.5, color=INK2, linespacing=1.4)
    return f


@fig("slide25_summary")
def s29():
    f, ax = canvas(13, 6.2)
    ax.text(1.5, 60, "Phase 1 in four steps: each result and the problem it exposed", fontsize=14.5, fontweight="bold", va="center")
    journey(ax, results=True)
    ax.text(65, 2.4, "Lesson: skipped loops shorten a stage and spikes lengthen it, so a one-sided test wins.\nExtra work (FT-5) is the exception.",
            fontsize=13, fontweight="bold", ha="center", va="center", linespacing=1.4)
    return f


# ==== PART 3 ====

if __name__ == "__main__":
    want = sys.argv[1:]
    for name, fn in FIGS:
        if not want or any(name.startswith(w) for w in want):
            save(fn(), name)
            print("wrote", name)
