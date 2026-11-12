# Pipeline and Methodology Guide

How the pieces fit together and why the detector is built the way it is. Results, effort and limitations live in [STATUS.md](STATUS.md); this guide does not repeat them. Commands and troubleshooting are in [README.md](README.md); the firmware detector's design is in [FIRMWARE_DETECTOR.md](FIRMWARE_DETECTOR.md).

## 1. What the system does

A bare-metal Cortex-M33 bootrom stub runs in QEMU (`mps2-an505`). Each boot passes through eight checkpoints (CP0-CP7) and prints its timing. Two detectors run in the firmware:

1. **Floor detector** (primary): After each checkpoint CP1-CP7, checks if any sub-stage is below 0.45× its clean median. If so, halts the boot immediately. 140 bytes, integer compares only.

2. **Mahalanobis detector** (secondary): After CP3 only, scores the boot against a multivariate Gaussian model of clean timing. If the one-shot Mahalanobis distance exceeds a threshold, prints a warning but allows boot to continue. 1060 bytes, Q16.16 fixed-point.

Design rationale: The floor rule has 0% false alarms and catches large timing reductions reliably. The Mahalanobis rule has 5.7% false alarms on clean boots (timing spikes trigger it), so it warns only. Together they provide fail-stop protection for skipped loops and visibility into upward timing anomalies. See [FIRMWARE_DETECTOR.md](FIRMWARE_DETECTOR.md) and [docs/MAHALANOBIS_ANALYSIS.md](docs/MAHALANOBIS_ANALYSIS.md).

## 2. Firmware (`src/`)

- `startup.c`: vector table and reset handler.
- `main.c`: UART output, SysTick timing, four stages, checkpoint recording, detector call.
- `cusum_detector.{h,c}`: fixed-point Q16.16 Mahalanobis distance and the CUSUM update (no FPU, no division).
- `linker.ld`: FLASH at 0x10000000, RAM at 0x38000000 (the `mps2-an505` memory map).

Stages (the work is busy loops on `volatile` variables, not real cryptography):

| Checkpoint | Stage | Sub-stages A / B / C (loop iterations) |
|---|---|---|
| 0 | boot start (includes UART init) | none (sub values are 0) |
| 1 | hardware init | 200 / 200 / 200 |
| 2 | boot mode detect | 200 / 200 / 200 |
| 3 | signature verify (primary attack target) | 500 / 300 / 200 |
| 4 | decrypt stage | 200 / 200 / 200 |
| 5 | integrity check | 200 / 200 / 200 |
| 6 | memory setup | 200 / 200 / 200 |
| 7 | handoff | 200 / 200 / 200 |

Each checkpoint prints `cp, elapsed, sub_a, sub_b, sub_c` between `DATA_START` and `DATA_END`. Timing is the SysTick 24-bit down-counter. In QEMU it follows host time, not executed instructions, so partial skips are invisible (ISSUE-012).

Build variants:

| Command | Result |
|---|---|
| `make` | Clean firmware `app.elf`; floor detector halts on alarm |
| `make app_collect.elf` | Non-halting (`-DCOLLECT_MODE`) for data collection |
| `make app_attack.elf` | Attack fault (`-DGLITCH_ATTACK`) + collect mode |
| `make app_ft1.elf` | FT-1 fault (CP1 sub_b removed) + collect mode |
| `make app_ft2.elf` ... `app_ft5.elf` | Other fault types, see [FAULT_MODELS.md](FAULT_MODELS.md) |

Six fault types are implemented: five skipped loops and one extra loop (FT-5, +84% on CP3 sub_c).

## 3. Statistical model (`scripts/`)

**Floor detector:** For each checkpoint, compute the median of each sub-stage over 300 clean boots. Alarm if any sub-stage < F × median, where F = 0.45. Calibrated by `scripts/calibrate_floor.py`, table written to `src/floor_table.h`.

**Mahalanobis detector (CP3 only):** Feature vector `x = [sub_a, sub_b, sub_c]`.

1. Fit the mean `mu` and covariance `S` on 300 clean boots at CP3.
2. Score a boot by Mahalanobis distance `MD = sqrt((x - mu)' S^-1 (x - mu))`.
3. Alarm when MD exceeds H = 1.25 × max clean MD (one-shot threshold, k=0).

Why a multivariate score: the three sub-stages move together under normal variation (correlation about 0.9), so a spike in one of them is far more unusual than its own spread suggests. 

The clean data is not Gaussian (Shapiro-Wilk rejects it; [docs/GAUSSIAN_ASSUMPTION_ANALYSIS.md](docs/GAUSSIAN_ASSUMPTION_ANALYSIS.md)), and contains timing spikes (about 14% of boots have some sub-stage above 1.5× median). These spikes make the two-sided Mahalanobis rule unreliable across all checkpoints. The floor rule is one-sided (downward only) and robust. See [docs/MAHALANOBIS_ANALYSIS.md](docs/MAHALANOBIS_ANALYSIS.md).

Scripts:

| Script | Purpose |
|---|---|
| `collect_fault_types.sh` | Batch QEMU collection (N boots → CSV) |
| `calibrate_floor.py` | Fit floor table, write `src/floor_table.h` |
| `calibrate_firmware.py` | Fit Mahalanobis model for CP3, print C constants |
| `validate_firmware.py` | Test detectors on validation data (held-out, 4 splits) |
| `test_halting_build.sh` | Real halting-build test (N=300 per variant) |
| `detector_comparison.py` | Held-out comparison, floor fraction sweep, synthetic severity |
| `mahalanobis_failure_analysis.py` | Why Mahalanobis fails on 8-CP data |
| `make_slide_plots.py` | Generate figures 1-6 for slides |
| `fw_model.py` | Python mirror of firmware fixed-point arithmetic |

## 4. Fixed-point implementation

Q16.16 in `int32_t`, with 64-bit intermediates. The square root is a division-free bit-by-bit 64-bit integer root that keeps the fractional part. Two bugs shaped it (KNOWN_ISSUES.md): an integer-truncating root let distances just above the threshold slip under it (ISSUE-008), and a squared distance of 32768 or more wrapped on narrowing and failed open (ISSUE-014, fixed by clamping inputs and saturating the squared distance). Verification so far is offline host testing, not an in-repo test.

## 5. Running the full flow

```bash
# Build and test
make clean && make
make run </dev/null

# Collect calibration data
bash scripts/collect_fault_types.sh data/cal_clean app_collect.elf 300

# Calibrate detectors
source .venv/bin/activate
python scripts/calibrate_floor.py data/cal_clean.csv 0.45
python scripts/calibrate_firmware.py data/cal_clean.csv 3 data/ds1_attack.csv
# (Update src/floor_table.h and src/cusum_detector.c constants, then rebuild)

# Collect validation data (7 variants × 300 boots)
bash scripts/collect_fault_types.sh data/val_clean app_collect.elf 300
bash scripts/collect_fault_types.sh data/val_attack app_attack.elf 300
# ... (ft1 through ft5)

# Validate
python scripts/validate_firmware.py
python scripts/detector_comparison.py
python scripts/mahalanobis_failure_analysis.py

# Generate slide figures
python scripts/make_slide_plots.py

# Test real halting build (optional, ~30 minutes for N=300)
bash scripts/test_halting_build.sh
```

Run `test_halting_build.sh` alone: it rebuilds `app.elf` per variant, so concurrent `make` commands corrupt results.

Redirect QEMU's input from `/dev/null` (or use `timeout --foreground`) when running it by hand from a terminal; otherwise it can block and the capture comes back empty. `test_firmware_detector.sh` aborts if a boot produces no output.

Dependencies: `arm-none-eabi-gcc`, QEMU 8.0 or newer (developed on 8.2.2), Python 3.12 or newer (developed on 3.13) with the packages in `requirements.txt`.

## 6. Reading the outputs

- `results/model_distributions.png`, `threshold_calibration.png`: the fitted model and the sequential calibration.
- `results/cusum_results.png`: detection against severity, from the Python simulation.
- `results/empirical_attack.png`: recorded attack boots against the clean cloud.
- `results/cycle_stability.png`: raw timing of the clean boots.
- `results/validation_1000.log`: the firmware validation. The final lines give the false-alarm and detection counts.
- `results/false_alarms.csv`, `results/false_alarms/`: telemetry of each false alarm from the last validation run. `test_firmware_detector.sh` deletes `results/false_alarms/` when it starts and rewrites the CSV. Once these files are committed, `git checkout -- results/false_alarms results/false_alarms.csv` restores them after a rerun; until then, or if you want to keep both runs, copy them elsewhere first. The 9-alarm table of the earlier run lives only in `results/false_alarms_prev_run_9_recovered.csv` (untracked until committed).

## 7. What the platform can and cannot tell us

- QEMU's Cortex-M33 has no DWT cycle counter (CYCCNT stays 0), so SysTick stands in for the PMU counters.
- SysTick follows host time, so shortening the loop by less than 100% barely changes `sub_b`. There is no firmware severity curve; the severity curve is Python-only.
- Rare host pauses appear as one-sided timing spikes and cause the roughly 1% false-alarm rate.
- The model is fitted on boots that probably exclude such spikes (STATUS.md, Section 3).

Phase 2 (STM32L552, DWT counters, debugger-based fault injection) is meant to remove the first three limits. The plan is in STATUS.md, Section 7.
