"""
Debug ROC AUC Calculation
==========================
Investigates why AUC = 0.50 despite 99.9% detection rate.
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy import stats

# Load model
m = np.load('data/model.npz')
mu = m['mu']
cov_inv = m['cov_inv']
X_nom = m['X']
K_SLACK = float(m['K_SLACK'])
H_99 = float(m['H_99'])

print("=== MODEL INFO ===")
print(f"Nominal samples: {len(X_nom)}")
print(f"mu = {mu}")
print(f"K_SLACK = {K_SLACK:.4f}")
print(f"H_99 = {H_99:.4f}")

rng = np.random.default_rng(seed=42)

# Simplified CUSUM
def run_cusum_simple(stream, mu, cov_inv, H, k):
    s = 0.0
    for x in stream:
        d = x - mu
        md = float(np.sqrt(d @ cov_inv @ d))
        s = max(0.0, s + md - k)
        if s > H:
            return True, s  # Alarmed
    return False, s  # No alarm

# Generate glitch stream
def make_glitch_stream(severity, n_nom=10, n_glitch=10):
    idx_n = rng.choice(len(X_nom), size=n_nom, replace=True)
    idx_g = rng.choice(len(X_nom), size=n_glitch, replace=True)

    X_clean = X_nom[idx_n].copy()
    X_glitch = X_nom[idx_g].copy().astype(float)

    # Apply glitch to sub_b
    shift = severity * mu[1]
    X_glitch[:, 1] -= shift
    X_glitch = np.clip(X_glitch, 1.0, None)

    return np.vstack([X_clean, X_glitch])

# Test at 20% severity
print("\n=== TESTING AT 20% SEVERITY ===")
SEV = 0.20
N_TRIALS = 100

# Test with different H values
H_values = [1.0, 5.0, 10.0, H_99, 20.0, 30.0]
print(f"\nThreshold sweep with k={K_SLACK:.2f}:")
print(f"{'H':>8} | {'Det Rate':>10} | {'FA Rate':>10}")

for H in H_values:
    det_count = 0
    fa_count = 0

    for _ in range(N_TRIALS):
        # Glitched stream
        stream = make_glitch_stream(SEV, 10, 10)
        alarmed, _ = run_cusum_simple(stream, mu, cov_inv, H, K_SLACK)
        if alarmed:
            det_count += 1

        # Clean stream
        stream_clean = X_nom[rng.choice(len(X_nom), size=20, replace=True)]
        alarmed, _ = run_cusum_simple(stream_clean, mu, cov_inv, H, K_SLACK)
        if alarmed:
            fa_count += 1

    det_rate = det_count / N_TRIALS
    fa_rate = fa_count / N_TRIALS
    print(f"{H:>8.2f} | {det_rate:>10.2%} | {fa_rate:>10.2%}")

# Check if ROC points are being computed correctly
print("\n=== ROC CURVE DIAGNOSTIC ===")
print("Generating ROC data...")

H_sweep = np.linspace(0.1, 40, 50)
roc_det = []
roc_fa = []

N_ROC = 200
for H in H_sweep:
    det_count = 0
    fa_count = 0

    for _ in range(N_ROC):
        # Test on glitch sequences
        stream = make_glitch_stream(SEV, 10, 10)
        alarmed, _ = run_cusum_simple(stream, mu, cov_inv, H, K_SLACK)
        if alarmed:
            det_count += 1

        # Test on clean sequences
        stream_clean = X_nom[rng.choice(len(X_nom), size=20, replace=True)]
        alarmed, _ = run_cusum_simple(stream_clean, mu, cov_inv, H, K_SLACK)
        if alarmed:
            fa_count += 1

    roc_det.append(det_count / N_ROC)
    roc_fa.append(fa_count / N_ROC)

roc_det = np.array(roc_det)
roc_fa = np.array(roc_fa)

print(f"\nROC Data:")
print(f"  Det rate range: [{roc_det.min():.3f}, {roc_det.max():.3f}]")
print(f"  FA rate range: [{roc_fa.min():.3f}, {roc_fa.max():.3f}]")
print(f"  Number of unique FA values: {len(np.unique(roc_fa))}")
print(f"  Number of unique Det values: {len(np.unique(roc_det))}")

# Check if data is monotonic
fa_sorted_idx = np.argsort(roc_fa)
fa_sorted = roc_fa[fa_sorted_idx]
det_sorted = roc_det[fa_sorted_idx]

is_monotonic = all(det_sorted[i] <= det_sorted[i+1] for i in range(len(det_sorted)-1))
print(f"  Detection rate monotonic with FA? {is_monotonic}")

# Compute AUC
auc = np.trapz(det_sorted, fa_sorted)
print(f"\n  AUC (trapezoidal integration): {auc:.4f}")

# Alternative: sort by H instead
h_sorted_idx = np.argsort(H_sweep)
det_by_h = roc_det[h_sorted_idx]
fa_by_h = roc_fa[h_sorted_idx]
auc_alt = np.trapz(det_by_h, fa_by_h)
print(f"  AUC (sorted by H): {auc_alt:.4f}")

# Plot ROC curve
fig, axes = plt.subplots(1, 2, figsize=(14, 6))

# Left: Raw points colored by H
ax = axes[0]
scatter = ax.scatter(roc_fa, roc_det, c=H_sweep, cmap='viridis', alpha=0.7, s=50)
ax.plot([0, 1], [0, 1], 'k--', alpha=0.3, label='Random')
ax.plot(fa_sorted, det_sorted, 'r-', alpha=0.5, lw=2, label=f'ROC (AUC={auc:.3f})')
ax.set_xlabel('False Alarm Rate')
ax.set_ylabel('Detection Rate')
ax.set_title('ROC Curve - Raw Points')
ax.legend()
ax.grid(True, alpha=0.3)
plt.colorbar(scatter, ax=ax, label='Threshold H')

# Right: Sorted curve
ax2 = axes[1]
ax2.plot(fa_sorted, det_sorted, 'b-o', ms=4, alpha=0.6, label=f'Sorted by FA')
ax2.plot([0, 1], [0, 1], 'k--', alpha=0.3, label='Random (AUC=0.5)')
ax2.axhline(0.999, color='green', ls=':', alpha=0.5, label='Target Det=99.9%')
ax2.axvline(0.01, color='red', ls=':', alpha=0.5, label='Target FA=1%')
ax2.set_xlabel('False Alarm Rate')
ax2.set_ylabel('Detection Rate')
ax2.set_title(f'ROC Curve - Sorted (20% severity)')
ax2.legend()
ax2.grid(True, alpha=0.3)
ax2.set_xlim([-0.02, 1.02])
ax2.set_ylim([-0.02, 1.02])

plt.tight_layout()
plt.savefig('results/debug_roc.png', dpi=150)
print(f"\nSaved: results/debug_roc.png")

# Print sample points
print("\nSample ROC points (first 10, sorted by FA):")
for i in range(min(10, len(fa_sorted))):
    h_val = H_sweep[fa_sorted_idx[i]]
    print(f"  H={h_val:>6.2f}  FA={fa_sorted[i]:.3f}  Det={det_sorted[i]:.3f}")
