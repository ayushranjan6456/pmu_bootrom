# Mahalanobis Detector: When It Worked, When It Failed, What to Use Instead

Numbers come from `scripts/mahalanobis_failure_analysis.py` ([results/mahalanobis_failure_analysis.txt](../results/mahalanobis_failure_analysis.txt)) and `scripts/detector_comparison.py` ([results/detector_comparison.txt](../results/detector_comparison.txt)). All detection and false-alarm figures are held-out unless marked in-sample: the model is fitted on one half of the 300 clean boots of `data/ds1_clean.csv` and scored on the other half (two interleaved and two time-ordered splits). Python floating point, not the firmware's Q16.16.

## 1. Summary

- The Mahalanobis **score** is not the problem. A robust full-covariance fit ranks a faulted boot above a clean boot with AUC 0.97 to 0.98 for all five faults.
- The **one-shot threshold** is the problem. `H = 1.25 x max clean MD` is set by the single most extreme clean boot, and about 14% of the 8-checkpoint clean boots contain an upward timing spike somewhere. Spikes look as extreme to a two-sided distance as a skipped loop does.
- It worked on the frozen 4-checkpoint data because that training set contained no spikes at the monitored checkpoint (0 of 496). Its 1.4% false-alarm rate is mostly spikes in the test boots (11 of the 14 false alarms, section 2).
- It can be partly rescued at **one** checkpoint (spiked boots removed from training, about 2% false alarms). It cannot be extended to all seven checkpoints (about 16% of clean boots alarm).
- A one-sided floor (alarm if a sub-stage falls below a fraction of its clean median) avoids the spike problem and is the recommended detector.

## 2. When it worked: the frozen 4-checkpoint firmware

Monitored checkpoint is CP2 of that firmware (git tag `phase1-review-freeze-2`). Full results in [STATUS.md](../STATUS.md#frozen-firmware-4-checkpoints-tag-phase1-review-freeze-2-firmware-detector-1000-boot-validation).

The key property: that training set contained 0 spiked boots at CP2 (largest is 1.29× median). The covariance was fitted on tight data, so the covariance was small and a skipped loop (about 85% of sub_b) landed far outside it.

Two caveats:
- **The false alarms are spikes.** 11 of the 14 false alarms in the 1000-boot validation have a CP2 sub-stage above 1.5× the training median, so the test boots had spikes at a rate of at least 1.1%. A spike-free training set of 496 boots would be unlikely at that rate (probability 0.4%).
- **Evidence for a selection effect.** An earlier collection of 500 boots from the firmware before the detector existed (commit 051046f) has 5 boots with a CP2 sub-stage above 1.5× the median (3 above 3×). The 496-boot re-collection with the halting firmware has none, and 4 boot ids are absent. This fits the hypothesis that the halting build dropped the spiked boots when the detector alarmed on them. It is not proven.
- **"1000 / 1000" is conditional** on that spike-free training set and on one large fault.

## 3. When it failed: the 8-checkpoint firmware

Training set `data/ds1_clean.csv`, 300 boots, collected with the non-halting build, so nothing was dropped.

### 3.1 Spikes are common

Clean boots with any sub-stage above the multiple of its checkpoint median:

| Multiple | CP1 | CP2 | CP3 | CP4 | CP5 | CP6 | CP7 | Any of CP1-7 |
|----------|----:|----:|----:|----:|----:|----:|----:|-------------:|
| > 1.5x | 4 | 2 | 6 | 10 | 5 | 7 | 9 | 42 of 300 (14%) |
| > 3x | 3 | 1 | 4 | 4 | 2 | 4 | 6 | 24 of 300 (8%) |

### 3.2 The threshold lands above the faults

At CP3, fitted on all 300 clean boots (in-sample): largest clean MD 16.7, so H = 20.9. The attack boots have median MD 3.1 and 90th percentile 3.4. The spikes inflate the fitted spread: CP3 sub_b has a standard deviation of 286 with all boots and 113 without the six boots above 1.5x its median. A fault that removes 89% of sub_b still sits well inside a spread that wide.

Held-out result for the firmware rule (a Gaussian per checkpoint, `H = 1.25 x max`):

| Split | False alarms, CP3 only (of 150) | False alarms, CP1-7 (of 150) | Detections of the five faults (of 300 each) |
|-------|-----:|-----:|----------------------------|
| interleaved A | 1 | 11 | 3, 0, 1, 5, 1 |
| interleaved B | 2 | 17 | 1, 216, 1, 4, 0 |
| time A | 2 | 22 | 3, 3, 184, 5, 10 |
| time B | 0 | 4 | 1, 0, 1, 3, 0 |

Order is attack, FT-1, FT-2, FT-3, FT-4. The detection count also swings (FT-1 is 0 in two splits and 216 in another, FT-2 is 1 in three splits and 184 in another) depending on which half trained, which fits a single spiked boot in the training half deciding the threshold.

### 3.3 Why a two-sided score confuses spikes with faults

At CP3, with a robust (median / MAD) diagonal score, 6 of 300 clean boots score above the median attack boot. They are the spiked boots: an upward excursion in one sub-stage is as many robust sigmas from the median as a skipped loop is in the other direction.

AUC at the faulted checkpoint, mean of 4 splits (0.5 no separation, 1.0 perfect):

| Fault | Full-cov, robust (MCD), two-sided | Diagonal, median/MAD, two-sided | Diagonal, low side only |
|-------|------:|------:|------:|
| attack | 0.980 | 0.980 | 0.999 |
| FT-1 | 0.983 | 0.976 | 0.985 |
| FT-2 | 0.969 | 0.869 | 0.882 |
| FT-3 | 0.971 | 0.974 | 1.000 |
| FT-4 | 0.968 | 0.983 | 1.000 |

The ranking is fine. What fails is choosing a cut-off: the spiked clean boots sit in the same score range as the faulted ones, so any threshold low enough to catch the faults alarms on the spikes.

## 4. Can it be made to work?

Robust fits with a looser threshold, pooled over the 4 held-out splits (600 clean test boots), detection is the worst split of 300:

| Fit | Threshold | False alarms CP3 | False alarms CP1-7 | attack | FT-1 | FT-2 | FT-3 | FT-4 |
|-----|-----------|-----:|-----:|-----:|-----:|-----:|-----:|-----:|
| robust diag | 1.25 x max | 2 | 24 | 0 | 0 | 0 | 1 | 0 |
| robust diag | 97.5th pct | 16 | 112 | 299 | 42 | 1 | 5 | 300 |
| robust MCD | 1.25 x max | 3 | 25 | 1 | 0 | 0 | 2 | 0 |
| robust MCD | 95th pct | 36 | 185 | 300 | 300 | 299 | 300 | 299 |

A robust covariance alone does not help while the threshold is `1.25 x max`. Moving the threshold down recovers detection only by accepting 6% false alarms at CP3 and 31% across CP1-7.

Removing spiked boots from the training set before fitting (the frozen data was effectively in this condition), then `H = 1.25 x max`, full-covariance Gaussian per checkpoint, pooled over 4 splits:

| Boots trimmed if any sub-stage is above | False alarms CP3 (of 600) | False alarms CP1-7 (of 600) | attack | FT-1 | FT-2 | FT-3 | FT-4 | Alarms at untouched checkpoints (of 6000) |
|------|-----:|-----:|-----:|-----:|-----:|-----:|-----:|-----:|
| nothing | 5 | 54 | 1 | 0 | 1 | 3 | 0 | 272 |
| 3.0x median | 11 | 78 | 3 | 3 | 1 | 5 | 1 | 504 |
| 2.0x median | 14 | 87 | 300 | 216 | 292 | 5 | 192 | 625 |
| 1.5x median | 14 | 94 | 300 | 216 | 292 | 300 | 192 | 760 |

Trimming does recover detection once the trim reaches the 1.5x to 3x spikes (a 3x trim leaves them in and changes nothing). At CP3 with a 1.5x trim, the Gaussian detects the attack in every split and FT-2 and FT-3 in at least 292 of 300, with 2.3% false alarms, in line with the frozen 1.4%. The limits:
- **Not extendable to all checkpoints.** Monitoring CP1-7, 94 of 600 clean boots (16%) alarm, because each checkpoint adds its own spike chance. The fusion premise of the original plan (OR of per-checkpoint Gaussian detectors) therefore fails.
- **Weak on FT-1 and FT-4.** Worst split 216 and 192 of 300.
- **Cliff at the trim level.** Trimming at 3x gives 3 of 300, at 2x gives 300 of 300. The behaviour depends on a tuning choice I made after seeing detection results.
- **Needs a false-alarm floor equal to the spike rate.** Spiked boots are still in the test boots.

Conclusion: Mahalanobis is usable only for a single monitored checkpoint with a spike-free training set, accepting a false-alarm rate equal to the spike rate (about 2%). It is not a good fit for multi-checkpoint fusion on this data.

## 5. The better solution: one-sided floor

Rule: alarm if any monitored sub-stage is below `f x` its clean median. A skipped loop only makes the sub-stage shorter, and the median is not moved by upward spikes, so spiked boots do not alarm.

Held-out, `f` from 0.4 to 0.5 (21 sub-stages at CP1-7, [results/detector_comparison.txt](../results/detector_comparison.txt) sections 3 and 3b):

| Quantity | f = 0.4 | f = 0.45 (firmware) | f = 0.5 |
|----------|--------:|--------:|--------:|
| Clean false alarms, CP1-7 (pooled 300 test boots, interleaved and time-ordered pairs) | 0 | 0 | 0 |
| Alarms at untouched checkpoints of the fault builds (of 3000) | 0 | 0 | 0 |
| Worst-split detection of the five faults (of 300) | 298 | 298-300 | 299 |
| Misses per fault, pooled over two splits (of 600) | 0 to 4 | 0-2 (firmware validation) | 0 to 2 |

Synthetic severity sweep, sub_b reduced at CP3, detection by reduction: the f = 0.45 floor (fig 4, results/slide_plots_data.txt) detects 0% at 30%, 26% at 40%, 33% at 50%, 96% at 60%. It catches reductions of about 60% or more reliably and misses those under about 35%.

Cost: about 140 bytes of code at `-O0` for the compare loop, against about 1060 bytes for the current detector (measured ad hoc with `arm-none-eabi-gcc`, not saved in the repository), and 21 small constants, with no multiply, square root or fixed-point arithmetic.

**Firmware validation (f = 0.45, fresh boots):** 0 of 300 clean false alarms, 298-300 of 300 detected on five skipped-loop faults. See [STATUS.md](../STATUS.md#current-firmware-8-checkpoints-validation-on-fresh-boots) and [FAULT_MODELS.md](../FAULT_MODELS.md).

Limits to state when presenting:
- **`f` was chosen after seeing fault data.** The validation set is fresh, but the faults and builds are the same kinds, so it checks the calibration, not the choice of rule.
- **Little headroom above 0.5.** An untouched sub-stage in a fault build ran down to 0.51 of the clean-build median (FT-1 build, CP3). At f = 0.55, 30 of 3000 untouched-checkpoint boots alarm. The cause of the build-to-build difference is not identified (ISSUE-016), so recalibrate the floor table for every firmware build.
- **FT-5 (extra work, +84%) is not covered by the floor.** The Mahalanobis warning catches it (300 of 300). A ceiling at 1.5× median would detect 88% of FT-5 but alarm on 14% of clean boots across the 21 sub-stages.
- **Timer guard untested.** Under heavy CPU load the SysTick wraps or stalls. The firmware has a guard (`timer_ok()`) that rejects inconsistent checkpoints and skips both detectors (fail-open, ISSUE-019); it never fired in validation.

## 6. Lessons

1. The frozen result depended on the training data, not only on the algorithm. Record how the training boots were collected and whether any were dropped.
2. A threshold set by the largest training value is as unstable as the single most extreme training boot.
3. Faults here have a direction (shorter), so a one-sided rule suits them better than a two-sided distance.
4. Per-checkpoint false-alarm rates compound across checkpoints; any fusion design must be tested on the full set of monitored checkpoints, not at one.
