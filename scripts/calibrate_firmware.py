#!/usr/bin/env python3
"""
Calibrate firmware detector from collected data.
Applies proper filtering and generates C code for embedding.
"""

import numpy as np
import pandas as pd
import sys

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
print("Loading data from data/nominal_boots.csv...")
df = pd.read_csv('data/nominal_boots.csv')
print(f"Loaded {len(df)} total rows")

# Get unique boot count
n_boots = df['boot_id'].nunique()
print(f"Unique boots: {n_boots}")

# Focus on CP2 (signature verify - primary attack target)
cp2 = df[df['cp'] == 2].copy()
print(f"\nCP2 observations: {len(cp2)}")

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

# Use existing CUSUM parameters (from Python model)
# These were calibrated on similar data
k_slack = 1.527768
H_99 = 13.844297

print(f"\nCUSUM parameters (from prior calibration):")
print(f"  k_slack = {k_slack:.6f}")
print(f"  H_99    = {H_99:.6f}")

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
    vals = [f"FLOAT_TO_FIXED({cov_inv[i,j]:.6f})" for j in range(3)]
    print(f"        {{{', '.join(vals)}}},")
print("""    },

    /* CUSUM parameters */
    .k_slack = FLOAT_TO_FIXED(1.527768),   /* Slack reduces noise false alarms */
    .H       = FLOAT_TO_FIXED(13.844297),  /* H_99: 1% false alarm rate */
};""")

print("\n" + "="*70)
print(f"✓ Calibration complete! Model ready for embedding.")
print(f"  Training samples: {len(X)}")
print(f"  Mean CV: {cv.mean():.1f}%")
print("="*70)
