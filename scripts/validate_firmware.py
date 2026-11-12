#!/usr/bin/env python3
"""Summarise a firmware validation collection and check the firmware against its Python mirror.

Usage: python3 scripts/validate_firmware.py [PREFIX]      (default val; writes results/validation_8cp.txt)
Reads data/<PREFIX>_<variant>.csv (telemetry) and data/<PREFIX>_<variant>_boots.csv (the alarms the
firmware itself printed, host load per boot), written by scripts/collect_fault_types.sh.

For every boot the script recomputes what the firmware should decide from the printed telemetry
(floor table from src/floor_table.h, Mahalanobis constants from src/cusum_detector.c, timer guard as
in main.c) and counts disagreements with what the firmware actually printed.
"""
import math
import re
import sys

import numpy as np
import pandas as pd

from fw_model import cusum_alarm, to_fixed

PREFIX = sys.argv[1] if len(sys.argv) > 1 else "val"
OWN_CP = {"attack": 3, "ft1": 1, "ft2": 3, "ft3": 7, "ft4": 3, "ft5": 3}
VARIANTS = ["clean", "attack", "ft1", "ft2", "ft3", "ft4", "ft5"]
lines = []


def P(s=""):
    print(s)
    lines.append(s)


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def frac(k, n):
    lo, hi = wilson(k, n)
    return f"{k:3d}/{n} = {100 * k / n:5.1f}%  (95% CI {100 * lo:.1f}-{100 * hi:.1f}%)"


# ---- firmware constants, parsed from the sources that were compiled ----
floor = np.array([[int(v) for v in re.findall(r"\d+", row.split("/*")[0])] for row in open("src/floor_table.h") if row.strip().startswith("{")])
assert floor.shape == (8, 3), floor.shape
src = open("src/cusum_detector.c").read()
nums = [float(x) for x in re.findall(r"FLOAT_TO_FIXED\((-?[\d.]+)\)", src)]
mu_q = [to_fixed(v) for v in nums[0:3]]
ci_q = [[to_fixed(v) for v in nums[3 + 3 * i: 6 + 3 * i]] for i in range(3)]
H_q = to_fixed(nums[13])
assert len(nums) == 14, len(nums)


def timer_ok(E, S, cp):
    if E[cp] >= 0xFFFFFF or E[cp] <= E[cp - 1]:
        return False
    step = E[cp] - E[cp - 1]
    return max(S[cp]) <= step and sum(S[cp]) <= step


def predict(E, S):
    """Set of 'detector@cp' strings and set of invalid checkpoints the firmware should report."""
    alarms, invalid = set(), set()
    for cp in range(1, 8):
        if not timer_ok(E, S, cp):
            invalid.add(cp)
            continue
        sub = [int(v) for v in S[cp]]
        if cp == 3 and cusum_alarm(sub, mu_q, ci_q, H_q):
            alarms.add("mahalanobis@3")
        if any(sub[i] < floor[cp][i] for i in range(3)):
            alarms.add(f"floor@{cp}")
    return alarms, invalid


data = {}
for v in VARIANTS:
    t = pd.read_csv(f"data/{PREFIX}_{v}.csv")
    b = pd.read_csv(f"data/{PREFIX}_{v}_boots.csv", keep_default_na=False)
    boots = sorted(t.boot_id.unique())
    rows = {}
    for bid, g in t.groupby("boot_id"):
        g = g.sort_values("cp")
        rows[bid] = (g.elapsed.to_numpy(np.int64), g[["sub_a", "sub_b", "sub_c"]].to_numpy(np.int64))
    b = b.set_index("boot_id")
    data[v] = (boots, rows, b)

P(f"FIRMWARE VALIDATION, prefix '{PREFIX}'")
P(f"Floor table (src/floor_table.h), cycles per CP x [a b c]: {floor[1:].tolist()}")
P(f"Mahalanobis: H = {H_q / 65536:.3f}; ceiling 4096 cycles per sub-stage at CP3")
P()
P("0. HOST LOAD AND TIMER VALIDITY")
for v in VARIANTS:
    boots, rows, b = data[v]
    ld = b.loc[boots, "loadavg"].astype(float)
    inv = sum(1 for i in boots if str(b.loc[i, "timer_invalid"]) != "")
    P(f"   {v:7s} boots {len(boots)}/300  load avg per boot: median {ld.median():.2f} max {ld.max():.2f} | boots above 2.0: {(ld > 2).sum()} | boots with a rejected timer reading: {inv}")

P()
P("1. FIRMWARE vs PYTHON MIRROR (do the compiled firmware and the offline rule agree on every boot?)")
tot = mism = 0
for v in VARIANTS:
    boots, rows, b = data[v]
    bad = []
    for i in boots:
        E, S = rows[i]
        a, inv = predict(E, S)
        fa = {x for x in str(b.loc[i, "alarms"]).split(";") if x}
        fi = {int(x) for x in str(b.loc[i, "timer_invalid"]).split(";") if x}
        if a != fa or inv != fi:
            bad.append((i, sorted(a), sorted(fa), sorted(inv), sorted(fi)))
    tot += len(boots)
    mism += len(bad)
    P(f"   {v:7s} disagreements: {len(bad)} of {len(boots)}")
    for x in bad[:5]:
        P(f"      boot {x[0]}: python alarms {x[1]} firmware alarms {x[2]} | python invalid {x[3]} firmware invalid {x[4]}")
P(f"   total: {mism} of {tot}")

P()
P("2. CLEAN BOOTS (false alarms; a boot with any alarm would halt)")
boots, rows, b = data["clean"]
n = len(boots)
anyd = {"floor": 0, "mahalanobis": 0, "any": 0}
for i in boots:
    al = {x.split("@")[0] for x in str(b.loc[i, "alarms"]).split(";") if x}
    for k in ("floor", "mahalanobis"):
        anyd[k] += k in al
    anyd["any"] += bool(al)
P(f"   floor rule       : {frac(anyd['floor'], n)}")
P(f"   Mahalanobis (CP3): {frac(anyd['mahalanobis'], n)}")
P(f"   either (boot halts): {frac(anyd['any'], n)}")
inv_n = sum(1 for i in boots if str(b.loc[i, "timer_invalid"]) != "")
P(f"   boots with a rejected timer reading (checks skipped, no alarm): {inv_n}")

P()
P("3. FAULT BUILDS. detected = firmware printed an alarm at the checkpoint the fault hits.")
P("   'any' = alarm at any checkpoint (the boot would halt). 'elsewhere' = alarms only at checkpoints the fault does not touch.")
P(f"   {'build':7s} {'floor, own CP':44s} {'Mahalanobis, own CP':44s} any alarm")
for v in VARIANTS[1:]:
    boots, rows, b = data[v]
    n = len(boots)
    cp = OWN_CP[v]
    cnt = {"floor": 0, "mah": 0, "any": 0, "else": 0}
    for i in boots:
        al = [x for x in str(b.loc[i, "alarms"]).split(";") if x]
        cnt["floor"] += f"floor@{cp}" in al
        cnt["mah"] += f"mahalanobis@{cp}" in al
        cnt["any"] += bool(al)
        cnt["else"] += any(x.split("@")[1] != str(cp) for x in al)
    P(f"   {v:7s} {frac(cnt['floor'], n):44s} {frac(cnt['mah'], n):44s} {cnt['any']}/{n}  (alarms at other checkpoints in {cnt['else']} boots)")

P()
P("4. NOT COVERED: ft5 adds work (+84% at CP3 sub_c); a lower bound cannot see it by design.")
open("results/validation_8cp.txt", "w").write("\n".join(lines) + "\n")
