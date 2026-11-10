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
sub_a    | 0.8879      | <0.0001  | NON-GAUSSIAN ❌
sub_b    | 0.8968      | <0.0001  | NON-GAUSSIAN ❌
sub_c    | 0.9509      | <0.0001  | NON-GAUSSIAN ❌
```

**Visual Characteristics:**
- Trimodal with slight negative skew (three peaks at approximately 735, 640, and 540 cycles)
- Heavier tails than expected for Gaussian
- Departure from normality is stronger in sub_a and sub_b than in sub_c

---

## Root Cause: QEMU Host OS Jitter

### Timing Variance Sources

The bootrom runs in QEMU emulation, where timing measurements include **host OS scheduling effects**:

1. **Context Switches** - Linux scheduler preempts QEMU VM for other processes
2. **CPU Frequency Scaling** - Dynamic voltage/frequency changes mid-boot
3. **Timer Interrupts** - Kernel timer ticks add microsecond-level delays
4. **Cache Effects** - Host cache state affects QEMU translation performance
5. **WSL2 Overhead** - Virtualization layer introduces additional jitter

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

**Concern:** Training on 490 samples with high variance → unstable covariance estimate.

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

### Reality: Robust Performance Despite Violation

The detector works well **despite** non-Gaussianity because:

1. **Empirical calibration:** Threshold set from actual data, not theory
2. **Large effect size:** Glitches cause 50-500 cycle shifts (>> noise)
3. **Accumulation:** CUSUM integrates evidence over time, smoothing single-sample noise
4. **Conservative threshold:** firmware H sits well above the clean MD range (margin over the largest clean MD)

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

**Conclusion:** Gaussian assumption violation does not prevent detection of the large simulated fault, at a false alarm rate near the 1% design target.

### Test 2: Threshold Robustness

**Hypothesis:** Empirical calibration handles non-Gaussianity.

**Method:** Compare theoretical H (from chi-squared) vs. empirical H (from data).

**Results:**
- Theoretical H (sqrt(χ² 99th percentile for 3D)): ≈3.37
- Empirical H (99th percentile of actual MD): 8.67 (firmware uses H = 1.25 × 8.67 = 10.84)
- Using theoretical H would give a much higher false alarm rate (not measured)
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
3. CUSUM accumulation smooths single-sample noise

**No action required for Phase 1.** Whether hardware removes the non-Gaussianity is a Phase 2 hypothesis, to be tested on the STM32L552.

**Thesis Impact:** Document as limitation, emphasize robust performance despite it, note hardware resolution in future work.

---

## References

- Shapiro, S. S., & Wilk, M. B. (1965). "An analysis of variance test for normality"
- Basseville, M., & Nikiforov, I. V. (1993). "Detection of Abrupt Changes: Theory and Application" (CUSUM under non-Gaussian noise)
- Hodge, V., & Austin, J. (2004). "A survey of outlier detection methodologies"

---

**Document Version:** 1.0  
**Author:** Ayush (with Claude Code)  
**Date:** November 7, 2026
