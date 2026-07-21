import pandas as pd
import numpy as np

df = pd.read_csv('data/nominal_boots.csv')

print("=== BASIC SHAPE ===")
print(f"Total rows: {len(df)}")
print(f"Unique boot_ids: {df['boot_id'].nunique()}")
print(f"Checkpoints per boot: {df['cp'].nunique()}")
print(f"Columns: {list(df.columns)}")

print("\n=== MISSING / BAD ROWS ===")
print(f"Rows with any NaN: {df.isna().any(axis=1).sum()}")
print(f"Rows where elapsed==0 AND cp>0: "
      f"{len(df[(df['cp'] > 0) & (df['elapsed'] == 0)])}")

print("\n=== PER-CHECKPOINT STATISTICS ===")
for cp in sorted(df['cp'].unique()):
    sub = df[df['cp'] == cp]
    print(f"\nCheckpoint {cp} (n={len(sub)}):")
    for col in ['elapsed', 'sub_a', 'sub_b', 'sub_c']:
        vals = sub[col]
        print(f"  {col:10s}  mean={vals.mean():.1f}  "
              f"std={vals.std():.4f}  "
              f"min={vals.min()}  max={vals.max()}  "
              f"unique={vals.nunique()}")

print("\n=== DUPLICATE CHECK ===")
# If QEMU is deterministic, every boot produces identical rows
feature_cols = ['cp', 'elapsed', 'sub_a', 'sub_b', 'sub_c']
n_unique = df[feature_cols].drop_duplicates().shape[0]
print(f"Unique feature rows: {n_unique} out of {len(df)} total")
print(f"{'DETERMINISTIC (QEMU)' if n_unique <= df.cp.nunique() else 'HAS VARIANCE — good for real hardware'}")