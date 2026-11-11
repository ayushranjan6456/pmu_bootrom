# Gaussian Assumption Analysis

**Issue:** ISSUE-002 - Non-Gaussian Feature Distributions  
**Status:** Documented as Phase 1 Limitation  
**Date:** November 7, 2026

---

## Problem Statement

The CUSUM detector assumes feature vectors follow a **multivariate Gaussian (normal) distribution**. However, statistical tests reveal significant departures from normality in the collected data.

### Evidence

**Shapiro-Wilk Normality Test Results (n=496):**
```
Feature  | W-statistic | p-value  | Assessment
---------|-------------|----------|------------------
sub_a    | 0.9462      | <0.0001  | NON-GAUSSIAN ❌
sub_b    | 0.9463      | <0.0001  | NON-GAUSSIAN ❌
sub_c    | 0.9215      | <0.0001  | NON-GAUSSIAN ❌
```

**Visual Characteristics:**
- Slightly negative skew (-0.11 / -0.14 / -0.24) and negative excess kurtosis (-0.32 / -0.92 / -0.96): flatter than a Gaussian, not heavy-tailed and not right-skewed
- Several peaks in a kernel density estimate: sub_a at about 655, 738 and 933; sub_b at about 543 and 638; sub_c at about 462, 540 and 638 cycles (peak positions are approximate and depend on the smoothing)
- Departure from normality is strongest in sub_c (W = 0.9215)

---

## Root Cause: QEMU Host OS Jitter

### Timing Variance Sources

The bootrom runs in QEMU emulation, where timing measurements include **host OS scheduling effects**:

1. **Context Switches** - Linux scheduler preempts QEMU VM for other processes
2. **CPU Frequency Scaling** - Dynamic voltage/frequency changes mid-boot
3. **Timer Interrupts** - Kernel timer ticks add microsecond-level delays
4. **Cache Effects** - Host cache state affects QEMU translation performance
5. **Virtualization overhead** - if QEMU runs inside a VM or container, the extra layer adds jitter (the 2026-11-10 runs were on native Linux)

### Measured Impact

| Metric | Observed (QEMU) |
|--------|-----------------|
| CV (sub_a) | 8.8% |
| CV (sub_b) | 10.4% |
| CV (sub_c) | 10.0% |

**Interpretation:** QEMU timing noise comes from the host, not from the emulated CPU. On real hardware the same code executes in a fixed number of cycles apart from bus, flash wait-state and interrupt effects, so we **hypothesize** much lower variance (well under 1% CV). This has not been measured; Phase 2 on the STM32L552 is the test. Treat any specific hardware CV figure as a hypothesis until then.

---

## Impact on Detection

### 1. Increased False Alarm Rate

**Theory:** Non-Gaussian tails mean more outliers in clean data.

**Practice:** Firmware false alarm and detection rates are in [STATUS.md](../STATUS.md#2-results). Detection works despite non-Gaussianity.

**Why?** The threshold is set **empirically** from the observed clean Mahalanobis distances (not from a Gaussian quantile), so it accounts for tail behavior.

### 2. Reduced Low-Severity Detection

**Theory:** High noise masks small timing shifts.

**Data:** See [STATUS.md](../STATUS.md#python-simulation-synthetic-attacks) for the current table (4.5% / 86.2% / 99.7% at 5% / 10% / 20% severity).

**Conclusion:** QEMU noise limits detection to **>15% severity** glitches.

### 3. Model Overfitting Risk

**Concern:** Training on 496 samples with high variance → unstable covariance estimate.

**Mitigation:**
- IQR outlier filtering (the 2.5 x IQR filter removed none from the 496-boot dataset)
- Correlation structure is stable (condition number = 33.5)
- Validation: see [STATUS.md](../STATUS.md) for the false alarm rate measured on 1000 clean boots

---

## Theoretical vs. Practical Trade-offs

### Gaussian Assumption Benefits

1. **Analytical tractability** - Mahalanobis distance has clear interpretation
2. **Efficient computation** - Covariance inverse computed once offline
3. **Well-studied theory** - CUSUM optimality proofs for Gaussian case

### Reality: Detection of the large simulated fault works despite non-Gaussianity

The detector works well **despite** non-Gaussianity because:

1. **Empirical calibration:** Threshold set from actual data, not theory
2. **Large effect size:** Glitches cause cycle shifts large against the 60-cycle spread
3. **Conservative threshold:** firmware H (1.25 x the largest clean MD) sits above the whole clean MD range of the training data
4. **No accumulation in firmware:** the firmware tests one boot, so it is a threshold on Mahalanobis distance; only the Python simulation accumulates evidence over a window

**Key Insight:** Gaussian assumption is a **modeling convenience**, not a hard requirement.

---

## Alternative Approaches (Not Implemented)

### 1. Robust Statistics

**Student's t-distribution:**
- Heavier tails accommodate outliers
- Adds 1 parameter (degrees of freedom)
- Marginal benefit for current performance

**Huber M-estimator:**
- Down-weights extreme observations
- More complex computation
- Overkill for embedded context

### 2. Non-Parametric Methods

**Kernel Density Estimation (KDE):**
- No distributional assumption
- Requires storing training data (memory cost)
- Slower inference (distance to all samples)

**Histogram-based:**
- Simple outlier scoring
- Loses multivariate correlation information

### 3. Machine Learning

**One-class SVM:**
- Learns decision boundary from clean data
- Requires float ops, larger memory
- No real-time guarantees

**Autoencoder:**
- Reconstruction error as anomaly score
- Way too heavyweight for bootrom

**Reason for not implementing:** The current approach met the Phase 1 pass criteria (results in [STATUS.md](../STATUS.md)); the added complexity was not justified for Phase 1.

---

## Mitigation Strategies

### Implemented (Phase 1)

1. ✅ **IQR Outlier Filtering** - The 2.5 x IQR filter removed none from the 496-boot dataset
2. ✅ **Empirical Threshold Calibration** - H set from actual S distribution
3. ✅ **Large Training Set** - 496 samples for stable estimation
4. ✅ **Multi-dimensional Features** - Correlation structure reduces false alarms

### Planned (Phase 2 - Hardware)

1. **Real Hardware Timing** - Hypothesis: much lower CV and closer to Gaussian (to be measured)
2. **DWT Counters** - 5D hardware PMU features (more informative)
3. **Longer Boot Stages** - Increase loop iterations for better SNR
4. **Multi-Checkpoint Fusion** - Combine evidence across CP1, CP2, CP3

---

## Experimental Verification

### Test 1: Gaussianity Not Required for Detection

**Hypothesis:** Detector works despite non-Gaussian features.

**Method:** Run clean and glitched boots with the current (non-Gaussian) model.

**Results:** see [STATUS.md](../STATUS.md#2-results) (1000 clean and 1000 glitched boots).

**Conclusion:** Gaussian assumption violation does not prevent detection of the large simulated fault. The pooled firmware false-alarm rate is about 1% (23 / 2000), and all of those alarms are timing spikes (STATUS.md, ISSUE-013). The 1% figure is a measured result for the firmware, not a design target: the firmware threshold is 1.25 x the largest clean MD, not a percentile.

### Test 2: Threshold Robustness

**Hypothesis:** Empirical calibration handles non-Gaussianity.

**Method:** Compare theoretical H (from chi-squared) vs. empirical H (from data).

**Results:**
- Theoretical MD threshold for a Gaussian (sqrt of the χ² 99th percentile, 3 degrees of freedom): 3.37. Applied to the 496 clean boots it flags 3.6% (a Gaussian would give 1%).
- Empirical 99th percentile of the clean MD: 4.88 (flags 1% by construction)
- Largest clean MD: 8.67. The firmware uses H = 1.25 × 8.67 = 10.84, which is above every training boot.
- The firmware's empirical threshold gave a false alarm rate of about 1% on 2000 clean boots (pooled), all from timing spikes ([STATUS.md](../STATUS.md#2-results))

**Conclusion:** Empirical calibration essential for non-Gaussian data.

---

## Recommendations

### For Phase 1 (QEMU)

**Accept limitation and document:**
- ✅ Note non-Gaussianity in thesis methods section
- ✅ Report CV values as data quality metric
- ✅ Emphasize detection works despite assumption violation
- ✅ Cite empirical threshold calibration as mitigation

### For Phase 2 (Hardware)

**Verify Gaussian assumption holds:**
- Collect 1000 boots from STM32L552
- Rerun Shapiro-Wilk tests (hypothesis: p > 0.05)
- Measure CV and compare with the QEMU values above
- Compare QEMU vs. hardware model stability

**If still non-Gaussian on hardware:**
- Investigate hardware-specific noise sources
- Consider robust covariance estimation (MCD)
- Validate detection performance unchanged

---

## Conclusion

**ISSUE-002 Status: Documented as Acceptable Limitation**

The non-Gaussian feature distributions in Phase 1 are a **known artifact of QEMU emulation**, not a fundamental flaw. The detector still meets the Phase 1 pass criteria despite this violation (results: [STATUS.md](../STATUS.md#2-results)) because:

1. Empirical calibration accounts for actual data characteristics
2. Large glitch effects overwhelm distributional details
3. The firmware threshold sits above every clean training boot

**No action required for Phase 1.** Whether hardware removes the non-Gaussianity is a Phase 2 hypothesis, to be tested on the STM32L552.

**Thesis Impact:** Document as limitation, emphasize detection of the large simulated fault works despite non-Gaussianity, note hardware resolution in future work.

---

## References

- Shapiro, S. S., & Wilk, M. B. (1965). "An analysis of variance test for normality"
- Basseville, M., & Nikiforov, I. V. (1993). "Detection of Abrupt Changes: Theory and Application" (CUSUM under non-Gaussian noise)
- Hodge, V., & Austin, J. (2004). "A survey of outlier detection methodologies"

---

**Document Version:** 1.1  
**Author:** Ayush (with Claude Code)  
**Date:** November 7, 2026
