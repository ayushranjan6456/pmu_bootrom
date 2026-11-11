# Firmware-Embedded CUSUM Detector

**Status:** Implemented (Phase 1)  
**Date:** 2026-11-10  
**Files:** `src/cusum_detector.{h,c}`, integrated in `src/main.c`

## Overview

Firmware-embedded fault injection detector that runs once per boot after checkpoint 2; one CUSUM update, so a one-shot threshold on Mahalanobis distance. Detects timing anomalies caused by voltage/clock glitch attacks.

**Key point:** The detector runs **during boot**, not offline. Results are in [STATUS.md](STATUS.md).

## Architecture

### Data Flow
```
Boot Stage → Timing Checkpoint (SysTick) → Feature Vector → CUSUM Update → Alarm?
                                               ↓                  ↓
                                        [sub_a, sub_b, sub_c]   S > H?
                                               ↓                  ↓
                                        Mahalanobis Distance   YES → HALT BOOT
                                                               NO  → Continue
```

### Files

**`src/cusum_detector.h`** - API and data structures
- Fixed-point Q16.16 arithmetic (no floats)
- `cusum_model_t`: Embedded parameters (μ, Σ⁻¹, k, H)
- `cusum_state_t`: Runtime state (S statistic, alarm flag)
- API: `cusum_init()`, `cusum_update()`, `mahalanobis_distance()`

**`src/cusum_detector.c`** - Implementation
- Fixed-point sqrt (division-free bit-by-bit 64-bit integer square root; keeps the fractional part; no libgcc)
- Mahalanobis distance: `MD = sqrt((x-μ)' Σ⁻¹ (x-μ))`
- CUSUM update: `S = max(0, S + MD - k)`
- Alarm check: `S > H`

**`src/main.c`** - Integration
- Detector initialized at boot start
- Checks CP2 (signature verify - primary attack target)
- Halts boot if alarm fires

## Fixed-Point Arithmetic

Uses Q16.16 format (signed 32-bit):
- 16 bits integer, 16 bits fractional
- Range: -32768.0 to +32767.99998
- Precision: 1/65536 ≈ 0.000015

**Why no floats?**
- Cortex-M33 has no FPU in this config
- Float ops require soft-float library (large)
- No FPU needed with fixed-point

**Example:**
```c
fixed_t a = FLOAT_TO_FIXED(1.5);    // 98304 = 0x00018000
fixed_t b = FLOAT_TO_FIXED(2.0);    // 131072 = 0x00020000
// There is no multiply helper: products are widened to 64 bits and shifted
fixed_t c = (fixed_t)(((int64_t)a * (int64_t)b) >> 16);  // 196608 = 0x00030000 = 3.0
```

**Overflow fix (2026-11-10):**
The squared Mahalanobis distance `q = (x-μ)' Σ⁻¹ (x-μ)` is computed as a 64-bit intermediate and then narrowed to Q16.16. When `q >= 32768` (MD >= 181.02), the narrowing wrapped and the detector failed open (large distances reported as zero). The fix: clamp observations to 32767 before computing the delta, and saturate the 64-bit `q` to `INT32_MAX` before narrowing. See [KNOWN_ISSUES.md](KNOWN_ISSUES.md) ISSUE-014 and [STATUS.md](STATUS.md#resource-footprint-measured-and-latency-not-yet-measured) for details.

## Model Calibration

### Training Process

1. **Collect nominal boots** (500 samples):
   ```bash
   make collect
   ```

2. **Filter outliers** (IQR method, 2.5×):
   ```bash
   python scripts/calibrate_firmware.py
   ```

3. **Embed parameters:** paste the C code printed by `calibrate_firmware.py` into `CUSUM_MODEL` in `src/cusum_detector.c`. That constant is the only place the model values are recorded.

4. **Rebuild** firmware:
   ```bash
   make clean && make all
   ```

### Parameters

| Parameter | Meaning |
|-----------|---------|
| **μ** | Mean cycle counts [sub_a, sub_b, sub_c] |
| **Σ⁻¹** | Inverse covariance from clean boots |
| **k_slack** | CUSUM slack. Set to 0 by `calibrate_firmware.py` because the detector runs once per boot. |
| **H** | Alarm threshold. Set to 1.25 x the largest clean-boot Mahalanobis distance. With k_slack = 0 the alarm fires when MD > H. |

Values: see `CUSUM_MODEL` in `src/cusum_detector.c`.

**Note:** The one-shot threshold is sensitive to the single largest clean MD. In the current dataset, boot 78 (`sub_a` = 934) has MD 8.669, and H = 1.25 × 8.669 = 10.84. The next largest clean MD is 6.091, so without boot 78 the threshold would be significantly lower.

**One-shot operation.** The firmware calls `cusum_update` once per boot with S starting at 0, so it is a threshold test on Mahalanobis distance, not a sequential detector. The Python pipeline (`build_model.py`) runs CUSUM over 20-boot windows and calibrates a different `k` and `H` for that setting; those values are not used in firmware. Sequential accumulation across checkpoints is Phase 2 work.

**Note:** Parameters must be recalibrated whenever firmware changes (timing shifts).

## Detection Algorithm

**CUSUM Sequential Change Detection:**

```c
// At each checkpoint:
1. Compute Mahalanobis distance:
   delta = x - mu
   y = Σ⁻¹ * delta
   MD = sqrt(delta' * y)

2. Update CUSUM statistic:
   S = max(0, S + MD - k)

3. Check alarm:
   if (S > H) {
       ATTACK DETECTED!
       halt_boot();
   }
```

**Why CUSUM?**
- The CUSUM update `S = max(0, S + MD - k)` allows sequential accumulation of evidence over multiple checkpoints. The firmware implementation calls it once per boot (S starts at 0, k = 0), so it acts as a threshold test on Mahalanobis distance; sequential accumulation is Phase 2 work.
- Slack parameter `k` filters normal variance (set to 0 for one-shot operation).

**Mahalanobis Distance:**
- Measures "how many standard deviations from mean"
- Accounts for feature correlation (sub_a, sub_b, sub_c not independent)
- Dimensionless metric (3D → 1D)

## Testing

### Test Suite

**`scripts/test_firmware_detector.sh`** - Automated validation
- Runs N clean boots (expect at most 5% false alarms) and N glitched boots (expect at least 90% detections). Default N is 20; set `N=1000` for the full validation.
- Results: [STATUS.md](STATUS.md#2-results).

```bash
./scripts/test_firmware_detector.sh
```

### Manual Testing

**Test clean boot:**
```bash
make clean && make all
timeout 1 make run </dev/null | grep "ATTACK DETECTED" || echo "Clean (no alarm)"
```

**Test glitch attack:**
```bash
make clean
make CFLAGS="-mcpu=cortex-m33 -mthumb -O0 -g -Wall -fno-builtin -DGLITCH_ATTACK" app.elf
timeout 1 make run </dev/null | grep "ATTACK DETECTED" && echo "Detected!" || echo "Missed"
```

## Performance

### Memory Usage (measured)

From `arm-none-eabi-size app.elf` (2026-11-10, after the overflow fix):

**Flash (code):**
- `cusum_detector.o` text section: 1060 bytes
- Whole firmware text: 3152 bytes

**RAM (runtime):**
- BSS (detector state): 64 bytes

Earlier notes cited ~968 bytes for the detector and ~3060 bytes for the firmware. Those figures could not be reproduced: rebuilding commit 4b019e3 (before the overflow fix) gives 1,784 bytes for the detector object.

### Execution Time (not yet measured)

**Latency:** detection runs once, right after checkpoint 2. Measure it with SysTick around `cusum_update` and add to a later revision. Earlier estimate (~350 cycles) is unverified.

## Current Limitations (Phase 1)

1. **QEMU timing variance** (CV about 9 to 10%, see the Gaussian analysis)
   - Host OS jitter causes high noise
   - Real hardware: expected to be lower (hypothesis, not yet measured)
   - Detection of the large simulated fault still works; about 1% of clean boots false-alarm

2. **Single checkpoint** (CP2 only)
   - Only monitors signature verify stage
   - Attacker could target CP1 or CP3
   - Phase 2: Multi-checkpoint fusion

3. **Fixed threshold**
   - H calibrated offline
   - Could adapt online (future work)

4. **Simulated faults**
   - `#ifdef GLITCH_ATTACK` macro
   - Phase 2: QEMU TCG plugin or real electrical glitching

## Phase 2 Enhancements

**When porting to real hardware (STM32L552):**

1. **Replace SysTick with DWT counters:**
   ```c
   // 5D hardware features (not 3D substage timing)
   uint32_t features[5] = {
       DWT->CYCCNT,   // Total cycles
       DWT->CPICNT,   // Multi-cycle instructions
       DWT->LSUCNT,   // Load/store stalls
       DWT->SLEEPCNT, // Sleep cycles
       DWT->FOLDCNT   // Folded instructions
   };
   ```

2. **Recalibrate model** on hardware data (and measure the real CV)

3. **Debugger-based fault injection** for testing

4. **Optimize:**
   - Precompute Σ⁻¹ matrix multiply with lookup tables
   - Use ARM DSP instructions (SIMD)
   - Constant-time operations (timing-attack resistant)

## Troubleshooting

### "No alarm on glitch attack"
- **Cause:** Model not calibrated for current firmware
- **Fix:** Run `python scripts/calibrate_firmware.py`, update parameters, rebuild

### "False alarms on clean boots"
- **Cause:** Usually a timing spike from a host pause (ISSUE-013), not a threshold problem
- **Fix:** Re-run the boot. Raising H does not remove large spikes; see STATUS.md

### "Linker error: undefined reference to __aeabi_ldivmod"
- **Cause:** Code uses 64-bit division (no libgcc)
- **Fix:** Use fixed-point arithmetic, avoid `/` on int64_t

### "Build error: cusum_detector.h not found"
- **Cause:** Header not in include path
- **Fix:** Source files must be in `src/` directory

## References

- **CUSUM Theory:** Page, E. S. (1954). "Continuous Inspection Schemes"
- **Mahalanobis Distance:** For multivariate anomaly detection
- **Fixed-Point Arithmetic:** Q16.16 format standard in embedded systems
- **ARM PMU:** ARM Cortex-M33 TRM, DWT chapter

## See Also

- [KNOWN_ISSUES.md](KNOWN_ISSUES.md) - Issue tracking
- [STATUS.md](STATUS.md) - Results, effort, scope
- [PROJECT_GUIDE.md](PROJECT_GUIDE.md) - Pipeline and methodology guide
