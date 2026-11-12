#!/usr/bin/env python3
"""
Calibrate firmware detector from collected data.
Applies proper filtering and generates C code for embedding.
"""

import numpy as np
import pandas as pd
import sys

from fw_model import md_fixed, to_fixed

# Usage: python3 scripts/calibrate_firmware.py [clean_csv] [checkpoint] [attack_csv]
# The 8-checkpoint firmware monitors the Mahalanobis rule at CP3:
#   python3 scripts/calibrate_firmware.py data/cal_clean.csv 3 data/ds1_attack.csv
CSV = sys.argv[1] if len(sys.argv) > 1 else 'data/nominal_boots.csv'
CP = int(sys.argv[2]) if len(sys.argv) > 2 else 2

def filter_outliers_iqr(df, columns, multiplier=2.5):
    """Remove outliers using IQR method."""
    mask = pd.Series([True] * len(df), index=df.index)
    for col in columns:
        Q1 = df[col].quantile(0.25)
        Q3 = df[col].quantile(0.75)
        IQR = Q3 - Q1
        lower = Q1 - multiplier * IQR
        upper = Q3 + multiplier * IQR
        mask &= (df[col] >= lower) & (df[col] <= upper)
    return df[mask]

# Load data
print(f"Loading data from {CSV}...")
df = pd.read_csv(CSV)
print(f"Loaded {len(df)} total rows")

# Get unique boot count
n_boots = df['boot_id'].nunique()
print(f"Unique boots: {n_boots}")

# Focus on the monitored checkpoint (signature verify - primary attack target)
cp2 = df[df['cp'] == CP].copy()
print(f"\nCP{CP} observations: {len(cp2)}")

# Check for corruption markers (like old SysTick bug)
corrupt_high = (cp2['elapsed'] > 100000).sum()
corrupt_sub = (cp2['sub_a'] > 100000).sum()
print(f"Corruption check:")
print(f"  CP2 elapsed > 100k: {corrupt_high}")
print(f"  sub_a > 100k: {corrupt_sub}")

if corrupt_high > 0 or corrupt_sub > 0:
    print("⚠️  Found corrupt boots! Removing...")
    cp2 = cp2[(cp2['elapsed'] <= 100000) & (cp2['sub_a'] <= 100000)]
    print(f"  Remaining: {len(cp2)}")

# Apply IQR outlier filtering
print(f"\nApplying IQR outlier filter (2.5×IQR)...")
n_before = len(cp2)
cp2_clean = filter_outliers_iqr(cp2, ['sub_a', 'sub_b', 'sub_c'])
n_after = len(cp2_clean)
print(f"  Before: {n_before}")
print(f"  After: {n_after}")
print(f"  Removed: {n_before - n_after} ({100*(n_before-n_after)/n_before:.1f}%)")

# Check if we have enough data
if n_after < 100:
    print(f"\n❌ ERROR: Only {n_after} samples after filtering!")
    print("Need at least 100 samples for stable model.")
    print("Collect more data or reduce filtering.")
    sys.exit(1)

# Compute statistics
X = cp2_clean[['sub_a', 'sub_b', 'sub_c']].values
mu = X.mean(axis=0)
sigma = X.std(axis=0)
cv = 100 * sigma / mu

print(f"\n=== CALIBRATED MODEL (n={len(X)}) ===")
print(f"Mean (mu):")
for i, name in enumerate(['sub_a', 'sub_b', 'sub_c']):
    print(f"  {name}: {mu[i]:7.2f}  σ={sigma[i]:6.2f}  CV={cv[i]:5.1f}%")

# Check if noise is acceptable
if cv.max() > 20:
    print(f"\n⚠️  WARNING: High noise! CV={cv.max():.1f}%")
    print("Detection performance may be reduced.")
    print("Consider running on real hardware for <1% CV.")

# Compute covariance
cov = np.cov(X.T)
cov_inv = np.linalg.inv(cov)

print(f"\nCovariance matrix condition number: {np.linalg.cond(cov):.1f}")
print(f"Determinant: {np.linalg.det(cov):.2e}")

# Display correlation
corr = np.corrcoef(X.T)
print(f"\nCorrelation matrix:")
for i in range(3):
    print(f"  [{corr[i,0]:.3f}  {corr[i,1]:.3f}  {corr[i,2]:.3f}]")

# The firmware calls cusum_update once per boot (S starts at 0), so it is a
# one-shot threshold test on Mahalanobis distance. The sequential k/H from
# build_model.py (20-boot windows) do not apply. With k = 0, S = MD and the
# alarm fires when MD > H.
d = X - mu
md_float = np.sqrt(np.einsum('ij,jk,ik->i', d, cov_inv, d))
MARGIN = 1.25
k_slack = 0.0

# The firmware computes the distance in Q16.16 from the constants as printed below. Set H
# from those fixed-point distances, not from the float ones: the float and fixed-point
# distances differ when cov_inv entries are only a few Q16.16 steps (1 step = 1.5e-5).
mu_q = [to_fixed(float(f"{v:.6f}")) for v in mu]
ci_q = [[to_fixed(float(f"{cov_inv[i, j]:.9f}")) for j in range(3)] for i in range(3)]
if np.linalg.eigvalsh(np.array(ci_q, dtype=float)).min() <= 0:
    print("❌ ERROR: the Q16.16 inverse covariance is not positive definite; the firmware would clamp q to 0.")
    sys.exit(1)
md_train = np.array([md_fixed(x, mu_q, ci_q) for x in X]) / 65536.0
H_99 = MARGIN * md_train.max()

step_err = np.abs(np.array(ci_q) / 65536.0 - cov_inv).max() / np.abs(cov_inv).max()
print(f"\nOne-shot threshold (k = 0, H = {MARGIN} x max clean MD, fixed-point distances):")
print(f"  Q16.16 error of cov_inv, largest entry error / largest entry: {step_err:.1%}")
print(f"  clean MD (float):       p50={np.median(md_float):.2f}  max={md_float.max():.2f}")
print(f"  clean MD (fixed-point): p50={np.median(md_train):.2f}  p99={np.percentile(md_train, 99):.2f}  max={md_train.max():.2f}")
print(f"  k_slack = {k_slack:.6f}")
print(f"  H       = {H_99:.6f}")

# Attack separation is checked only against an attack set from the same firmware. The default
# data/attack_boots.csv belongs to the old 4-checkpoint firmware (CP2 monitored); for the
# 8-checkpoint firmware pass a third argument, e.g. data/ds1_attack.csv, or the check is skipped.
ATK_CSV = sys.argv[3] if len(sys.argv) > 3 else ('data/attack_boots.csv' if CP == 2 else None)
try:
    if ATK_CSV is None:
        raise FileNotFoundError
    atk = pd.read_csv(ATK_CSV)
    atk = atk[atk['cp'] == CP]
    md_atk = np.array([md_fixed(x, mu_q, ci_q) for x in atk[['sub_a', 'sub_b', 'sub_c']].values]) / 65536.0
    print(f"  attack MD ({len(md_atk)} boots): min={md_atk.min():.2f}  p50={np.median(md_atk):.2f}")
    print(f"  attack boots above H: {(md_atk > H_99).sum()}/{len(md_atk)}")
    if md_atk.min() <= H_99:
        print("  WARNING: some attack boots fall below H")
except FileNotFoundError:
    print("  (no attack set for this firmware given, attack separation not checked)")

# Generate C code
print("\n" + "="*70)
print("C CODE FOR src/cusum_detector.c")
print("="*70)
print("\nReplace the CUSUM_MODEL initialization with:\n")

print("""const cusum_model_t CUSUM_MODEL = {
    /* Mean vector [sub_a, sub_b, sub_c] - Calibrated from v0.3 data */
    .mu = {""")
print(f"        FLOAT_TO_FIXED({mu[0]:.6f}),    /* mu[0] = sub_a */")
print(f"        FLOAT_TO_FIXED({mu[1]:.6f}),    /* mu[1] = sub_b */")
print(f"        FLOAT_TO_FIXED({mu[2]:.6f}),    /* mu[2] = sub_c */")
print("""    },

    /* Inverse covariance matrix (symmetric) - Calibrated from v0.3 data */
    .cov_inv = {""")
for i in range(3):
    vals = [f"FLOAT_TO_FIXED({cov_inv[i,j]:.9f})" for j in range(3)]
    print(f"        {{{', '.join(vals)}}},")
print("""    },

    /* CUSUM parameters */
""")
print(f"    .k_slack = FLOAT_TO_FIXED({k_slack:.6f}),   /* one-shot test: S = MD */")
print(f"    .H       = FLOAT_TO_FIXED({H_99:.6f}),  /* {MARGIN} x max clean MD */")
print("};")

print("\n" + "="*70)
print(f"✓ Calibration complete! Model ready for embedding.")
print(f"  Training samples: {len(X)}")
print(f"  Mean CV: {cv.mean():.1f}%")
print("="*70)
