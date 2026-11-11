# Project Status

Single source of truth for results, effort, scope versus proposal, and limitations. Other documents link here instead of repeating these numbers.

**Project:** PMU-Based Statistical Detection of Fault Injection Attacks in Secure Boot
**Student:** Ayush Ranjan (EE24M504)
**Phase:** 1 (QEMU simulation and algorithm development), ready for review
**Last updated:** 2026-11-10

---

## 1. What exists

- Bare-metal Cortex-M33 bootrom stub running in QEMU (`mps2-an505`), with four boot stages and timing checkpoints (SysTick cycle counter).
- Python pipeline: data collection, Gaussian model fit, CUSUM simulation with synthetic attacks, ROC analysis.
- Firmware-embedded detector in fixed-point Q16.16 (Mahalanobis distance plus CUSUM). It runs after checkpoint 2 and halts boot on alarm. Design: [FIRMWARE_DETECTOR.md](FIRMWARE_DETECTOR.md).
- Calibration script that emits the C model parameters, and an automated detection test script.

## 2. Results

### Firmware detector, 1000-boot validation

Run with `N=1000 bash scripts/test_firmware_detector.sh`. Raw log: [results/validation_1000.log](results/validation_1000.log).

| Test | Result |
|------|--------|
| Clean boots with a false alarm | 14 / 1000 (1.4%) |
| Glitched boots detected | 1000 / 1000 (100%) |
| Glitched boots missed | 0 / 1000 |

The firmware is a calibrated one-shot threshold on Mahalanobis distance (k = 0, H = 1.25 x max clean MD, see [FIRMWARE_DETECTOR.md](FIRMWARE_DETECTOR.md)). The script's pass criteria are at most 5% false alarms and at least 90% detection, so it reports PASS. The 1% false alarm target of the Python sequential calibration does not apply to the firmware.

Run on 2026-11-10. All 1000 clean boots (986 clean, 14 false alarms) and all 1000 glitched boots (all detected) are recorded, and the log ends with the summary. This harness version aborts if a boot produces no output, so an empty QEMU capture cannot be counted as a clean boot or a miss.

Earlier runs, kept in `results/` for history only (file times are from the repository; the detector sources `cusum_detector.{c,h}` and `main.c` were last edited at 09:13 on 2026-11-10):

| Log (written) | Build | False alarms | Detected | Notes |
|---------------|-------|--------------|----------|-------|
| `validation_1000.log` (09:38) | current sources | 14 / 1000 (1.4%) | 1000 / 1000 | Final run |
| `validation_1000_prev_run_10_nov.log` (08:38) | same threshold and clean-boot path; built before the 09:13 edit, so no overflow protection and a weaker glitch | 9 / 1000 (0.9%) | 997 / 1000 | 3 misses: attacks 404, 557, 842. Probably the weaker glitch (plausible, not proven) |
| `validation_1000_prev_model.log` | sequential `k`, `H` (alarm at MD > about 15.4) | 10 / 1000 | 999 / 1000 | 1 miss |
| `validation_1000_before_sqrt_fix.log` | before the sqrt fix | 14 / 1000 | 981 / 1000 | 19 misses |

The last two came from earlier firmware (the threshold or the sqrt changed) and from earlier versions of the test harness, so they are not comparable with the final run and no trend is drawn from them. A further run (8 false alarms, 1000 detected) left no log in the repo and is not cited.

**Pooled false-alarm rate, final run plus the 08:38 run:** 23 / 2000 = 1.15% (Wilson 95% interval 0.77% to 1.72%), so about 1%. The two runs use the same threshold and the same clean-boot path; the later build added overflow protection and a stronger glitch, which do not affect clean boots in the normal range. The 14 against 9 difference is not significant (Fisher exact test, p = 0.40), which supports pooling.

Caveats on these numbers:
- The glitched boots all use one fault: the whole of sub-stage B in signature verification is skipped (`-DGLITCH_ATTACK`). The fault is large, so clean and glitched boots are far apart in the datasets (clean Mahalanobis distance at most 8.7 and glitched 19.1 to 31.9, over 496 and 50 boots). The run shows the pipeline works end to end. It does not show sensitivity to subtle faults (next subsection).
- Host load during the run was not recorded.
- Earlier 20+20 smoke tests were too small to support a "100% / 0%" claim and are superseded.

### Sensitivity of the shipped firmware threshold

The firmware threshold (H = 10.84) is much higher than the thresholds behind the Python and baseline tables below, so those tables do not describe the shipped detector. To measure it, the firmware's own C arithmetic (`src/cusum_detector.c`, compiled for the host) was run on the 496 clean CP2 rows with `sub_b` reduced by x%. This is offline and in-sample (the training boots, not held-out boots), not a QEMU measurement.

| `sub_b` reduction | 10% | 20% | 30% | 40% | 45% | 50% | 60% and more |
|-------------------|-----|-----|-----|-----|-----|-----|--------------|
| Detected | 0% | 0.2% | 1.4% | 49% | 79% | 97% | 100% |

An independent audit with a slightly different method got 37% at 40%, 95% at 45% and 99% at 50%, so read the transition as roughly 40 to 50%. Slowing all three sub-stages together by the same factor is not flagged until about 2x (0.8% at 1.5x, 67% at 2x), because that moves along the correlated direction of normal variation. The real glitch removes about 85% of `sub_b` (mean `sub_b` 87 against a clean mean of 583), far beyond the transition. The shipped detector therefore catches large faults reliably and misses anything milder than roughly a 40% `sub_b` reduction.

The three operating points are different: the baseline table uses a one-shot threshold at the 99th percentile of clean MD (4.88), the Python table uses a sequential CUSUM (k = 1.685, H = 10.14) over 20-boot windows, and the firmware uses a one-shot H = 10.84.

### False alarms in the 1000-boot validation

The harness saved the telemetry of each false alarm (`results/false_alarms.csv`, full output in `results/false_alarms/`). Mahalanobis distance (MD) below is computed offline with the embedded parameters in floating point; the threshold H is 10.84. The z-score is the largest sub-stage deviation from the clean mean in units of the clean standard deviation (496-boot dataset).

**Final run (14 false alarms):**

| Boot | sub_a | sub_b | sub_c | MD | Largest deviation |
|------|-------|-------|-------|----|-------------------|
| 25 | 731 | 2059 | 599 | 63.7 | sub_b, +24.3 |
| 110 | 964 | 719 | 1524 | 45.0 | sub_c, +20.3 |
| 222 | 1934 | 842 | 546 | 44.6 | sub_a, +20.3 |
| 368 | 1011 | 668 | 479 | 12.2 | sub_a, +5.2 |
| 440 | 817 | 1301 | 658 | 26.1 | sub_b, +11.8 |
| 557 | 1913 | 854 | 499 | 44.9 | sub_a, +19.9 |
| 560 | 1957 | 798 | 488 | 47.7 | sub_a, +20.7 |
| 757 | 733 | 592 | 787 | 13.8 | sub_c, +5.7 |
| 784 | 1044 | 639 | 568 | 11.8 | sub_a, +5.7 |
| 807 | 1199 | 561 | 455 | 22.0 | sub_a, +8.2 |
| 834 | 859 | 2007 | 503 | 61.6 | sub_b, +23.5 |
| 932 | 1151 | 3589 | 751 | 120.7 | sub_b, +49.6 |
| 963 | 1689 | 923 | 504 | 35.3 | sub_a, +16.3 |
| 981 | 2980 | 900 | 520 | 86.4 | sub_a, +37.4 |

**Earlier run (9 false alarms, see [false_alarms_prev_run_9_recovered.csv](results/false_alarms_prev_run_9_recovered.csv)):**

| Boot | sub_a | sub_b | sub_c |
|------|-------|-------|-------|
| 90 | 1692 | 736 | 511 |
| 99 | 1051 | 552 | 489 |
| 128 | 780 | 2991 | 533 |
| 249 | 778 | 1110 | 589 |
| 318 | 776 | 2769 | 526 |
| 405 | 750 | 2125 | 670 |
| 410 | 745 | 720 | 1852 |
| 602 | 650 | 1834 | 575 |
| 780 | 4900 | 611 | 474 |

**Characterization (mechanism, evidence, status):**

**Mechanism:** The false alarms are large one-sided slowdowns of a single sub-stage. In the 496-boot training set at CP2, the largest z-score is about +3.9 and the smallest about -2.3; normal variation across clean boots moves all three sub-stages together (correlation about 0.9). A spike that moves only one sub-stage breaks the correlation pattern, so the Mahalanobis distance jumps. This is the detector working as designed on a corrupted timing signal.

**Hypothesis:** SysTick in QEMU follows host time, not executed instructions (see the severity sweep below and ISSUE-012). If the host pauses the emulator mid-boot (a context switch, a timer tick, a scheduler stall), the pause appears in the telemetry as one or two inflated sub-stages.

**Evidence:**
- All 23 alarms (14 + 9) have at least one sub-stage above the training maximum. Across the 23, the largest sub-stage z-score runs from +5.2 to +68.9 (14-boot run +5.2 to +49.6; 9-boot run +5.8 to +68.9) and the MD from 11.8 to 171.5, against H = 10.84. The smallest values (MD 11.8, 12.2, 13.8, 15.5) are near the threshold; most are far above it.
- The deviations are all upward (slower). No false alarm has a low `sub_b` (the lowest `sub_b` z-score across the 23 is -0.5), whereas the simulated glitch drops `sub_b` to about 15% of its clean value.
- Timing spikes also exist in the training data at other checkpoints: 7 of the 496 boots have a spike at CP1 or CP3 (up to `sub_b` = 4653). CP2 has none. At the validation rate (23 / 2000) the chance of no spike in 496 boots at CP2 is about 0.3%, so something removed them (next paragraph).
- Harness differences do not explain the spikes: in an interleaved test run by the external audit (collect-style against validation-style captures) the medians matched (p = 0.86 / 0.19 / 0.50) and spikes appeared under both. That test is not in the repo.

**Probable selection effect in the training set (consistent with the data, not proven):** `make collect` runs the halting firmware (`app.elf`). A boot that alarms prints no data block, so it is silently dropped. The external audit saw 5 of 240 captures with no CP2 row, all of them alarms (not reproduced here). The four absent ids (26, 116, 386, 479) are probably such boots (4 of 500 is close to the 5.75 expected at 1.15%). If so, the training set was filtered by the detector, the clean-boot spread is understated, and the 1.25x margin was fitted to a sample without spikes. The way to test it is to collect with a non-halting build (`-DCOLLECT_MODE`) and compare.

**Status:** The hypothesis is a fit, not a confirmed cause. Confirming it needs the host load during the runs (not recorded), or repeating the alarmed boots in isolation. Alternatives (a real timing spike in the emulator, a UART stall) have not been ruled out.

**Consequence for the detector:** The false alarms are timing spikes and not a calibration problem, so raising H would not remove the large ones (they reach MD 171, while the real glitch in the datasets sits at MD 19 to 32). A signed test that alarms only on a low `sub_b` would not have alarmed on any of these 23. This has not been tested; the `sub_b` low-side baseline below is the closest existing measurement.

**Phase 2 mitigation:** On hardware, the DWT counters measure executed work (cycle count, CPI, load-store unit events), not wall-clock time. A host stall cannot inflate the counter (there is no host). Re-measure the false-alarm rate on hardware; if it drops below 0.1%, the issue is resolved. If hardware also shows timing spikes, options include: (a) a fault-vs-stall discriminator (the real glitch is a downward shift; the false alarms are upward and uncorrelated), (b) a repeat-confirm rule (two consecutive alarms → halt; latency cost).

### Baseline comparison (one-shot detectors)

From `scripts/baseline_comparison.py`: all detectors see one boot at CP2 and use a threshold at the 99th percentile of clean training scores. False alarms are measured on held-out clean boots (50/50 split, 200 repeats). Columns 5% to 50% are synthetic `sub_b` reductions applied to held-out clean boots.

| Detector | False alarm | Real glitch | 5% | 10% | 20% | 30% | 50% |
|----------|-------------|-------------|----|-----|-----|-----|-----|
| Mahalanobis (3 features) | 1.73% | 100% | 2.1% | 5.5% | 71.6% | 99.4% | 100% |
| `sub_b` low side | 1.36% | 100% | 7.3% | 16.2% | 48.3% | 73.3% | 99.7% |
| `sub_b` two-sided | 1.39% | 100% | 5.3% | 13.2% | 45.9% | 65.0% | 99.7% |

Reading it honestly:
- The real glitch (about 85% reduction of `sub_b`: median 88 in `attack_boots.csv` against the clean mean of 583) is caught by every detector. It cannot show that Mahalanobis is better.
- Mahalanobis is better from about 20% severity upward (71.6% against 48.3% at 20%, 99.4% against 73.3% at 30%).
- At 5% and 10% a `sub_b` threshold is better (16.2% against 5.5% at 10%). Nothing here supports Mahalanobis for the weakest faults.
- These one-shot rates differ from the sequential Python table below because the detectors differ (one boot against 20-boot windows) and the severity definitions may not match; do not read them as one dataset.

### Python simulation (synthetic attacks)

From `scripts/cusum_detector.py`, a timing shift applied to sub-stage B of nominal data, sequential CUSUM over 20-boot windows. Details in [KNOWN_ISSUES.md](KNOWN_ISSUES.md) ISSUE-003.

**Note:** The detection rates below are for 10 consecutive faulted boots (per stream), not single boots. Each stream is 10 clean boots followed by 10 faulted ones, resampled from the same 496 boots used to fit the model (in-sample). With the same k and H, one faulted boot at 20% severity is detected 2.3% of the time, three boots 83%, ten boots 100%.

| Severity | Detection rate | False alarm rate |
|----------|----------------|------------------|
| 5% | 4.5% | 0.1% |
| 10% | 86.2% | 0.5% |
| 20% | 99.7% | 0.3% |
| 30% | 99.6% | 0.4% |
| 50% | 99.6% | 0.4% |

ROC AUC at 20% severity: 0.9933 (the script reports it only at 20%). Threshold: k = 1.685 and H = 10.14 from `data/model.npz`. This is a different operating point from the shipped firmware (see "Sensitivity of the shipped firmware threshold" above).

### Firmware partial-severity sweep: not possible with QEMU timing

`main.c` accepts `-DGLITCH_SKIP_PCT=<n>` (skips n% of the sub-stage B loop, default 100) and `scripts/severity_sweep.sh` builds and boots each setting. Raw output: [results/severity_sweep.log](results/severity_sweep.log) (2026-11-10, QEMU 8.2.2, N=20 per setting). The sweep shows no dependence on the skip percentage, so no firmware severity curve is reported.

| Skip % | Loop iterations | Detected (of 20) | Median `sub_b` (cycles) |
|--------|-----------------|------------------|-------------------------|
| 0 | 300 | 0 | 627 |
| 25 | 225 | 0 | 626 |
| 50 | 150 | 0 | 610 |
| 75 | 75 | 0 | 611 |
| 90 | 30 | 0 | 601 |
| 99 | 3 | 0 | 600 |
| 100 | 0 | 20 | 93 |

This table is from the log written at 13:15 on 2026-11-10 with the current build, run alone on an otherwise idle machine (QEMU 8.2.2, N=20, mean clean `sub_b` 582.651). Within this run the medians for 0 to 99% skip lie between 600 and 627 (a 4% change from 0% to 99% skip), against a drop of about 84% when the whole loop is removed, so the platform shows no usable dependence on the skip percentage. That 84% is against the clean mean of 582.7 cycles in `nominal_boots.csv` (the log's mean-reduction column reads 84.1%); against this run's own 0%-skip mean of 622.6 it is 85%. A 4% change is about what chance produces here: with a clean `sub_b` standard deviation of 60.6 cycles, the median of 20 boots scatters by about 17 cycles (3% of the mean). None of the 120 non-glitch boots was detected in this run.

This is the only sweep kept. An earlier run the same day was discarded because overlapping invocations shared one `app.elf` (each run rebuilds it), so run `severity_sweep.sh` and `test_firmware_detector.sh` one at a time.

Likely cause, not yet confirmed: SysTick in QEMU follows host time, not executed instructions, so `sub_b` is dominated by a roughly fixed cost (for example first-time translation of the loop block) and not by per-iteration work. With QEMU `-icount shift=0,sleep=off`, `sub_b` is exact and linear (78, 39, 1, 0 at 0, 50, 99, 100% skip, identical on 6 boots each; not saved in the repo), but clean boots then have zero variance and the Mahalanobis model cannot be fitted without an artificial noise floor. The partial-severity result therefore comes only from the Python simulation; the hardware phase will repeat the sweep with DWT counters.

Note: the sweep's own 0%-skip median (627) is about 8% above the clean mean in `nominal_boots.csv` (583). Compare rows within one sweep, not against the CSV.

### Resource footprint (measured) and latency (not yet measured)

**Footprint:**
From `arm-none-eabi-size app.elf` (2026-11-10, after the overflow fix):
- Detector code (`cusum_detector.o` text section): 1060 bytes
- Whole firmware (text): 3152 bytes
- BSS (detector state): 64 bytes

Earlier notes cited ~968 bytes for the detector and ~3060 bytes for the firmware. Those figures could not be reproduced: rebuilding commit 4b019e3 (before the overflow fix) gives 1,784 bytes for the detector object, which is larger than the current 1,060.

**Latency:**
Not yet measured. Estimate in earlier documents (about 350 cycles) is unverified. Measure with SysTick around `cusum_update` and add to a later revision.

### Fixed-point overflow bug (found and fixed, Phase 1)

**Issue:** The squared Mahalanobis distance `q = (x-μ)' Σ⁻¹ (x-μ)` is computed as a 64-bit intermediate and then narrowed to Q16.16 (`int32_t`). When `q >= 32768` (MD >= 181.02), the narrowing wrapped, clamped to zero, and `fixed_sqrt(0)` returned zero → the detector failed open (large distances reported as zero, no alarm).

**Found:** 2026-11-10, while reviewing how the detector handles extreme inputs, not by a failing test. The datasets do not exercise it (the largest sub-stage at checkpoint 2, the only checkpoint the detector sees, is 934 cycles in the clean data; checkpoints 1 and 3 reach 4,653 and 3,293 in occasional spiky boots; and the glitched boots only shorten `sub_b`).

**Fix:** Observations above 32767 are clamped to 32767 before the delta is formed ([src/cusum_detector.c](src/cusum_detector.c), the clamp in `mahalanobis_distance`), the 64-bit squared distance is saturated to `INT32_MAX` before it is narrowed (same function, the `q64` branches), and `cusum_update` additionally alarms on any single sub-stage above `SUBSTAGE_ALARM_CYCLES` (4096). Find the lines with `grep -n "32767U\|INT32_MAX\|SUBSTAGE_ALARM" src/cusum_detector.*`; line numbers are not quoted because they move.

**Impact:** A real security flaw: a glitch that inflates a sub-stage, or a wrapped SysTick difference near 2^32, would give a huge distance that wrapped past zero and escaped detection (fail open).

**Verification:** Host test in [tests/test_firmware_detector.c](tests/test_firmware_detector.c) (compile with `gcc -O1 -I src tests/test_firmware_detector.c src/cusum_detector.c -o tests/test_firmware_detector -lm`): the fixed-point square root stays within 1 LSB over 2 million values; the firmware distance stays within 0.0008 of a floating-point reference on 3 million random inputs wherever the float distance is below 180 (above that, 6,873 of the 3 million, the fixed-point value saturates at 181.02 by design, so the maximum difference over all samples is 26.8); every extreme input tried alarms and the distance saturates at 181.02; 12 decision disagreements with floating point in 3 million inputs, all within 0.0002 of the threshold. The test prints PASS or FAIL and exits non-zero on failure.

## 3. Data

| File | Contents |
|------|----------|
| `data/nominal_boots.csv` | 496 clean boots, 4 checkpoints each (1985 lines with header). 500 collection runs were made; boots 26, 116, 386 and 479 are absent. Probable cause (consistent with the data, not proven): `make collect` runs the halting firmware, so an alarmed boot prints no data block and is dropped. If so, the training set excludes timing spikes by construction (see "False alarms" in Section 2). Re-collected 2026-11-09. |
| `data/attack_boots.csv` | 50 boots with the glitch macro on (`make collect-attack`, built with `-DCOLLECT_MODE` so the detector does not halt and telemetry is still printed). 201 lines with header. Re-collected 2026-11-09. |
| `data/model.npz` | Model for the Python sequential detector, fitted on the CP2 features of `nominal_boots.csv` (496 boots; the 2.5 x IQR outlier filter removed none). Rebuilt 2026-11-09. |

Embedded firmware parameters live only in `src/cusum_detector.c`. `scripts/calibrate_firmware.py` fits them from the same `nominal_boots.csv` (mean and inverse covariance, plus a one-shot threshold, see [FIRMWARE_DETECTOR.md](FIRMWARE_DETECTOR.md)) and they are not copied into any document. The firmware does not read `model.npz`; the sequential `k` and `H` in `model.npz` are used only by the Python simulation.

## 4. Effort

Phase 1 total: **600 hours** (July to November 2026), matching the Phase 1 guideline of about 600 hours over two trimesters.

The breakdown below allocates the 600 hours across the work visible in the repository (source, scripts, data, documents, git history from 2026-07-21). It is an allocation across the work done, not a time log.

| Category | Activity | Hours |
|----------|----------|------:|
| **1. Research and learning** | | **135** |
| | Literature survey (20 papers, survey document) | 60 |
| | Domain learning: secure boot, fault injection, Cortex-M33, TrustZone-M, DWT/SysTick | 40 |
| | Problem formulation and approach design | 20 |
| | Phase 0 proposal preparation and revision | 15 |
| **2. Infrastructure** | | **55** |
| | Toolchain and QEMU setup (QEMU 6.2 UART bug, build of QEMU 8.x) | 25 |
| | Build system, linker script, startup code, UART driver | 20 |
| | Repository, Python environment, script scaffolding | 10 |
| **3. Bootrom firmware** | | **50** |
| | Boot stages, checkpoints, sub-stage timing design | 35 |
| | Glitch-attack macro and feature-design iterations | 15 |
| **4. Statistical pipeline (Python)** | | **120** |
| | Data collection automation and clean-boot runs (including recollections) | 25 |
| | Data quality checks and outlier filtering | 15 |
| | Gaussian model, Mahalanobis distance, threshold calibration | 25 |
| | CUSUM simulation, ROC analysis, k_slack tuning | 30 |
| | Visualisation | 10 |
| | Gaussian-assumption analysis | 15 |
| **5. Firmware detector** | | **85** |
| | Fixed-point (Q16.16) design | 20 |
| | Detector implementation and integer square root | 35 |
| | Calibration script (model to C parameters) | 15 |
| | Integration into boot flow | 15 |
| **6. Debugging** | | **60** |
| | ISSUE-001 SysTick initialisation (data corruption) | 20 |
| | ISSUE-004 ROC calculation | 10 |
| | ISSUE-008 fixed-point square root | 20 |
| | Other (linker errors, pandas indexing, build issues) | 10 |
| **7. Testing and validation** | | **50** |
| | Test script development | 10 |
| | Smoke and integration tests | 10 |
| | 1000-boot validation runs and result analysis | 20 |
| | Manual checks of fixed-point arithmetic | 10 |
| **8. Documentation** | | **30** |
| | Technical documentation and issue tracking | 20 |
| | Code comments and file headers | 5 |
| | READMEs and document consolidation | 5 |
| **9. Project management** | | **15** |
| | Progress tracking and mentor discussions | 10 |
| | Phase 1 review preparation | 5 |
| **Total** | | **600** |

Share of total: research and learning 22.5%, infrastructure 9.2%, bootrom firmware 8.3%, statistical pipeline 20.0%, firmware detector 14.2%, debugging 10.0%, testing and validation 8.3%, documentation 5.0%, project management 2.5% (sums to 100%).

**Note:** The 600 hours above is an allocation across delivered work. An earlier commit message (4b019e3) and archived documents give ~205 hours; the difference reflects untracked early exploration and rework.

AI tool use: Claude Code was used as a development assistant for implementation, debugging and documentation. The hours above are the student's total effort including that assisted work.

## 5. Scope versus the Phase 0 proposal

Proposal: [Phase_0_Proposal.txt](Phase_0_Proposal.txt).

| Proposed | Status | Delivered |
|----------|--------|-----------|
| Simulation environment with scripted fault injection (NOP substitution plugin) | Partial | QEMU plus a compile-time macro that skips a loop. No QEMU plugin. |
| 500 clean boots | Done, with a note | 500 collection runs, 496 boots recorded (4 missing, probably dropped alarm boots; not proven). |
| 10,000 glitched boots at 5 severity levels | Not done | 50 collected boots plus a 1000-boot detection test at a single severity. Five severity levels exist only in the Python simulation. |
| 5-dimensional PMU vectors at 10 checkpoints | Partial | 3-dimensional sub-stage timing vectors, 4 checkpoints, only checkpoint 2 monitored. SysTick is the only counter. |
| CUSUM log-likelihood detector | Done, with a note | Mahalanobis-distance CUSUM. The firmware calls it once per boot, so it acts as a single-observation threshold test. Accumulation across checkpoints is not exercised yet. |
| Formal detection bounds (Stein's Lemma) | Not done | Threshold calibrated empirically. |
| Fixed-point C port (proposed for Phase 2) | Done early | Q16.16, no FPU. |
| BOOTROM integration (proposed for Phase 2) | Done early | Halts boot on alarm. |
| Cycle overhead and latency benchmark (Phase 2) | Partial | Footprint measured (Section 2); latency not measured. |
| TrustZone-M lockout response (Phase 2) | Not done | Infinite loop on alarm. |
| Comparison against redundant execution (Phase 2) | Not done | |

## 6. Limitations

1. **Timing noise.** QEMU host jitter gives a coefficient of variation of about 10%, and the features are not Gaussian ([docs/GAUSSIAN_ASSUMPTION_ANALYSIS.md](docs/GAUSSIAN_ASSUMPTION_ANALYSIS.md)).
2. **QEMU timing does not track executed work.** SysTick follows host time, so partial loop skips do not change `sub_b` proportionally and no firmware severity sweep is possible (Section 2). Only the full-loop fault is detectable in firmware.
3. **Mild glitches are missed.** The Python simulation and the one-shot baselines miss glitches below about 10% severity, and the shipped firmware threshold (H = 10.84) needs roughly a 40 to 50% `sub_b` reduction before it alarms (Section 2, "Sensitivity of the shipped firmware threshold").
4. **Simulated fault.** One macro-based fault; no skip, repeat or register-corruption variants.
5. **One monitored checkpoint.** Attacks on checkpoints 1 and 3 are not covered.
6. **Counter.** SysTick timing, not DWT or PMU event counters.
7. **False alarms from timing spikes.** Two runs with the same threshold show 14 and 9 false alarms per 1000 clean boots (pooled 23 / 2000, about 1%). Each is a large one-sided slowdown of one or two sub-stages (z up to +68.9, MD 11.8 to 171.5 against H = 10.84), likely host pauses of the emulator (unconfirmed). The training set probably excludes such boots (Section 3). See Section 2 and ISSUE-013. Phase 2 will re-measure on hardware.

Open and resolved issues: [KNOWN_ISSUES.md](KNOWN_ISSUES.md) (limitations 2 and 7 are ISSUE-012 and ISSUE-013).

## 7. Phase 2 plan

- Port to STM32L552 and replace SysTick with DWT counters (cycle, CPI, LSU, fold counters).
- Real fault injection (debugger-based, optionally voltage glitching) with several fault models.
- Multi-checkpoint fusion; revisit Stein's Lemma bounds once hardware data is available.
- Comparison against redundant execution; TrustZone-M lockout.
- Larger glitched-boot datasets.

Phase 2 budget per the guidelines: about 400 hours.

## 8. Document map

| Document | Purpose |
|----------|---------|
| [README.md](README.md) | Entry point: setup, build, run, pipeline commands, troubleshooting |
| STATUS.md | This file: results, effort, scope, limitations |
| [FIRMWARE_DETECTOR.md](FIRMWARE_DETECTOR.md) | Detector design and API |
| [PROJECT_GUIDE.md](PROJECT_GUIDE.md) | Pipeline and methodology guide |
| [KNOWN_ISSUES.md](KNOWN_ISSUES.md) | Issue tracker |
| [docs/GAUSSIAN_ASSUMPTION_ANALYSIS.md](docs/GAUSSIAN_ASSUMPTION_ANALYSIS.md) | Non-Gaussianity analysis |
| [review/PPT_OUTLINE.md](review/PPT_OUTLINE.md) | Phase 1 review slide outline |
| [review/DEMO_SCRIPT.md](review/DEMO_SCRIPT.md) | Phase 1 review demo script |
| [review/QA_BACKUP.md](review/QA_BACKUP.md) | Likely panel questions and answers |
| `archive/` | Superseded documents, kept for history (each carries a SUPERSEDED banner) |

The literature survey (`Literature_Survey/COMPREHENSIVE_LITERATURE_SURVEY.md`), the project-level `README.md` and `CLAUDE.md`, and the course guidelines sit one level above this repository and are not part of it.
