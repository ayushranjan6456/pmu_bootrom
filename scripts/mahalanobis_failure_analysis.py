#!/usr/bin/env python3
"""Why the one-shot Mahalanobis rule fails on DS-1 and when it works.

Usage: python3 scripts/mahalanobis_failure_analysis.py   (writes results/mahalanobis_failure_analysis.txt)

Held-out protocol as in detector_comparison.py: four splits (two interleaved, two
time-ordered), fit on one half of the 300 clean boots, score the other half.
"""
import numpy as np
import pandas as pd
from scipy.stats import rankdata
from sklearn.covariance import MinCovDet

F = ["sub_a", "sub_b", "sub_c"]
CPS = list(range(1, 8))
TGT = {"attack": [3], "ft1": [1], "ft2": [3], "ft3": [7], "ft4": [3]}
lines = []


def P(s=""):
    print(s)
    lines.append(s)


def load(k):
    df = pd.read_csv(f"data/ds1_{k}.csv").sort_values(["boot_id", "cp"])
    return df[F].to_numpy(float).reshape(-1, 8, 3)


D = {k: load(k) for k in ["clean", "attack", "ft1", "ft2", "ft3", "ft4"]}
idx = np.arange(300)
SPLITS = {"intA": (idx[0::2], idx[1::2]), "intB": (idx[1::2], idx[0::2]),
          "timeA": (idx[:150], idx[150:]), "timeB": (idx[150:], idx[:150])}


def md_fn(X):
    mu, ci = X.mean(0), np.linalg.inv(np.cov(X, rowvar=False))
    return lambda a: np.sqrt(np.einsum("ij,jk,ik->i", a - mu, ci, a - mu))


def fit(train, trim):
    m = {}
    for cp in CPS:
        X = train[:, cp, :]
        if trim:
            X = X[~(X > trim * np.median(X, 0)).any(axis=1)]
        f = md_fn(X)
        m[cp] = (f, 1.25 * f(X).max())
    return m


def alarm(m, a, cps):
    out = np.zeros(len(a), bool)
    for cp in cps:
        f, H = m[cp]
        out |= f(a[:, cp, :]) > H
    return out


# ---- A. clean spikes ----
med = np.median(D["clean"], axis=0)
P("A. TIMING SPIKES IN THE 8-CP CLEAN SET (300 boots). Boots with any sub-stage above the multiple of its checkpoint median:")
P("   multiple   " + "  ".join(f"CP{c}" for c in CPS) + "   any of CP1-7")
for g in [1.5, 2.0, 3.0]:
    per = [int((D["clean"][:, c, :] > g * med[c]).any(axis=1).sum()) for c in CPS]
    anyc = int((D["clean"][:, 1:, :] > g * med[1:]).any(axis=(1, 2)).sum())
    P(f"   > {g:.1f}x     " + "  ".join(f"{v:3d}" for v in per) + f"   {anyc:3d}")

# ---- B. the threshold, in-sample at CP3 ----
f3 = md_fn(D["clean"][:, 3, :])
c3, a3 = f3(D["clean"][:, 3, :]), f3(D["attack"][:, 3, :])
P()
P("B. THE ONE-SHOT THRESHOLD AT CP3 (Gaussian fitted on all 300 clean boots, in-sample)")
P(f"   largest clean MD {c3.max():.1f}  ->  H = 1.25 x max = {1.25 * c3.max():.1f}")
P(f"   attack MD: median {np.median(a3):.1f}, 90th percentile {np.quantile(a3, .9):.1f}, max {a3.max():.1f}")
sd_all = D["clean"][:, 3, 1].std(ddof=1)
keep = ~(D["clean"][:, 3, :] > 1.5 * med[3]).any(axis=1)
P(f"   CP3 sub_b std: {sd_all:.0f} with all boots, {D['clean'][keep, 3, 1].std(ddof=1):.0f} without the {int((~keep).sum())} boots above 1.5x median")

# ---- C. does the score separate? AUC ----
def auc(neg, pos):
    r = rankdata(np.r_[neg, pos])
    n1, n2 = len(neg), len(pos)
    return (r[n1:].sum() - n2 * (n2 + 1) / 2) / (n1 * n2)


def scorers(X):
    m = np.median(X, 0)
    s = 1.4826 * np.median(np.abs(X - m), 0)
    s = np.where(s == 0, 1.0, s)
    mcd = MinCovDet(random_state=0, support_fraction=0.75).fit(X)
    mu, ci = mcd.location_, np.linalg.inv(mcd.covariance_)
    return {
        "full-cov, robust (MCD), two-sided": lambda a: np.sqrt(np.einsum("ij,jk,ik->i", a - mu, ci, a - mu)),
        "diagonal, median/MAD, two-sided": lambda a: np.sqrt((((a - m) / s) ** 2).sum(1)),
        "diagonal, median/MAD, low side only": lambda a: np.sqrt((np.maximum(0, (m - a) / s) ** 2).sum(1)),
    }


P()
P("C. DOES THE SCORE SEPARATE? AUC = P(faulted boot scores above a held-out clean boot) at the faulted checkpoint, mean of 4 splits (0.5 none, 1.0 perfect)")
names = list(scorers(D["clean"][:, 3, :]).keys())
P(f"   {'fault':7s}" + "".join(f"{n:>38s}" for n in names))
for k, cps in TGT.items():
    cp = cps[0]
    res = {n: [] for n in names}
    for tr, te in SPLITS.values():
        S = scorers(D["clean"][tr][:, cp, :])
        for n, fn in S.items():
            res[n].append(auc(fn(D["clean"][te][:, cp, :]), fn(D[k][:, cp, :])))
    P(f"   {k:7s}" + "".join(f"{np.mean(res[n]):38.3f}" for n in names))

# ---- D. robust fits with a max / quantile threshold ----
P()
P("D. ROBUST FIT, SAME KIND OF THRESHOLD. FA pooled over 4 held-out splits (600 clean test boots); detection = worst split of 300.")
P("   fit                  threshold   FA cp3  FA cp1-7   attack  ft1  ft2  ft3  ft4")
for kind in ["diag", "mcd"]:
    for th in ["1.25max", "q99.9", "q99", "q97.5", "q95"]:
        fa3 = faa = 0
        det = {k: [] for k in TGT}
        for tr, te in SPLITS.values():
            sc = {}
            for cp in CPS:
                X = D["clean"][tr][:, cp, :]
                fn = scorers(X)["diagonal, median/MAD, two-sided" if kind == "diag" else "full-cov, robust (MCD), two-sided"]
                s = fn(X)
                q = {"1.25max": 1.25 * s.max(), "q99.9": np.quantile(s, .999), "q99": np.quantile(s, .99),
                     "q97.5": np.quantile(s, .975), "q95": np.quantile(s, .95)}
                sc[cp] = (fn, q[th])
            fa3 += alarm(sc, D["clean"][te], [3]).sum()
            faa += alarm(sc, D["clean"][te], CPS).sum()
            for k, c in TGT.items():
                det[k].append(int(alarm(sc, D[k], c).sum()))
        P(f"   {('robust diag' if kind == 'diag' else 'robust MCD'):19s}  {th:8s}  {fa3:6d}  {faa:8d}   " + "  ".join(f"{min(v):4d}" for v in det.values()))

# ---- E. trimming the training set ----
P()
P("E. TRIM SPIKED BOOTS FROM TRAINING, THEN H = 1.25 x max training MD (per checkpoint, full-cov Gaussian). Pooled over 4 held-out splits.")
P("   xbuild = boots (out of 6000 = 300 boots x 5 fault builds x 4 splits) with an alarm at any checkpoint the fault does not touch.")
P("   trim T    FA cp3/600  FA cp1-7/600   worst-split detection /300: attack  ft1  ft2  ft3  ft4   xbuild")
for T in [None, 3.0, 2.0, 1.5, 1.35]:
    fa3 = faa = xb = 0
    det = {k: [] for k in TGT}
    for tr, te in SPLITS.values():
        m = fit(D["clean"][tr], T)
        fa3 += alarm(m, D["clean"][te], [3]).sum()
        faa += alarm(m, D["clean"][te], CPS).sum()
        for k, c in TGT.items():
            det[k].append(int(alarm(m, D[k], c).sum()))
            xb += int(alarm(m, D[k], [x for x in CPS if x not in c]).sum())
    P(f"   {('none' if T is None else f'>{T}x median'):12s} {fa3:6d}  {faa:11d}   " + "  ".join(f"{min(v):4d}" for v in det.values()) + f"   {xb:6d}")
P("   per split at T = 1.5 (detection /300 | FA /150 at CP3, CP1-7):")
for sn, (tr, te) in SPLITS.items():
    m = fit(D["clean"][tr], 1.5)
    P(f"   {sn:6s} " + " ".join(f"{k}={int(alarm(m, D[k], c).sum())}" for k, c in TGT.items())
      + f" | {int(alarm(m, D['clean'][te], [3]).sum())}, {int(alarm(m, D['clean'][te], CPS).sum())}")

# ---- F. the frozen 4-CP data ----
old = pd.read_csv("data/nominal_boots.csv")
o2 = old[old.cp == 2]
m2 = o2[F].median().to_numpy()
fa = pd.read_csv("results/false_alarms.csv")
ratio = fa[F].to_numpy(float) / m2
n_big = int((ratio > 1.5).any(axis=1).sum())
P()
P("F. THE FROZEN 4-CP DATA (monitored checkpoint = CP2 of that firmware)")
P(f"   training set: {old.boot_id.nunique()} boots, missing ids {sorted(set(range(1, 501)) - set(old.boot_id.unique()))}")
P(f"   training boots with any CP2 sub-stage > 1.5x median: {int((o2[F].to_numpy() > 1.5 * m2).any(axis=1).sum())} of {len(o2)}")
spk = {c: int((old[old.cp == c][F].to_numpy() > 3 * old[old.cp == c][F].median().to_numpy()).any(axis=1).sum()) for c in (1, 2, 3)}
P(f"   training boots with any sub-stage > 3x median, by checkpoint: CP1 {spk[1]}, CP2 {spk[2]}, CP3 {spk[3]}")
P(f"   1000-boot validation: {len(fa)} false alarms, of which {n_big} have a CP2 sub-stage > 1.5x the training median (so the test boots had spikes at >= {n_big / 10:.1f}%)")
P(f"   chance of 0 spiked boots in {len(o2)} if the spike rate were {n_big / 10:.1f}%: {(1 - n_big / 1000) ** len(o2):.4f}")

open("results/mahalanobis_failure_analysis.txt", "w").write("\n".join(lines) + "\n")
