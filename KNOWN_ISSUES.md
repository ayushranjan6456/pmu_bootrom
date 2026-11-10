# Known Issues and Technical Debt

**Document Version:** 1.8  
**Date:** November 10, 2026  
**Build:** Phase 1 freeze (see STATUS.md)  

This document tracks identified issues, their impact, root causes, and planned remediation. Issues are categorized by severity and implementation phase.

---

## Critical Issues (Block Production Use)

### ISSUE-001: High Data Corruption Rate (37%)

**Status:** ✅ RESOLVED  
**Severity:** Critical  
**Component:** Firmware - SysTick timer initialization  
**Discovered:** 2026-11-07 during first data collection  
**Resolved:** 2026-11-07

**Symptoms:**
- 185 out of 500 boots (37%) flagged as corrupt and removed
- CP0 elapsed = 16777215 (0xFFFFFF) - SysTick max value
- CP1 sub_a values like 4278192042 (0xFF00xxxx) - uint32 underflow

**Root Cause:**
```c
// In src/main.c, systick_init():
void systick_init(void) {
    SYST_RVR = 0x00FFFFFF;          // Set reload value
    SYST_CVR = 0;                   // ❌ Writing 0 loads RVR!
    SYST_CSR = SYST_CLKSRC | SYST_ENABLE;
    while (SYST_CVR == 0);          // Wait, but CVR is now 0xFFFFFF
}
```

**Explanation:**
Per ARM Cortex-M documentation, writing ANY value to SYST_CVR (Current Value Register) clears it and loads SYST_RVR. So:
1. Write 0 to SYST_CVR → loads 0xFFFFFF from RVR
2. First `systick_elapsed()` reads 0xFFFFFF
3. Subtraction: 0xFFFFFF - 0xFFFFFF = 0 (looks OK for CP0)
4. But stage timing: t1 - t0 where t0=0xFFFFFF causes uint32 underflow

**Impact:**
- Only 315 usable boots instead of 500 (63% yield)
- Wastes collection time (~3 minutes lost per 500 boots)
- Reduces statistical power of model

**Proposed Fix:**
```c
void systick_init(void) {
    SYST_RVR = 0x00FFFFFF;
    SYST_CVR = 1;  // Write any value to clear, but not 0
    SYST_CSR = SYST_CLKSRC | SYST_ENABLE;
    // No need to wait - timer starts immediately
}
```

**Fix Applied:**
1. Reordered `systick_init()` to enable timer before writing CVR (src/main.c:50-56)
2. Removed manual `SYST_CVR = 0;` reset in main() before CP0 (src/main.c:208-212)
3. Accept UART init overhead in CP0 baseline (consistent across boots)

**Results:**
- Before: 500 boots → 185 corrupt (37%) → 315 usable (63% yield)
- After: 500 boots → 0 corrupt (0%) → 496 usable (99% yield; four ids absent, see STATUS.md Section 3)
- Improvement: **36% increase in data quality**

**Verification:**
```bash
grep -c '16777215' data/nominal_boots.csv  # Returns: 0
wc -l data/nominal_boots.csv               # Returns: 1985 (header + 496×4)
```

**Priority:** ✅ Complete  
**Effort:** 20 hours (diagnosis + fix + validation; see STATUS.md)

---

### ISSUE-002: Non-Gaussian Feature Distributions

**Status:** 📋 DOCUMENTED  
**Severity:** Medium (does not prevent detection)  
**Component:** System - QEMU host OS jitter  
**Discovered:** 2026-11-07 during model fitting  
**Documented:** 2026-11-07

**Symptoms:**
```
Shapiro-Wilk normality test:
  sub_a: W=0.9462  p=2e-12   [NON-GAUSSIAN]
  sub_b: W=0.9463  p=2e-12   [NON-GAUSSIAN]
  sub_c: W=0.9215  p=2e-15   [NON-GAUSSIAN]
```

(496 clean CP2 boots.) Skew is slightly negative (-0.11, -0.14, -0.24) and excess kurtosis is negative (-0.32, -0.92, -0.96): the distributions are flatter and multi-peaked, not right-skewed and not heavy-tailed.

**Root Cause:**
Host OS scheduling jitter during QEMU execution:
- Background processes preempt QEMU VM
- CPU frequency scaling changes clock speed
- Timer interrupts add microsecond-level delays
- Any virtualization layer under the host (the 2026-11-10 runs were on native Linux)

**Impact:**
- Gaussian model assumption violated (theoretical foundation weakened)
- Increases false alarm rate in tails of distribution
- Reduces detection performance at low severities (5-10%)
- CV (coefficient of variation) = 11% instead of target <1%

**Data (from 496-boot dataset):**
```
mu[0] sub_a: 695.44  sigma: 61.05  CV: 8.8%
mu[1] sub_b: 582.65  sigma: 60.71  CV: 10.4%
mu[2] sub_c: 501.77  sigma: 50.39  CV: 10.0%
Condition number: 33.5
```

**Proposed Solutions:**

1. **Short-term:** Use robust statistics
   - Replace Gaussian with a mixture model (the features are multi-peaked and flatter than Gaussian)
   - Use robust covariance estimation (Minimum Covariance Determinant)
   - Apply Box-Cox transformation to normalize skew
   
2. **Medium-term:** Reduce jitter
   - Run QEMU with real-time priority: `chrt -r 99 qemu-system-arm ...`
   - Disable CPU frequency scaling: `cpupower frequency-set -g performance`
   - Close background applications during collection
   - Use taskset to pin QEMU to dedicated CPU cores
   
3. **Long-term:** Hardware validation
   - Collect data from real ARM Cortex-M33 dev board
   - Use dedicated timing counter (DWT) instead of SysTick
   - Hypothesis: lower CV on real hardware (to be measured)

**Analysis Complete:**
Comprehensive analysis document created: [docs/GAUSSIAN_ASSUMPTION_ANALYSIS.md](docs/GAUSSIAN_ASSUMPTION_ANALYSIS.md)

**Key Findings:**
1. Non-Gaussianity is attributed to QEMU host OS jitter (cause not isolated; hardware is expected to be cleaner, a hypothesis not yet measured)
2. Detector still works despite the assumption violation (results: [STATUS.md](STATUS.md))
3. Empirical threshold calibration mitigates distributional mismatch
4. Low-severity detection limited (5-10% glitches missed due to noise)

**Mitigation Applied:**
- ✅ IQR outlier filtering (the 2.5 x IQR filter removed none from the 496-boot dataset)
- ✅ Empirical threshold from actual S distribution
- ✅ Large training set (496 samples)
- ✅ Multi-dimensional features for robustness

**Phase 2 Resolution:**
Hardware validation (STM32L552) will test the hypothesis that variance is much lower and distributions closer to Gaussian.

**Priority:** 📋 Documented - No action needed for Phase 1  
**Effort:** 15 hours (analysis + documentation; see STATUS.md)

---

### ISSUE-003: Poor Low-Severity Detection Performance

**Status:** 🟡 Open  
**Severity:** Medium  
**Component:** Algorithm - CUSUM sensitivity  
**Discovered:** 2026-11-07 during detector simulation

**Symptoms:**
See [STATUS.md](STATUS.md#python-simulation-synthetic-attacks) for the current table (4.5% / 86.2% / 99.7% at 5% / 10% / 20% severity).

Detector fails to catch subtle attacks (5-10% timing shifts).

**Root Cause:**
Signal-to-noise ratio problem:
```
5% severity shift  = 0.05 × 555 = 28 cycles
Noise (1σ)         = 63 cycles
SNR                = 28/63 = 0.44 (very poor)

20% severity shift = 0.20 × 555 = 111 cycles
SNR                = 111/63 = 1.75 (good)
```

At 5% severity, the signal is **smaller than the noise**.

**Impact:**
- Cannot detect sophisticated attacks with minimal timing footprint
- Attacker could use weaker glitch that only skips 1-2 iterations
- Detection threshold set by noise floor, not by attacker capability

**Proposed Solutions:**

1. **Reduce noise** (see ISSUE-002)
2. **Increase signal:** Longer boot stages
   - More loop iterations → larger absolute shift
   - Example: 3000 iterations instead of 300
   - 5% of 3000 = 150 cycles (2.4σ above noise)
   
3. **Multi-checkpoint fusion:**
   - Combine evidence from CP1, CP2, CP3
   - Even if each individually weak, joint probability strong
   - Requires fitting 3 separate models
   
4. **Adaptive thresholding:**
   - Lower H for high-value targets (key derivation)
   - Accept higher false alarms on critical stages

**Workaround (Current):**
Acceptable performance at 20%+ severity is sufficient for proof-of-concept.

**Update 2026-11-10 (baseline comparison):** `scripts/baseline_comparison.py` compares one-shot detectors at a 1% false alarm calibration. Mahalanobis on three features beats a `sub_b` threshold from about 20% severity (71.6% against 48.3%), but a `sub_b` threshold is better at 5 to 10% (16.2% against 5.5% at 10%). A multivariate model does not fix the weakest faults; more signal or hardware timing is needed. Table: [STATUS.md](STATUS.md#2-results).

**Priority:** P2 - Phase 2 enhancement  
**Effort:** 40 hours (multi-checkpoint detector)

---

## High Priority Issues

### ISSUE-004: ROC AUC Reported as 0.4988 (Near 1 Expected)

**Status:** ✅ RESOLVED  
**Severity:** High (incorrect metric, revealed fundamental bug in ROC calculation)  
**Component:** Analysis - ROC curve calculation logic  
**Discovered:** 2026-11-07 during detector evaluation  
**Resolved:** 2026-11-07

**Symptoms:**
Terminal output showed:
```
AUC (severity=20%) = 0.4988
```

This suggested random performance (AUC=0.5), contradicting the high detection rate at a single operating point.

**Root Cause:**
The ROC loop was testing on **mixed streams** (10 nominal + 10 glitch boots) for both detection and false alarm rates. This is fundamentally wrong:

**Incorrect logic (`cusum_detector.py` lines 164-177):**
```python
for H in H_values:
    for _ in range(N_ROC):
        stream = make_glitch_stream(...)  # 10 nominal + 10 glitch
        alarm, _, _ = run_cusum(stream, ...)
        if alarm >= N_NOMINAL:     # Alarm in glitch region
            det_count += 1
        elif alarm != -1:          # Alarm in nominal lead-in
            fa_count += 1
```

This conflates "early alarm before glitch" with "false alarm on clean data". The FA rate measured alarms during the nominal lead-in period of **attack sequences**, not alarms on **pure nominal sequences**.

**Result:** When H is low, alarms fire early (positions 0-9) on attack sequences, inflating FA count. When H is high, no alarms fire at all, reducing both det and FA. This creates a diagonal ROC curve (AUC ≈ 0.5).

**Correct ROC Methodology:**
- **Detection rate:** Test on attack sequences → any alarm = detection
- **False alarm rate:** Test on **pure nominal** sequences → any alarm = false alarm

**Fix Applied:**
```python
for H in H_values:
    for _ in range(N_ROC):
        # Test detection on attack sequences
        stream_attack = make_glitch_stream(..., severity=0.20)
        alarm = run_cusum(stream_attack, ...)
        if alarm != -1:
            det_count += 1
        
        # Test FA on pure nominal sequences (NO glitch)
        stream_nominal = make_glitch_stream(..., severity=0.0, n_glitch=0)
        alarm_nom = run_cusum(stream_nominal, ...)
        if alarm_nom != -1:
            fa_count += 1
```

Also removed `abs()` from AUC display (lines 187, 246) which was masking negative values.

**Diagnosis Process:**
1. Created `debug_roc.py` with simplified CUSUM → got AUC near 1 
2. Compared with main script → got AUC=0.5
3. Identified difference: debug script tested on separate nominal/attack streams
4. Realized main script was conflating "early alarm" with "false alarm"

**Impact:**
- **Fundamental bug** - ROC curve was measuring wrong thing
- Detector performance was still correct at single operating point (H=H_99)
- But ROC sweep was meaningless for threshold selection

**Verification:**
After fix, `python scripts/cusum_detector.py` shows:
```
AUC (severity=20%) = 0.9933   (current data; the first fixed run printed 1.0000 on the earlier dataset)
```

Perfect discrimination: detector can separate attack from nominal at all threshold values.

**Priority:** ✅ Complete  
**Effort:** 10 hours (diagnostic + fix + verification; see STATUS.md)

---

### ISSUE-005: Limited Sample Size

**Status:** ✅ RESOLVED  
**Severity:** Medium  
**Component:** Data collection  
**Discovered:** 2026-11-07  
**Resolved:** 2026-11-07

**Original Problem:**
- Started with 500 boots
- After corruption removal: 315 boots (63% yield)
- After IQR filtering: 312 boots (62% yield)
- Statistical power reduced

**Resolution:**
Fixed ISSUE-001 (SysTick bug), then recollected:
- Collected: 500 boots
- After corruption removal: 500 boots (100% yield!) ✅
- After IQR filtering: 496 boots (the filter removed none) ✅

**Results:**
| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Collection yield | 63% | 99% (496 of 500) | +36% |
| Usable samples | 312 | 496 | +59% |

**Statistical Impact:**
- Covariance condition number: 33.5 (stable)
- Sufficient for Gaussian estimation (rule of thumb: n > 10×d = 30 for 3D)

**Priority:** ✅ Complete  
**Effort:** 15 minutes (recollection after SysTick fix)

---

## Medium Priority Issues

### ISSUE-006: High Feature Correlation (0.91 between sub_a and sub_b)

**Status:** 🟢 Open - By Design  
**Severity:** Low  
**Component:** Feature engineering  
**Discovered:** 2026-11-07

**Symptoms:**
```
Correlation matrix:
[[1.000  0.913  0.761]
 [0.913  1.000  0.780]
 [0.761  0.780  1.000]]
```

sub_a and sub_b are 91% correlated.

**Root Cause:**
Both sub-stages affected by common factors:
- Same boot iteration (QEMU VM state)
- Sequential execution (shared cache state)
- Similar instruction mix (loops with arithmetic)

**Impact:**
- Features are somewhat redundant
- Could reduce to 2D feature space with PCA
- Doesn't harm detection (Mahalanobis accounts for correlation)
- Makes model more stable (condition number = 27)

**Analysis:**
This is **not a bug**, but a characteristic of the workload. High correlation means timing variance is systematic (affects all stages similarly), which actually helps detection because glitches are localized.

**Action:** Document, no fix needed  
**Priority:** P3 - Monitor, do not fix

---

### ISSUE-007: Attack Simulation Uses Python Perturbation

**Status:** 🟡 Open  
**Severity:** Medium  
**Component:** Testing methodology  
**Discovered:** Design phase (July 2026)

**Symptoms:**
`cusum_detector.py` generates synthetic attacks by:
```python
X_glitch[:, 1] -= (severity * mu[1])  # Python subtraction
```

Instead of real fault injection during QEMU execution.

**Impact:**
- Not testing firmware's response to real glitch
- Assumes glitch affects only sub_b (might affect others)
- Cannot validate firmware detector (only Python detector)
- Published results are "simulation of simulation"

**Proposed Solution:**
Implement QEMU TCG (Tiny Code Generator) plugin for instruction-level fault injection:
- Hook into instruction execution at specific PC
- Replace instruction with NOP (skip)
- Corrupt register values
- Inject at randomized cycle counts

Planned work: see [STATUS.md](STATUS.md#7-phase-2-plan).

**Workaround (Current):**
`cusum_detector2.py` tests on real firmware attack data (`#ifdef GLITCH_ATTACK`), which validates the approach partially.

**Priority:** P2 - Phase 2. Not completed in Phase 1: a compile-time macro (`-DGLITCH_ATTACK`, optionally `-DGLITCH_SKIP_PCT`) stands in for the plugin; see the scope table in [STATUS.md](STATUS.md#5-scope-versus-the-phase-0-proposal).  
**Effort:** 60 hours

---

### ISSUE-008: No Firmware-Embedded Detector

**Status:** ✅ RESOLVED  
**Severity:** Critical (Phase 1 Blocking)  
**Component:** Firmware implementation  
**Discovered:** Design phase (July 2026)  
**Resolved:** 2026-11-07

**Symptoms:**
- Detector exists only in Python (`scripts/cusum_detector.py`)
- Firmware has no detection logic
- No alarm mechanism in bootrom
- Detection happens offline after data collection

**Impact:**
- Cannot demonstrate real-time detection
- Thesis contribution is incomplete
- No embedded response (halt boot, zero keys)
- Phase 1 review will flag this as critical gap

**Implementation Completed:**

**Files Created:**
- `src/cusum_detector.h` - API and data structures (150 lines)
- `src/cusum_detector.c` - Fixed-point implementation (250 lines)
- `scripts/calibrate_firmware.py` - Model training pipeline (150 lines)
- `scripts/test_firmware_detector.sh` - Automated test suite (80 lines)
- `FIRMWARE_DETECTOR.md` - Complete documentation

**Key Features:**
- Fixed-point Q16.16 arithmetic (no floating-point)
- Mahalanobis distance calculation with covariance matrix
- CUSUM sequential change detection
- Real-time alarm mechanism (halts boot on detection)
- Automatic model calibration from clean data

**Critical Bug Fixed:**
Two square-root bugs were found.
1. The integer square root mishandled Q16.16 format, so MD always returned 0. A first fix took the integer part before the root (`sqrt(x >> 16) << 16`).
2. That fix dropped the fractional part of the distance, so an MD of 15.5 to 16.0 was rounded down below the alarm threshold (about 15.4 at the time) and could slip through. `fixed_sqrt` now computes the root of `x << 16` in 64-bit with a division-free bit-by-bit method and keeps the fraction. `results/validation_1000_before_sqrt_fix.log` is the run before this change; the later logs are after it (history table in [STATUS.md](STATUS.md#2-results)).

**Test Results:** see [STATUS.md](STATUS.md#2-results) (1000-boot validation). Latency and memory figures are unmeasured estimates.

**Integration:**
Detector runs after CP2 (signature verify stage). On alarm:
```c
if (cusum_update(&detector, cp2_features, 2)) {
    uart_println("!!! ATTACK DETECTED at CP2 !!!");
    while (1);  // Halt boot
}
```

**Priority:** ✅ Complete  
**Effort:** 20 hours for the square-root debugging; implementation effort is under "Firmware detector" in STATUS.md

---

## Low Priority Issues / Future Enhancements

### ISSUE-009: Single Checkpoint Monitoring

**Status:** 🟢 Open  
**Severity:** Low  
**Component:** Coverage  

**Description:**
Currently only monitors CP2 (signature verify). Attacker could target CP1 (memory) or CP3 (key derivation).

**Solution:** Multi-checkpoint detector (see ISSUE-003)  
**Priority:** P2 - Phase 2  
**Effort:** 50 hours

---

### ISSUE-010: QEMU-Only Validation

**Status:** 🟢 Open  
**Severity:** Low  
**Component:** Validation methodology  

**Description:**
No hardware validation. QEMU timing doesn't match real Cortex-M33 (no cache, no pipeline effects).

**Solution:** Hardware validation campaign  
**Priority:** P2 - Phase 2  
**Effort:** 80 hours

---

### ISSUE-011: Fixed Attack Model

**Status:** 🟢 Open  
**Severity:** Low  
**Component:** Testing coverage  

**Description:**
Only tests one attack: early loop break in sub_b. Real attackers use skip, repeat, flush, register corruption.

**Update 2026-11-10:** the attack macro now takes `-DGLITCH_SKIP_PCT=<n>` to skip part of the loop, but this does not add a second fault model, and in QEMU partial skips are not detectable (ISSUE-012).

**Solution:** Three glitch models (skip/repeat/flush)  
**Priority:** P2 - Phase 2  
**Effort:** 40 hours

---

## Issues Found During Final Phase 1 Validation (2026-11-10)

### ISSUE-012: QEMU Timing Does Not Track Executed Work

**Status:** 🟡 Open (documented as a Phase 1 limitation)  
**Severity:** Medium  
**Component:** Platform (QEMU SysTick)  
**Discovered:** 2026-11-10 during the partial-severity sweep

**Symptoms:**
Skipping part of the sub-stage B loop (`-DGLITCH_SKIP_PCT`, driven by `scripts/severity_sweep.sh`) does not change `sub_b` in proportion. N=20 per setting, QEMU 8.2.2, raw output in `results/severity_sweep.log`; loop bound confirmed in the disassembly:

The table is in [STATUS.md](STATUS.md#firmware-partial-severity-sweep-not-possible-with-qemu-timing) (single copy, run 2026-11-10T13:15:04+05:30 on an idle machine). In short: the median `sub_b` is 600 to 627 cycles for 0 to 99% skip and drops to 93 when the loop is removed completely (about 84% reduction against the clean mean of 582.7 from `nominal_boots.csv`). No non-glitch boot (0 of 120) was detected in that run.

**Likely cause (not confirmed):**
SysTick in QEMU follows host time, not executed instructions, so the measured cycles are dominated by a roughly fixed cost (for example first-time translation of the loop block) and not by per-iteration work. This also fits the host-jitter noise in ISSUE-002.

**Alternatives considered:**
1. QEMU `-icount shift=0,sleep=off` makes `sub_b` exact and linear (78, 39, 1, 0 at 0, 50, 99, 100% skip, identical on 6 boots each), but clean boots then have zero variance and the covariance matrix is singular. The Mahalanobis detector would need an artificial noise floor and would no longer match the 1000-boot validation.
2. Make sub-stage B heavier so wall-clock time scales with iterations. It keeps real noise but requires re-collecting the clean data, refitting the model and repeating the validation.
3. Keep wall-clock timing and report the limitation (chosen for Phase 1).

**Impact:**
The 1000-boot validation (full-loop fault) stands, but there is no firmware detection-versus-severity curve. The severity curve comes only from the Python simulation.

**Resolution plan:** repeat the sweep on STM32L552 with DWT counters (Phase 2).  
**Priority:** P2 - Phase 2  
**Effort:** not estimated

---

### ISSUE-013: False Alarms in the Validation (Timing Spikes)

**Status:** 📋 DOCUMENTED (mechanism characterised, root cause unconfirmed; Phase 2 resolution on hardware)  
**Severity:** Medium  
**Component:** Validation  
**Discovered:** 2026-11-09; characterised 2026-11-10

**Symptoms:**
Two runs with the same threshold show 14 and 9 false alarms per 1000 clean boots (pooled 23 / 2000, about 1%; the difference between the runs is not significant, Fisher p = 0.40). Tables and analysis: [STATUS.md](STATUS.md#false-alarms-in-the-1000-boot-validation).

**Mechanism:**
Each false alarm is a large one-sided slowdown of one or two sub-stages. Normal variation moves all three sub-stages together (correlation about 0.9); a spike in one sub-stage breaks that pattern and the Mahalanobis distance jumps. The detector is working as designed on a corrupted timing signal.

**Hypothesis (not confirmed):**
SysTick in QEMU follows host time, not executed instructions (ISSUE-012). A host pause mid-boot shows up as an inflated sub-stage.

**Evidence:**
- All 23 alarms have at least one sub-stage above the training maximum. The largest sub-stage z-score runs from +5.2 to +68.9 and the MD from 11.8 to 171.5 against H = 10.84.
- All deviations are slowdowns; the lowest `sub_b` z-score across the 23 is -0.5, whereas the simulated glitch drops `sub_b` to about 15% of its clean value.
- Timing spikes also occur in the training data at CP1 and CP3 (7 of 496 boots, up to `sub_b` = 4653) but not at CP2. At 23 / 2000 the chance of no CP2 spike in 496 boots is about 0.3%.

**Probable selection effect (consistent with the data, not proven):**
`make collect` runs the halting firmware, so an alarmed boot prints no data block and is dropped; the four absent ids (26, 116, 386, 479) are probably such boots. If so, the training set was filtered by the detector, and the 1.25x margin was fitted to a sample without spikes. Test: collect with a non-halting build and compare.

**Consequence for the detector:**
These are timing spikes and not a calibration problem; raising H would not remove the large ones (MD up to 171, against 19 to 32 for the real glitch). A signed rule that alarms only on a low `sub_b` would not have alarmed on any of the 23, but this is untested.

**Instrumentation (2026-11-10):**
On alarm the firmware prints an `ALARM_FEATURES,<sub_a>,<sub_b>,<sub_c>` line, and `scripts/test_firmware_detector.sh` appends each false alarm to `results/false_alarms.csv` and saves its full output as `results/false_alarms/boot_<i>.txt`. The script clears that folder at the start of every run, so copy it after the full run before starting any other test.

**Phase 2 mitigation:**
On hardware the DWT counters measure executed work, not wall-clock time, so a host stall cannot inflate them. Re-measure the false-alarm rate on the STM32L552. If hardware also shows spikes, options are a fault-versus-stall discriminator (the real glitch is a drop in `sub_b`, the false alarms are slowdowns) or a repeat-confirm rule (two consecutive alarms; adds latency, so an option and not the plan).

**Priority:** P2 - Phase 2 (hardware measurement)  
**Effort:** documented

---

### ISSUE-014: Fixed-Point Overflow Bug (Fail-Open for Large MD)

**Status:** ✅ RESOLVED  
**Severity:** High (security flaw: detector fails open)  
**Component:** Firmware - fixed-point arithmetic  
**Discovered:** 2026-11-10 while reviewing extreme-input handling (not by a failing test)  
**Resolved:** 2026-11-10

**Symptoms:**
The squared Mahalanobis distance `q = (x-μ)' Σ⁻¹ (x-μ)` is computed as a 64-bit intermediate and then narrowed to Q16.16 (`int32_t`). When `q >= 32768` (MD >= 181.02), the narrowing wrapped, clamped to zero, and `fixed_sqrt(0)` returned zero → the detector failed open (large distances reported as zero, no alarm).

**Root Cause:**
In `src/cusum_detector.c`, the 64-bit `q_int64` is right-shifted by 16 bits to convert from Q32.32 to Q16.16:
```c
int64_t q64 = q_int64 >> 16;
fixed_t q_fixed = (fixed_t)q64;  // Narrowing cast, unchecked
```

When `q64 > INT32_MAX` (2,147,483,647 in Q16.16 = 32768.0), the cast wraps and the subsequent clamp to zero logic (`if (q_fixed < 0) q_fixed = 0;`) incorrectly zeros out the value.

**Impact:**
A real security flaw (fail open). The datasets do not exercise it: the largest sub-stage in the clean data at checkpoint 2, the only checkpoint the detector scores, is 934 cycles (checkpoints 1 and 3 reach 4,653 and 3,293 in a few spiky boots but are not scored), and the glitched boots only shorten `sub_b`.

**Verification:**
Host test in [tests/test_firmware_detector.c](tests/test_firmware_detector.c): the fixed-point square root stays within 1 LSB over 2 million values; the firmware distance stays within 0.0008 of a floating-point reference on 3 million random inputs wherever the float distance is below 180 (above that the fixed-point value saturates at 181.02 by design, so the maximum difference over all samples is 26.8); every extreme input tried alarms and the distance saturates at 181.02; 12 decision disagreements with floating point in 3 million inputs, all within 0.0002 of the threshold.

**Priority:** ✅ Complete (fixed, verified, documented)  
**Effort:** included in the firmware detector and debugging hours (see STATUS.md)

---

## Issue Statistics

**Total Issues:** 14  
**Resolved:** 5 (ISSUE-001, ISSUE-004, ISSUE-005, ISSUE-008, ISSUE-014)  
**Documented limitation:** 2 (ISSUE-002, ISSUE-013)  
**Open:** 7 (ISSUE-003, ISSUE-006, ISSUE-007, ISSUE-009, ISSUE-010, ISSUE-011, ISSUE-012)

**By severity (open and documented):**
- **Medium:** ISSUE-002, ISSUE-003, ISSUE-007, ISSUE-009, ISSUE-012, ISSUE-013
- **Low:** ISSUE-006, ISSUE-010, ISSUE-011

**Phase 1 blockers:** ISSUE-001, ISSUE-004, ISSUE-008 and ISSUE-014 are fixed. Remaining items are limitations stated in STATUS.md Section 6.

---

## Next Actions

See [STATUS.md](STATUS.md) Sections 6 and 7 for the limitations and the Phase 2 plan. Open work that matters for the review: collect training data with a non-halting build to test the selection effect (ISSUE-013), measure the latency of `cusum_update`, and save missed attacks in the validation harness.

---

## Revision History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2026-11-07 | Initial document, 11 issues identified | System |
| 1.1 | 2026-11-07 | ISSUE-001 resolved (SysTick corruption) | System |
| 1.2 | 2026-11-07 | ISSUE-004 resolved (ROC AUC calculation) | System |
| 1.3 | 2026-11-07 | ISSUE-008 resolved (firmware CUSUM detector) | System |
| 1.4 | 2026-11-07 | Phase 1 blockers complete, statistics updated | System |
| 1.5 | 2026-11-10 | ISSUE-008 second sqrt fix; ISSUE-003 baseline update; ISSUE-007 and ISSUE-011 updated; ISSUE-012 and ISSUE-013 added | System |
| 1.6 | 2026-11-10 | ISSUE-013 documented (mechanism, Phase 2 resolution); ISSUE-014 added and resolved (overflow bug); dataset size 496; condition number 33.5 | System |
| 1.7 | 2026-11-10 | Corrections after external audit: Shapiro-Wilk and skew values, false-alarm ranges (23 alarms), selection-effect note, sweep table moved to STATUS.md, stale counts and code-line references removed | System |
| 1.8 | 2026-11-10 | ISSUE-012 refreshed from the isolated 13:15 sweep (the overlapping 12:23 run is not used); ISSUE-014 clean-data maximum qualified as checkpoint 2; host test in the repo | System |

---

## References

- [STATUS.md](STATUS.md) - results, effort, scope
- [PROJECT_GUIDE.md](PROJECT_GUIDE.md) - Pipeline and methodology guide
- `scripts/build_model.py` - Data cleaning and model fitting
- `scripts/cusum_detector.py` - Detector implementation
