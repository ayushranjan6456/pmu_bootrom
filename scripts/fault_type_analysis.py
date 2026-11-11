#!/usr/bin/env python3
"""
Fault Type Coverage Analysis

Analyzes detection rates across multiple fault types and checkpoints.
Generates bar charts with confidence intervals showing detector performance
per fault type and per checkpoint.

Usage:
    python scripts/fault_type_analysis.py data/ds1_*.csv

Output:
    results/fault_type_coverage.png
    results/fault_type_summary.txt
"""

import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import stats
from pathlib import Path

# Import the model and detector
sys.path.insert(0, str(Path(__file__).parent))
from cusum_detector import mahalanobis_distance

def load_model(model_path='data/model.npz'):
    """Load the fitted Gaussian model for each checkpoint."""
    model = np.load(model_path)
    return {
        'mu': model['mu'],
        'cov_inv': model['cov_inv'],
        'H': model['H_999']  # Use 99.9th percentile threshold
    }

def load_fault_data(file_pattern):
    """Load all fault type datasets."""
    files = sorted(Path('data').glob(file_pattern))
    datasets = {}

    for f in files:
        # Extract fault type from filename: ds1_ft1.csv -> ft1
        label = f.stem.split('_')[-1]
        df = pd.read_csv(f)
        datasets[label] = df

    return datasets

def compute_detection_rate(features, model, threshold_multiplier=1.0):
    """
    Compute detection rate for a set of feature vectors.

    Args:
        features: Nx3 array of [sub_a, sub_b, sub_c]
        model: dict with 'mu', 'cov_inv'
        threshold_multiplier: scale H for sensitivity analysis

    Returns:
        detection_rate: fraction of boots flagged as attacks
        distances: array of Mahalanobis distances
    """
    H = model['H'] * threshold_multiplier
    distances = []

    for feat in features:
        md = mahalanobis_distance(feat, model['mu'], model['cov_inv'])
        distances.append(md)

    distances = np.array(distances)
    detected = distances > H

    return np.mean(detected), distances

def wilson_confidence_interval(successes, trials, confidence=0.95):
    """Wilson score confidence interval for binomial proportion."""
    if trials == 0:
        return 0, 0, 0

    p_hat = successes / trials
    z = stats.norm.ppf(1 - (1 - confidence) / 2)

    denominator = 1 + z**2 / trials
    center = (p_hat + z**2 / (2 * trials)) / denominator
    margin = z * np.sqrt((p_hat * (1 - p_hat) + z**2 / (4 * trials)) / trials) / denominator

    return center, max(0, center - margin), min(1, center + margin)

def analyze_fault_types(datasets, model, checkpoint=3):
    """
    Analyze detection performance across fault types.

    Args:
        datasets: dict mapping label -> DataFrame
        model: fitted Gaussian model
        checkpoint: which checkpoint to analyze (default CP3, signature verify)

    Returns:
        results: DataFrame with detection rates and confidence intervals
    """
    results = []

    for label, df in datasets.items():
        if label == 'clean':
            continue  # Skip clean baseline

        # Filter to target checkpoint
        cp_data = df[df['cp'] == checkpoint]

        if len(cp_data) == 0:
            continue

        # Extract features per boot
        features = cp_data[['sub_a', 'sub_b', 'sub_c']].values
        n_boots = len(features)

        # Compute detection rate
        det_rate, distances = compute_detection_rate(features, model)
        n_detected = int(det_rate * n_boots)

        # Confidence interval
        center, ci_low, ci_high = wilson_confidence_interval(n_detected, n_boots)

        results.append({
            'fault_type': label.upper(),
            'n_boots': n_boots,
            'n_detected': n_detected,
            'detection_rate': center,
            'ci_low': ci_low,
            'ci_high': ci_high,
            'mean_md': np.mean(distances),
            'median_md': np.median(distances),
            'max_md': np.max(distances)
        })

    return pd.DataFrame(results)

def plot_fault_type_coverage(results, output_path='results/fault_type_coverage.png'):
    """Generate bar chart with error bars."""
    fig, ax = plt.subplots(figsize=(10, 6))

    x = np.arange(len(results))
    heights = results['detection_rate'].values
    errors_low = heights - results['ci_low'].values
    errors_high = results['ci_high'].values - heights

    bars = ax.bar(x, heights, yerr=[errors_low, errors_high],
                   capsize=5, color='steelblue', alpha=0.8,
                   error_kw={'linewidth': 2})

    # Add count labels on bars
    for i, (bar, row) in enumerate(zip(bars, results.itertuples())):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, height + 0.03,
                f'{row.n_detected}/{row.n_boots}',
                ha='center', va='bottom', fontsize=9)

    ax.set_xlabel('Fault Type', fontsize=12, fontweight='bold')
    ax.set_ylabel('Detection Rate', fontsize=12, fontweight='bold')
    ax.set_title('Detector Coverage Across Fault Types (CP3, H=10.84)',
                 fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(results['fault_type'])
    ax.set_ylim(0, 1.1)
    ax.axhline(0.95, color='green', linestyle='--', alpha=0.5, label='95% target')
    ax.axhline(0.05, color='red', linestyle='--', alpha=0.5, label='5% FA limit')
    ax.legend()
    ax.grid(axis='y', alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    print(f"Saved: {output_path}")

def main():
    # Load model (trained on 4-checkpoint data, use CP3 params for 8-checkpoint)
    model_path = 'data/model.npz'
    if not Path(model_path).exists():
        print(f"Error: Model file not found: {model_path}")
        print("Run: python scripts/build_model.py first")
        return 1

    model = load_model(model_path)

    # Load fault type datasets
    datasets = load_fault_data('ds1_*.csv')
    if not datasets:
        print("Error: No DS-1 datasets found in data/")
        return 1

    print(f"Loaded {len(datasets)} datasets:")
    for label, df in datasets.items():
        n_boots = len(df[df['cp'] == 0])  # Count unique boot_ids via CP0
        print(f"  {label:10s}: {n_boots:3d} boots")
    print()

    # Analyze at CP3 (signature verification, primary target)
    results = analyze_fault_types(datasets, model, checkpoint=3)

    # Print summary
    print("=== Detection Rates at CP3 (Signature Verify) ===")
    print(results.to_string(index=False))
    print()

    # Save summary
    Path('results').mkdir(exist_ok=True)
    with open('results/fault_type_summary.txt', 'w') as f:
        f.write("Fault Type Coverage Analysis\n")
        f.write("=" * 60 + "\n")
        f.write(f"Model: {model_path}\n")
        f.write(f"Threshold H: {model['H']:.3f}\n")
        f.write(f"Checkpoint: CP3 (Signature Verification)\n\n")
        f.write(results.to_string(index=False))
    print("Saved: results/fault_type_summary.txt")

    # Plot
    plot_fault_type_coverage(results)

    return 0

if __name__ == '__main__':
    sys.exit(main())
