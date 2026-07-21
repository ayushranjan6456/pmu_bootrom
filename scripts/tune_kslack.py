# scripts/tune_kslack.py
import numpy as np

mu      = np.load('data/nominal_mu.npy')
cov_inv = np.load('data/nominal_cov_inv.npy')
X_nom   = np.load('data/nominal_X.npy')

diff_nom = X_nom - mu
MD_nom   = np.sqrt(np.einsum('ij,jk,ik->i', diff_nom, cov_inv, diff_nom))
T_99     = np.percentile(MD_nom, 99)

print(f"Nominal MD: mean={MD_nom.mean():.3f}  "
      f"std={MD_nom.std():.3f}  "
      f"median={np.median(MD_nom):.3f}")
print(f"T_99={T_99:.3f}\n")

def mahalanobis(x, mu, cov_inv):
    d = x - mu
    return float(np.sqrt(d @ cov_inv @ d))

def run_trial(k_slack, sev=0.20, n_trials=300):
    detections = 0
    false_alarms = 0
    for _ in range(n_trials):
        # Nominal phase: 10 boots
        stream_nom = X_nom[np.random.choice(len(X_nom), 10)]
        # Glitch phase: 10 boots with sub_b reduced
        idx_g    = np.random.choice(len(X_nom), 10)
        X_g      = X_nom[idx_g].copy().astype(float)
        X_g[:,1] -= sev * mu[1]
        X_g      = np.clip(X_g, 1, None)
        stream   = np.vstack([stream_nom, X_g])

        s = 0.0
        alarm = -1
        for n, x in enumerate(stream):
            md = mahalanobis(x, mu, cov_inv)
            s  = max(0.0, s + md - k_slack)
            if s > T_99:
                alarm = n
                break

        if alarm == -1:
            pass
        elif alarm < 10:
            false_alarms += 1
        else:
            detections += 1

    return detections/n_trials, false_alarms/n_trials

print(f"{'k_slack':>10} | {'Det@20%':>10} | {'FA Rate':>10} | {'Det-FA':>10}")
print("-" * 48)

best_k = None
best_score = -999

for k in [0.5, 0.8, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0, 2.5, 3.0]:
    det, fa = run_trial(k, sev=0.20)
    score   = det - fa          # maximise detection minus false alarm
    marker  = " ←" if score > best_score else ""
    if score > best_score:
        best_score = score
        best_k     = k
    print(f"{k:>10.1f} | {det:>10.3f} | {fa:>10.3f} | {score:>10.3f}{marker}")

print(f"\nBest k_slack = {best_k}  (maximises det_rate - fa_rate)")
print(f"Use this value in cusum_detector.py")