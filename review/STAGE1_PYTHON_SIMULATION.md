# Stage 1: The Python Simulation

Study notes in plain language. Numbers come from [STATUS.md](../STATUS.md) and `data/model.npz`; if a number here ever differs from STATUS.md, STATUS.md wins.

**Period:** 7 Nov 2026 (commit 051046f). **Code:** [build_model.py](../archive/old_scripts/build_model.py) and [cusum_detector.py](../archive/old_scripts/cusum_detector.py) (now in `archive/old_scripts/`).

---

## The idea in one paragraph

A bootrom runs the same stages in nearly the same number of cycles every time. If an attacker makes a loop skip, one stage finishes faster than normal. So we measure how long clean boots take, learn the normal pattern, and raise an alarm when a boot does not fit it.

## The setup

- A 4-checkpoint stub in QEMU. We watched checkpoint 2, signature verification.
- At that checkpoint the firmware records three timings: `sub_a`, `sub_b`, `sub_c` (cycles spent in three parts of the stage).
- Each boot is one row of 3 numbers.
- **Which data the numbers below come from.** The first collection (7 Nov) had 500 usable boots, with averages of about 705 / 562 / 543 cycles. The model and results quoted here come from the later re-collection (9 to 10 Nov, 496 boots) because that is what the repo holds and what STATUS.md reports; the method is identical. Four boots are missing from the re-collection, probably because the halting firmware alarmed on them (consistent with the data, not proven).

## Step 1: learn what "normal" looks like (`build_model.py`)

1. **Clean the data.** Drop boots broken by the SysTick bug (below). Then drop outliers with the 2.5 x IQR rule, because the host sometimes slows QEMU by 3 to 5 times for one boot.
2. **Average boot.** The mean is `mu` = [695, 583, 502] cycles.
3. **How the three numbers move together.** This is the covariance matrix. Correlation between sub-stages is about 0.9: when the host is slow, all three get slower together.

## Step 2: score a boot with Mahalanobis distance (MD)

MD answers: "how strange is this boot, given how the three numbers normally move together?" Small means normal.

A real example from the fitted model, using the first boot in the data:

| | sub_a | sub_b | sub_c | MD |
|---|---:|---:|---:|---:|
| Clean boot | 782 | 680 | 559 | 1.79 |
| Same boot, `sub_b` cut by 20% | 782 | 563 | 559 | 4.47 |

After the cut, `sub_b` is only 0.3 standard deviations below the mean, so a plain threshold on `sub_b` sees nothing. But `sub_a` and `sub_c` are both high, and normally `sub_b` would be high too. A low `sub_b` beside two high neighbours breaks the pattern, and MD catches that. This is why MD was chosen over a simple threshold.

## Step 3: the CUSUM running total

One slightly odd boot is not proof of an attack, so CUSUM keeps a running total:

`S = max(0, S + MD - k)`

- MD below `k`: the total drifts back toward 0.
- MD above `k` boot after boot: the total climbs.
- `S` above `H`: alarm.

One illustrative run (a single random stream, not the averages in the results table), with `k` = 1.685 and `H` = 10.14. Boots 0 to 9 clean, boots 10 to 19 have `sub_b` cut by 20%:

| Boot | MD | S |
|---|---:|---:|
| 7 (clean, a mild bump) | 4.84 | 3.19 |
| 9 (clean) | 1.56 | 2.73 |
| 10 (first glitched) | 3.98 | 5.02 |
| 11 | 4.58 | 7.92 |
| 12 | 6.77 | 13.01, alarm |
| 19 | 5.06 | 38.16 |

## Step 4: choosing `k` and `H` correctly

- `k` is the 70th percentile of clean MD: 1.685.
- Taking `H` from single-boot MD values gives too many false alarms, because the total adds up over a window and a run of mildly high clean boots can cross the line. A quick simulation gave about 13% false alarms over 20 boots (the script's own comment says 8 to 10%).
- The fix: simulate 10,000 clean 20-boot sequences, record the highest `S` in each, and set `H` at the 99th percentile of those. That gives `H` = 10.14 and targets about 1% false alarms.

## Step 5: test with fake attacks (`cusum_detector.py`)

Take clean boots and subtract a fraction from `sub_b` in Python. Each test stream is 10 clean boots then 10 faulted boots.

| Cut to `sub_b` | Detected | False alarms |
|---|---:|---:|
| 5% | 4.5% | 0.1% |
| 10% | 86.2% | 0.5% |
| 20% | 99.7% | 0.3% |
| 30% to 50% | 99.6% | 0.4% |

It works from about 10% upward. At 5% the signal (28 cycles) is smaller than the noise (63 cycles). ROC AUC at 20% is 0.9933.

## Problems found in this stage

- **ISSUE-001, 37% corrupt boots (185 of 500).** The first `systick_init` wrote 0 to the counter register, and on ARM that reloads the counter to its maximum, 16,777,215. The first reading then looked like 16 million cycles, and later subtractions went negative and wrapped to about 4 billion. Fixed by starting the timer first, then clearing it.
- **ISSUE-004, ROC AUC 0.4988.** That is no better than a coin flip. The test mixed clean and attack boots in one stream, so detection and false-alarm rates were measured wrongly. Fixed; it now reads 0.9933.
- **ISSUE-002, data not Gaussian.** Shapiro-Wilk rejects it; the timings are flat and multi-peaked, probably host scheduling noise. So `H` is set from observed data, not from a textbook formula.

## Why this was not enough

1. **The attacks were not real.** They were Python subtraction on the data (ISSUE-007). Nothing in the firmware reacted.
2. **The test is in-sample.** Attack streams were resampled from the same 496 boots that fitted the model.
3. **It assumes 10 faulted boots in a row.** With a single faulted boot at 20% severity, detection was only 2.3%. A real boot decides once, for itself.
4. **It only existed in Python.** A boot-time defence has to run inside the bootrom (ISSUE-008).

Points 3 and 4 led to Stage 2: porting the detector to C.
