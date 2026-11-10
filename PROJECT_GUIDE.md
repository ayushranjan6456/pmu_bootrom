# Pipeline and Methodology Guide

How the pieces fit together and why the detector is built the way it is. Results, effort and limitations live in [STATUS.md](STATUS.md); this guide does not repeat them. Commands and troubleshooting are in [README.md](README.md); the firmware detector's design is in [FIRMWARE_DETECTOR.md](FIRMWARE_DETECTOR.md).

## 1. What the system does

A bare-metal Cortex-M33 bootrom stub runs in QEMU (`mps2-an505`). Each boot passes through four checkpoints and prints its timing. A statistical model of clean timing is fitted offline. After checkpoint 2 (signature verification) the firmware scores the boot against that model and halts if it looks anomalous.

Two detectors exist and they are calibrated differently:

| | Python simulation | Firmware |
|---|---|---|
| Input | 20-boot windows of recorded data | one boot, once |
| Statistic | sequential CUSUM, `S = max(0, S + MD - k)` | the same update, called once with S = 0 and k = 0, so a threshold on MD |
| Threshold | k = 70th percentile of clean MD; H = 99th percentile of the window maximum (`data/model.npz`) | H = 1.25 x the largest clean MD (`src/cusum_detector.c`) |
| Used for | severity curves (synthetic attacks) | the 1000-boot validation |

Do not compare their numbers as if they were one detector (STATUS.md, Section 2).

## 2. Firmware (`src/`)

- `startup.c`: vector table and reset handler.
- `main.c`: UART output, SysTick timing, four stages, checkpoint recording, detector call.
- `cusum_detector.{h,c}`: fixed-point Q16.16 Mahalanobis distance and the CUSUM update (no FPU, no division).
- `linker.ld`: FLASH at 0x10000000, RAM at 0x38000000 (the `mps2-an505` memory map).

Stages (the work is busy loops on `volatile` variables, not real cryptography):

| Checkpoint | Stage | Sub-stages A / B / C (loop iterations) |
|---|---|---|
| 0 | boot start (includes UART init) | none (sub values are 0) |
| 1 | memory init | 200 / 200 / 200 |
| 2 | signature verify (monitored) | 500 / 300 / 200 |
| 3 | key derivation | 100 / 100 / 100 |

Each checkpoint prints `cp, elapsed, sub_a, sub_b, sub_c` between `DATA_START` and `DATA_END`. Timing is the SysTick 24-bit down-counter. In QEMU it follows host time, not executed instructions (STATUS.md, "Firmware partial-severity sweep"), which is the main platform limit.

Build variants:

| Command | Result |
|---|---|
| `make` | clean firmware `app.elf`; the detector halts the boot on alarm |
| `make app_attack.elf` | glitch on (`-DGLITCH_ATTACK`) and non-halting (`-DCOLLECT_MODE`), used for data collection |
| `-DGLITCH_SKIP_PCT=<n>` | skip n% of the sub-stage B loop (default 100); used by `scripts/severity_sweep.sh` |

The simulated fault removes the sub-stage B loop. It models a skipped verification loop, not an electrical glitch.

## 3. Statistical model (`scripts/`)

Feature vector at checkpoint 2: `x = [sub_a, sub_b, sub_c]`.

1. Fit the mean `mu` and covariance `S` on clean boots.
2. Score a boot by Mahalanobis distance `MD = sqrt((x - mu)' S^-1 (x - mu))`.
3. Alarm when the CUSUM statistic exceeds H.

Why a multivariate score: the three sub-stages move together under normal variation (correlation about 0.9), so a spike in one of them is far more unusual than its own spread suggests. Whether this beats a plain `sub_b` threshold depends on the fault size; the comparison is in STATUS.md ("Baseline comparison").

The clean data is not Gaussian (Shapiro-Wilk rejects it; [docs/GAUSSIAN_ASSUMPTION_ANALYSIS.md](docs/GAUSSIAN_ASSUMPTION_ANALYSIS.md)), so thresholds are set empirically from observed distances, not from Gaussian quantiles. For reference, the Gaussian 99% value for three features is MD 3.37, which would flag 3.6% of the clean boots.

Scripts:

| Script | Purpose |
|---|---|
| `collect.sh` (`make collect`) | 500 QEMU boots into `data/nominal_boots.csv` |
| `data_quality.py` | dataset integrity checks |
| `build_model.py` | clean data, fit the model, calibrate the sequential threshold, write `data/model.npz` and two figures |
| `cusum_detector.py` | synthetic attacks at 5 severities, detection and false-alarm rates, ROC at 20%; writes `results/cusum_results.png` |
| `cusum_detector2.py` | the fitted model against the recorded attack boots (`data/attack_boots.csv`), writes `results/empirical_attack.png` |
| `baseline_comparison.py` | one-shot Mahalanobis against `sub_b` thresholds |
| `calibrate_firmware.py` | fit the firmware model and print the C block for `src/cusum_detector.c` |
| `visualize.py` | cycle-stability figure |
| `test_firmware_detector.sh` | N clean and N glitched boots through the real firmware (`N=1000` for the full run) |
| `severity_sweep.sh` | partial-skip builds and boots |

### Sequential calibration

A CUSUM over a window false-alarms far more often than its single-observation threshold suggests, because every boot adds a chance to cross H. Using the single-observation 99th percentile of MD (4.88) as H gives about 13% false alarms over 20-boot windows (a quick simulation, resampling the clean MD values; not a repo script). Taking H from the 99th percentile of the window maximum (10.14) gives about 1%. That is what `build_model.py` does.

## 4. Fixed-point implementation

Q16.16 in `int32_t`, with 64-bit intermediates. The square root is a division-free bit-by-bit 64-bit integer root that keeps the fractional part. Two bugs shaped it (KNOWN_ISSUES.md): an integer-truncating root let distances just above the threshold slip under it (ISSUE-008), and a squared distance of 32768 or more wrapped on narrowing and failed open (ISSUE-014, fixed by clamping inputs and saturating the squared distance). Verification so far is offline host testing, not an in-repo test.

## 5. Running the full flow

```bash
make clean && make                  # build
make run </dev/null                 # one boot in QEMU
make collect                        # 500 clean boots (about 7 minutes)
source .venv/bin/activate
python scripts/data_quality.py
python scripts/build_model.py
python scripts/cusum_detector.py
make collect-attack                 # 50 glitched boots
python scripts/cusum_detector2.py
python scripts/calibrate_firmware.py   # paste the printed block into src/cusum_detector.c, then rebuild
N=1000 bash scripts/test_firmware_detector.sh > results/validation_1000.log
python scripts/baseline_comparison.py
```

Run `test_firmware_detector.sh`, `severity_sweep.sh` and any manual build one at a time: they all run `make clean` and rebuild the shared `app.elf`, so overlapping runs swap the build under each other and corrupt the results.

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
