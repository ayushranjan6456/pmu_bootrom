"""
baseline_comparison.py
======================
Why Mahalanobis and not a simple threshold on sub_b?

Compares, on the same CP2 data, one-shot detectors that each see one boot:
  1. Mahalanobis distance on [sub_a, sub_b, sub_c]  (what the firmware uses)
  2. sub_b alone, low side   (alarm if sub_b < T; assumes a glitch shortens it)
  3. sub_b alone, two-sided  (alarm if |sub_b - mean| / std > T)

All three are calibrated identically: threshold = 99th percentile of the
clean training scores (1% target false alarm rate). Clean data is split 50/50
into train/test, repeated with different seeds; false alarms are measured on
the held-out half. Detection is measured on the 50 real glitched boots and on
synthetic sub_b reductions applied to the held-out clean boots.

Needs: data/nominal_boots.csv, data/attack_boots.csv
"""

import numpy as np
import pandas as pd

REPEATS = 200
TARGET_FA = 0.01
SEVERITIES = [0.05, 0.10, 0.20, 0.30, 0.50, 0.85]

clean = pd.read_csv('data/nominal_boots.csv').query('cp == 2')
atk = pd.read_csv('data/attack_boots.csv').query('cp == 2')
cols = ['sub_a', 'sub_b', 'sub_c']
Xc = clean[cols].values.astype(float)
Xa = atk[cols].values.astype(float)


def fit(X):
    mu = X.mean(axis=0)
    return mu, X.std(axis=0), np.linalg.inv(np.cov(X.T))


def scores(X, mu, sd, ci):
    d = X - mu
    return {
        'Mahalanobis (3 features)': np.sqrt(np.einsum('ij,jk,ik->i', d, ci, d)),
        'sub_b low-side': -X[:, 1],
        'sub_b two-sided': np.abs(d[:, 1]) / sd[1],
    }


def glitch(X, mu, sev, rng):
    G = X.copy()
    shift = sev * mu[1]
    G[:, 1] -= shift + rng.normal(0, 0.05 * shift, size=len(G))
    return np.clip(G, 1.0, None)


names = list(scores(Xc[:5], *fit(Xc)).keys())
fa = {n: [] for n in names}
real = {n: [] for n in names}
syn = {n: {s: [] for s in SEVERITIES} for n in names}

rng = np.random.default_rng(0)
for _ in range(REPEATS):
    perm = rng.permutation(len(Xc))
    train, test = Xc[perm[:len(Xc) // 2]], Xc[perm[len(Xc) // 2:]]
    mu, sd, ci = fit(train)
    thr = {n: np.quantile(v, 1 - TARGET_FA) for n, v in scores(train, mu, sd, ci).items()}

    for n, v in scores(test, mu, sd, ci).items():
        fa[n].append(np.mean(v > thr[n]))
    for n, v in scores(Xa, mu, sd, ci).items():
        real[n].append(np.mean(v > thr[n]))
    for s in SEVERITIES:
        for n, v in scores(glitch(test, mu, s, rng), mu, sd, ci).items():
            syn[n][s].append(np.mean(v > thr[n]))

print(f"CP2, {len(Xc)} clean boots (split 50/50, {REPEATS} repeats), {len(Xa)} real glitched boots")
print(f"Threshold = {100*(1-TARGET_FA):.0f}th percentile of clean training scores (target FA {TARGET_FA:.0%})\n")

w = max(len(n) for n in names)
hdr = f"{'Detector':<{w}} | {'FA (held-out)':>13} | {'Real glitch':>11} | " + " ".join(f"{int(s*100):>3}%".rjust(6) for s in SEVERITIES[:-1])
print(hdr)
print('-' * len(hdr))
for n in names:
    row = f"{n:<{w}} | {100*np.mean(fa[n]):>12.2f}% | {100*np.mean(real[n]):>10.1f}% | "
    row += " ".join(f"{100*np.mean(syn[n][s]):>5.1f}%" for s in SEVERITIES[:-1])
    print(row)
print("\nColumns 5%..50%: synthetic sub_b reduction applied to held-out clean boots (detection rate).")
print(f"Real glitch removes the whole sub_b loop (~{100*(1-Xa[:,1].mean()/Xc[:,1].mean()):.0f}% reduction).")
