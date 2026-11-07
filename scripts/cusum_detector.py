"""
cusum_detector.py
=================
Loads the fitted model, simulates glitch attacks at 5 severity levels,
computes detection rate and false alarm rate, and plots ROC curves.

Run after build_model.py.
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os

os.makedirs('results', exist_ok=True)

# ══════════════════════════════════════════════════════════════════════
# 1. LOAD MODEL
# ══════════════════════════════════════════════════════════════════════
m       = np.load('data/model.npz')
mu      = m['mu']
cov_inv = m['cov_inv']
X_nom   = m['X']
K_SLACK = float(m['K_SLACK'])
H_99    = float(m['H_99'])
H_999   = float(m['H_999'])

n = len(X_nom)
print(f"Model loaded: n={n} nominal boots")
print(f"mu      = {np.round(mu, 1)}")
print(f"k_slack = {K_SLACK:.4f}")
print(f"H_99    = {H_99:.4f}")
print(f"H_999   = {H_999:.4f}")

rng = np.random.default_rng(seed=0)

# ══════════════════════════════════════════════════════════════════════
# 2. CORE CUSUM FUNCTION
# ══════════════════════════════════════════════════════════════════════
def run_cusum(stream, mu, cov_inv, H, k):
    """
    Run CUSUM on a feature stream.

    Parameters
    ----------
    stream  : (N, 3) array — one row per boot observation
    mu      : (3,) nominal mean
    cov_inv : (3,3) inverse covariance
    H       : alarm threshold
    k       : slack parameter

    Returns
    -------
    alarm_index : first index where S > H, or -1 if no alarm
    S_trace     : CUSUM statistic at each step
    MD_trace    : Mahalanobis distance at each step
    """
    S_trace  = np.zeros(len(stream))
    MD_trace = np.zeros(len(stream))
    s        = 0.0

    for i, x in enumerate(stream):
        d           = x - mu
        md          = float(np.sqrt(d @ cov_inv @ d))
        s           = max(0.0, s + md - k)
        S_trace[i]  = s
        MD_trace[i] = md

    alarm_idx = next((i for i, v in enumerate(S_trace) if v > H), -1)
    return alarm_idx, S_trace, MD_trace

# ══════════════════════════════════════════════════════════════════════
# 3. GLITCH INJECTION
#
# Models an instruction-skip attack on sub_b (key reduction stage).
# Physical mechanism: voltage glitch reduces CPU Vdd below threshold
# for 1-3 clock cycles, causing the instruction fetch unit to skip
# one or more loop iterations.
# Effect on feature vector: sub_b cycle count decreases by `severity`
# fraction of its nominal mean. sub_a and sub_c are unaffected.
#
# severity=0.20 means sub_b drops by 20% of its mean value (142 cycles).
# ══════════════════════════════════════════════════════════════════════
def make_glitch_stream(X_nom, mu, severity, n_nominal=10, n_glitch=10):
    """
    Build a stream of n_nominal clean boots followed by n_glitch
    glitched boots.
    """
    idx_n   = rng.choice(len(X_nom), size=n_nominal, replace=True)
    idx_g   = rng.choice(len(X_nom), size=n_glitch,  replace=True)

    X_clean  = X_nom[idx_n].copy()
    X_glitch = X_nom[idx_g].copy().astype(float)

    shift              = severity * mu[1]
    noise              = rng.normal(0, shift * 0.05, size=n_glitch)
    X_glitch[:, 1]    -= (shift + noise)
    X_glitch           = np.clip(X_glitch, 1.0, None)

    return np.vstack([X_clean, X_glitch])

# ══════════════════════════════════════════════════════════════════════
# 4. DETECTION RATE vs SEVERITY
# ══════════════════════════════════════════════════════════════════════
N_TRIALS    = 1000
N_NOMINAL   = 10    # boots before glitch starts
N_GLITCH    = 10    # boots after glitch starts
SEVERITIES  = [0.05, 0.10, 0.20, 0.30, 0.50]

print(f"\n=== DETECTION RESULTS (H=H_99={H_99:.3f}, k={K_SLACK:.3f}) ===")
print(f"  Each row: {N_TRIALS} trials, "
      f"{N_NOMINAL} nominal + {N_GLITCH} glitched boots per trial")
print(f"\n{'Severity':>10} | {'Det Rate':>10} | {'FA Rate':>10} | "
      f"{'Missed':>8} | {'Mean Alarm':>12}")

results = {}

for sev in SEVERITIES:
    det = 0
    fa  = 0
    miss = 0
    alarm_lags = []

    for _ in range(N_TRIALS):
        stream    = make_glitch_stream(X_nom, mu, sev, N_NOMINAL, N_GLITCH)
        alarm, _, _ = run_cusum(stream, mu, cov_inv, H_99, K_SLACK)

        if alarm == -1:
            miss += 1
        elif alarm < N_NOMINAL:
            fa += 1
        else:
            det += 1
            alarm_lags.append(alarm - N_NOMINAL)

    det_rate  = det  / N_TRIALS
    fa_rate   = fa   / N_TRIALS
    miss_rate = miss / N_TRIALS
    mean_lag  = np.mean(alarm_lags) if alarm_lags else float('nan')

    results[sev] = dict(det=det_rate, fa=fa_rate,
                        miss=miss_rate, lag=mean_lag)

    print(f"{sev:>10.0%} | {det_rate:>10.3f} | {fa_rate:>10.3f} | "
          f"{miss_rate:>8.3f} | {mean_lag:>12.1f}")

# ══════════════════════════════════════════════════════════════════════
# 5. ROC CURVE
#
# Sweep threshold H from very low (many alarms) to very high (few alarms).
# At each H, compute detection rate and false alarm rate.
# The curve shows the fundamental tradeoff of the detector.
# ══════════════════════════════════════════════════════════════════════
print(f"\nComputing ROC curves (this takes ~30 seconds)...")

H_values    = np.linspace(0.1, H_999 * 1.5, 80)
N_ROC       = 300
SEV_ROC     = 0.20    # ROC at 20% severity

roc_det = []
roc_fa  = []

for H in H_values:
    det_count = 0
    fa_count  = 0
    for _ in range(N_ROC):
        # Test detection rate on attack sequences
        stream_attack = make_glitch_stream(X_nom, mu, SEV_ROC,
                                           N_NOMINAL, N_GLITCH)
        alarm, _, _ = run_cusum(stream_attack, mu, cov_inv, H, K_SLACK)
        if alarm != -1:  # Any alarm on attack sequence = detection
            det_count += 1

        # Test false alarm rate on pure nominal sequences
        stream_nominal = make_glitch_stream(X_nom, mu, 0.0,
                                            N_NOMINAL + N_GLITCH, 0)
        alarm_nom, _, _ = run_cusum(stream_nominal, mu, cov_inv, H, K_SLACK)
        if alarm_nom != -1:  # Any alarm on nominal sequence = false alarm
            fa_count += 1

    roc_det.append(det_count / N_ROC)
    roc_fa.append(fa_count  / N_ROC)

roc_det = np.array(roc_det)
roc_fa  = np.array(roc_fa)

# Sort by FA rate for proper AUC calculation
sort_idx = np.argsort(roc_fa)
roc_fa_s = roc_fa[sort_idx]
roc_det_s = roc_det[sort_idx]
auc = np.trapezoid(roc_det_s, roc_fa_s)
print(f"AUC (severity={SEV_ROC:.0%}) = {auc:.4f}")

# ══════════════════════════════════════════════════════════════════════
# 6. PLOTS
# ══════════════════════════════════════════════════════════════════════

# ── Example CUSUM trace ───────────────────────────────────────────────
stream_ex          = make_glitch_stream(X_nom, mu, 0.20, N_NOMINAL, N_GLITCH)
alarm_ex, S_ex, MD_ex = run_cusum(stream_ex, mu, cov_inv, H_99, K_SLACK)

fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle('CUSUM Fault Injection Detector — Results', fontsize=13)

# Plot 1: MD trace
ax = axes[0, 0]
ax.plot(MD_ex, 'b-o', ms=4, alpha=0.8, label='MD score')
ax.axvline(N_NOMINAL - 0.5, color='red', ls='--',
           lw=2, label='Glitch starts')
ax.axhline(K_SLACK, color='gray', ls=':', label=f'k_slack={K_SLACK:.2f}')
ax.set_title('Mahalanobis Distance per Boot (20% severity)')
ax.set_xlabel('Boot index in sequence')
ax.set_ylabel('MD')
ax.legend(fontsize=9); ax.grid(True, alpha=0.3)

# Plot 2: CUSUM S trace
ax2 = axes[0, 1]
ax2.plot(S_ex, color='purple', lw=2, label='CUSUM statistic S')
ax2.axvline(N_NOMINAL - 0.5, color='red', ls='--', lw=2,
            label='Glitch starts')
ax2.axhline(H_99,  color='orange', ls='--', label=f'H_99={H_99:.2f}')
ax2.axhline(H_999, color='red',    ls=':',  label=f'H_999={H_999:.2f}',
            alpha=0.6)
if alarm_ex != -1:
    ax2.axvline(alarm_ex, color='green', ls='-', lw=2,
                label=f'ALARM at boot {alarm_ex}')
ax2.set_title('CUSUM Statistic S')
ax2.set_xlabel('Boot index in sequence')
ax2.set_ylabel('S')
ax2.legend(fontsize=9); ax2.grid(True, alpha=0.3)

# Plot 3: Detection rate vs severity
ax3 = axes[1, 0]
sevs = list(results.keys())
dets = [results[s]['det'] for s in sevs]
fas  = [results[s]['fa']  for s in sevs]
ax3.plot([s * 100 for s in sevs], dets,
         'g-o', lw=2, ms=7, label='Detection Rate')
ax3.plot([s * 100 for s in sevs], fas,
         'r-s', lw=2, ms=7, label='False Alarm Rate')
ax3.axhline(0.01, color='gray', ls=':', alpha=0.7, label='Target FA=1%')
ax3.set_title('Detection Rate vs Glitch Severity')
ax3.set_xlabel('Glitch Severity (% reduction in sub_b cycles)')
ax3.set_ylabel('Rate')
ax3.set_ylim([-0.05, 1.05])
ax3.legend(fontsize=9); ax3.grid(True, alpha=0.3)

# Plot 4: ROC curve
ax4 = axes[1, 1]
ax4.plot(roc_fa_s, roc_det_s, 'b-', lw=2.5,
         label=f'CUSUM detector (AUC={auc:.3f})')
ax4.plot([0, 1], [0, 1], 'k--', alpha=0.4, label='Random (AUC=0.5)')
ax4.axvline(0.01, color='gray', ls=':', alpha=0.7, label='FA=1% operating point')
ax4.set_title(f'ROC Curve — 20% Glitch Severity')
ax4.set_xlabel('False Alarm Rate')
ax4.set_ylabel('Detection Rate')
ax4.set_xlim([-0.02, 1.02])
ax4.set_ylim([-0.02, 1.02])
ax4.legend(fontsize=9); ax4.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('results/cusum_results.png', dpi=150, bbox_inches='tight')
print("Saved: results/cusum_results.png")

# ── Detection rate vs severity (clean summary) ────────────────────────
print(f"\n=== FINAL SUMMARY ===")
print(f"{'Severity':>10} | {'Det Rate':>10} | {'FA Rate':>10} | "
      f"{'Status':>20}")
for sev in SEVERITIES:
    r   = results[sev]
    ok  = '✓ GOOD' if r['det'] > 0.8 and r['fa'] < 0.05 else \
          '~ OK'   if r['det'] > 0.5                      else \
          '✗ WEAK'
    print(f"{sev:>10.0%} | {r['det']:>10.3f} | "
          f"{r['fa']:>10.3f} | {ok:>20}")
print(f"\nROC AUC @ 20% severity = {abs(auc):.4f}")