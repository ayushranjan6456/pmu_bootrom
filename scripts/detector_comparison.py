#!/usr/bin/env python3
"""Offline comparison of detector designs on DS-1 (no firmware changes).

Usage: python3 scripts/detector_comparison.py   (writes results/detector_comparison.txt)

Designs: G0 Gaussian MD (current rule), G1 trimmed Gaussian, L1 floor = f x median,
L2 floor = median - T x robust sigma, F1 one-sided CUSUM-style fusion over sub-stages.
Every number is held-out: the model is fitted on one half of the clean boots and
scored on the other half.
"""
import numpy as np
import pandas as pd

FEAT = ["sub_a", "sub_b", "sub_c"]
CPS = list(range(1, 8))
LOW_TARGET = {"attack": [(3, 1)], "ft1": [(1, 1)], "ft2": [(3, 2)], "ft3": [(7, 0)], "ft4": [(3, 0), (3, 1)]}
F_FRAC, T_Z, K_FUSE = 0.5, 6.0, 2.0
lines = []


def P(s=""):
    print(s)
    lines.append(s)


def load(k):
    df = pd.read_csv(f"data/ds1_{k}.csv").sort_values(["boot_id", "cp"])
    assert (df.cp.values.reshape(-1, 8) == np.arange(8)).all(), k
    a = df[FEAT].to_numpy(float).reshape(-1, 8, 3)
    assert a.shape[0] == 300, k
    return a


D = {k: load(k) for k in ["clean", "attack", "ft1", "ft2", "ft3", "ft4", "ft5"]}


def robust(train):
    med = np.median(train, axis=0)
    sig = 1.4826 * np.median(np.abs(train - med), axis=0)
    return med, np.where(sig == 0, 1.0, sig)


def gfit(train, trim):
    med = np.median(train, axis=0)
    m = {}
    for cp in CPS:
        X = train[:, cp, :]
        if trim:
            X = X[~(X > 3 * med[cp]).any(axis=1)]
        mu, ci = X.mean(0), np.linalg.inv(np.cov(X, rowvar=False))
        d = X - mu
        m[cp] = (mu, ci, 1.25 * np.sqrt(np.einsum("ij,jk,ik->i", d, ci, d)).max())
    return m


def g_alarm(m, a, cps):
    out = np.zeros(len(a), bool)
    for cp in cps:
        mu, ci, H = m[cp]
        d = a[:, cp, :] - mu
        out |= np.sqrt(np.einsum("ij,jk,ik->i", d, ci, d)) > H
    return out


def l_alarm(L, a, cps):
    out = np.zeros(len(a), bool)
    for cp in cps:
        out |= (a[:, cp, :] < L[cp]).any(axis=1)
    return out


def f_score(a, med, sig, cps):
    z = ((med - a) / sig)[:, list(cps), :]
    return np.maximum(0, z - K_FUSE).sum(axis=(1, 2))


def build(train):
    med, sig = robust(train)
    g0, g1 = gfit(train, False), gfit(train, True)
    L1, L2 = F_FRAC * med, med - T_Z * sig
    H = {}

    def f_alarm(a, c):
        key = tuple(c)
        if key not in H:
            H[key] = max(1.25 * f_score(train, med, sig, key).max(), 1e-9)
        return f_score(a, med, sig, key) > H[key]
    return {
        "G0 gaussian, 1.25 x max (current)": lambda a, c: g_alarm(g0, a, c),
        "G1 gaussian, spikes trimmed": lambda a, c: g_alarm(g1, a, c),
        "L1 floor 0.4 x median": lambda a, c: l_alarm(0.4 * med, a, c),
        f"L1 floor {F_FRAC} x median": lambda a, c: l_alarm(L1, a, c),
        f"L2 floor median - {T_Z:g} sigma_r": lambda a, c: l_alarm(L2, a, c),
        f"F1 fusion k={K_FUSE:g}": f_alarm,
    }, med, sig, L1, L2


# ---- 1. per-cell structure of the clean set ----
med, sig = robust(D["clean"])
P("1. CLEAN SET, per sub-stage (300 boots): median, robust sigma, min/med, max/med")
P("   cell      median  sigma_r  min/med  max/med")
for cp in CPS:
    for s in range(3):
        x = D["clean"][:, cp, s]
        P(f"   CP{cp}.{'abc'[s]}   {med[cp, s]:7.0f} {sig[cp, s]:8.1f} {x.min() / med[cp, s]:8.2f} {x.max() / med[cp, s]:8.2f}")

# ---- 2. gap between clean and faulted (in-sample medians) ----
cr = D["clean"] / np.where(med == 0, 1, med)
P()
P(f"2. GAP. Lowest clean ratio x/median over all {len(CPS) * 3} cells x 300 boots: {cr[:, 1:, :].min():.2f}")
zc = ((med - D["clean"]) / sig)[:, 1:, :]
P(f"   Largest clean low-side z = (median - x)/sigma_r: {zc.max():.1f}")
worst_r, worst_z = [], []
for k, cells in LOW_TARGET.items():
    for cp, s in cells:
        r = D[k][:, cp, s] / med[cp, s]
        z = (med[cp, s] - D[k][:, cp, s]) / sig[cp, s]
        worst_r.append(r.max())
        worst_z.append(z.min())
        P(f"   {k:6s} CP{cp}.{'abc'[s]}: ratio median {np.median(r):.2f}, worst boot {r.max():.2f}; z median {np.median(z):.1f}, worst boot {z.min():.1f}")
P(f"   Worst faulted boot ratio {max(worst_r):.2f} exceeds the clean minimum {cr[:, 1:, :].min():.2f}: no single f catches every faulted boot (a host pause can inflate the shrunken sub-stage). Section 3b counts the misses.")
xb = []
for k in LOW_TARGET:
    tgt = {c for c, _ in LOW_TARGET[k]}
    for cp in CPS:
        if cp not in tgt:
            xb.append(((D[k][:, cp, :] / med[cp]).min(), k, cp))
mn = min(xb)
P(f"   Cross-build: lowest ratio of an UNTOUCHED sub-stage in a fault build, against clean-build medians: {mn[0]:.2f} ({mn[1]}, CP{mn[2]})")

# ---- 3. held-out evaluation ----
idx = np.arange(300)
splits = {
    "interleaved A (train odd boots, test even)": (idx[0::2], idx[1::2]),
    "interleaved B (train even, test odd)": (idx[1::2], idx[0::2]),
    "time A (train first 150, test last 150)": (idx[:150], idx[150:]),
    "time B (train last 150, test first 150)": (idx[150:], idx[:150]),
}
P()
P("3. HELD-OUT. FA = clean test boots with an alarm (monitoring CP3 only | CP1-7). Detection at the fault's own checkpoint.")
P("   xbuild = alarms at the UNTOUCHED checkpoints of the 5 low-side fault builds (all 300 boots each).")
agg = {}
for sname, (tr, te) in splits.items():
    methods, *_ = build(D["clean"][tr])
    P(f"   [{sname}]  n_test={len(te)}")
    P(f"   {'method':36s} FAcp3/150 FAall/150  attack/300 ft1 ft2 ft3 ft4  xbuild/1500")
    for mname, fn in methods.items():
        fa3 = int(fn(D["clean"][te], [3]).sum())
        faa = int(fn(D["clean"][te], CPS).sum())
        det = {k: int(fn(D[k], [LOW_TARGET[k][0][0]]).sum()) for k in ["attack", "ft1", "ft2", "ft3", "ft4"]}
        xb_n = sum(int(fn(D[k], [c for c in CPS if c not in {t for t, _ in LOW_TARGET[k]}]).sum()) for k in LOW_TARGET)
        P(f"   {mname:36s} {fa3:8d} {faa:9d} {det['attack']:11d} {det['ft1']:3d} {det['ft2']:3d} {det['ft3']:3d} {det['ft4']:3d} {xb_n:9d}")
        agg.setdefault(mname, []).append((fa3, faa, min(det.values()), xb_n))
P()
P("   Worst case over the 4 splits (max FA /150, min detection /300 over the 5 faults, max xbuild /1500):")
for mname, v in agg.items():
    P(f"   {mname:36s} FA cp3 {max(x[0] for x in v):3d}  FA all {max(x[1] for x in v):3d}  min detection {min(x[2] for x in v):3d}  xbuild {max(x[3] for x in v)}")

# ---- 3b. sweep of the floor fraction f (counts, pooled over a pair of held-out folds) ----
P()
P("3b. FLOOR FRACTION f. Pooled held-out: clean FA out of 300 boots (monitoring CP1-7), xbuild out of 3000, misses out of 600 per fault.")
for pname, pair in [("interleaved pair", ["interleaved A (train odd boots, test even)", "interleaved B (train even, test odd)"]),
                    ("time-ordered pair", ["time A (train first 150, test last 150)", "time B (train last 150, test first 150)"])]:
    P(f"   [{pname}]")
    P("   f      FA/300  xbuild/3000   miss: attack  ft1  ft2  ft3  ft4")
    for f in [0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7]:
        fa = xbn = 0
        miss = {k: 0 for k in LOW_TARGET}
        for sn in pair:
            tr, te = splits[sn]
            L = f * robust(D["clean"][tr])[0]
            fa += int(l_alarm(L, D["clean"][te], CPS).sum())
            for k, cells in LOW_TARGET.items():
                tgt = {t for t, _ in cells}
                miss[k] += int((~l_alarm(L, D[k], [cells[0][0]])).sum())
                xbn += int(l_alarm(L, D[k], [c for c in CPS if c not in tgt]).sum())
        P(f"   {f:4.2f} {fa:7d} {xbn:12d}   {miss['attack']:12d} {miss['ft1']:4d} {miss['ft2']:4d} {miss['ft3']:4d} {miss['ft4']:4d}")

# ---- 4. severity sweep (synthetic, held-out, CP3 only) ----
P()
P("4. SEVERITY SWEEP, synthetic: scale CP3 test boots by (1 - r). Detection at CP3, 4 splits pooled (600 boots per cell).")
rs = [0, .1, .2, .3, .4, .5, .6, .7, .8, .9]
for label, cols in [("sub_b only", [1]), ("all three sub-stages together (the F-01 case)", [0, 1, 2])]:
    P(f"   fault: {label}")
    names = list(build(D["clean"][idx[0::2]])[0].keys())
    P("   r        " + "".join(f"{r:6.0%}" for r in rs))
    res = {n: [] for n in names}
    for r in rs:
        hit = {n: 0 for n in names}
        tot = 0
        for tr, te in splits.values():
            methods, *_ = build(D["clean"][tr])
            a = D["clean"][te].copy()
            a[:, 3, cols] *= (1 - r)
            for n, fn in methods.items():
                hit[n] += int(fn(a, [3]).sum())
            tot += len(te)
        for n in names:
            res[n].append(hit[n] / tot)
    for n in names:
        P(f"   {n[:24]:24s} " + "".join(f"{v:6.0%}" for v in res[n]))

# ---- 5. high side (FT-5 and spikes) ----
P()
P("5. HIGH SIDE. Alarm if CP3 sub_c > g x median (median from the clean build).")
P("   g      FA (clean, CP3.c only)   FA (clean, any of 21 cells)   FT-5 detection")
for g in [1.3, 1.4, 1.5, 1.6, 1.7, 1.8]:
    fa_c = (D["clean"][:, 3, 2] > g * med[3, 2]).mean()
    fa_a = (D["clean"][:, 1:, :] > g * med[1:, :]).any(axis=(1, 2)).mean()
    det = (D["ft5"][:, 3, 2] > g * med[3, 2]).mean()
    P(f"   {g:.1f}   {fa_c:22.1%}   {fa_a:26.1%}   {det:14.0%}")

open("results/detector_comparison.txt", "w").write("\n".join(lines) + "\n")
