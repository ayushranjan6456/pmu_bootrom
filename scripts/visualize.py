import pandas as pd
import matplotlib.pyplot as plt
import os

# Define the path to your CSV
CSV_FILE = 'data/nominal_boots.csv'

if not os.path.exists(CSV_FILE):
    print(f"Error: {CSV_FILE} not found. Run 'make collect' first.")
    exit(1)

# Load the CSV data
print("Loading data...")
df = pd.read_csv(CSV_FILE)

# Filter data strictly for Checkpoint 2 (Signature Verification Stage)
# This is our primary attack target.
df_cp2 = df[df['cp'] == 2]

# Create a figure with two subplots (side-by-side)
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

# --- Plot 1: Cycle stability over time (Line Plot) ---
ax1.plot(df_cp2['boot_id'], df_cp2['sub_a'], label='Sub A (Hash Compute)', color='blue')
ax1.plot(df_cp2['boot_id'], df_cp2['sub_b'], label='Sub B (Key Reduction)', color='orange')
ax1.plot(df_cp2['boot_id'], df_cp2['sub_c'], label='Sub C (Signature Compare)', color='green')

ax1.set_title('Cycle Stability Across 500 Boots (CP 2)')
ax1.set_xlabel('Boot Iteration')
ax1.set_ylabel('Execution Time (Cycles)')
ax1.legend()
ax1.grid(True, linestyle='--', alpha=0.7)

# --- Plot 2: Distribution of cycle counts (Histogram) ---
# We use a histogram to visualize the variance (jitter) in the hardware.
ax2.hist(df_cp2['sub_a'], bins=10, alpha=0.6, label='Sub A', color='blue')
ax2.hist(df_cp2['sub_b'], bins=10, alpha=0.6, label='Sub B', color='orange')
ax2.hist(df_cp2['sub_c'], bins=10, alpha=0.6, label='Sub C', color='green')

ax2.set_title('Execution Time Distribution (Hardware Variance)')
ax2.set_xlabel('Execution Time (Cycles)')
ax2.set_ylabel('Frequency')
ax2.legend()
ax2.grid(True, linestyle='--', alpha=0.7)

plt.tight_layout()
plt.show()