# Firmware-Embedded CUSUM Detector

**Status:** Implemented (Phase 1)  
**Date:** November 7, 2026  
**Files:** `src/cusum_detector.{h,c}`, integrated in `src/main.c`

## Overview

Real-time fault injection detector running directly in bootrom firmware. Detects timing anomalies caused by voltage/clock glitch attacks using CUSUM (Cumulative Sum) sequential change detection.

**Key Achievement:** The detector runs **during boot**, not after. Attack detected in <1ms, not offline.

## Architecture

### Data Flow
```
Boot Stage → PMU Checkpoint → Feature Vector → CUSUM Update → Alarm?
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
- Fixed-point sqrt (binary search, no libgcc)
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
- Fixed-point is 10× faster, deterministic

**Example:**
```c
fixed_t a = FLOAT_TO_FIXED(1.5);    // 98304 = 0x00018000
fixed_t b = FLOAT_TO_FIXED(2.0);    // 131072 = 0x00020000
fixed_t c = fixed_mul(a, b);         // 3.0
```

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

3. **Embed parameters** in `src/cusum_detector.c`:
   ```c
   const cusum_model_t CUSUM_MODEL = {
       .mu = {...},          // Mean from training data
       .cov_inv = {...},     // Inverse covariance
       .k_slack = 1.528,     // From Python calibration
       .H = 13.844,          // H_99: 1% FA rate
   };
   ```

4. **Rebuild** firmware:
   ```bash
   make clean && make all
   ```

### Parameters

| Parameter | Value | Meaning |
|-----------|-------|---------|
| **μ** | [691, 560, 539] | Mean cycle counts [sub_a, sub_b, sub_c] |
| **Σ⁻¹** | 3×3 matrix | Inverse covariance (from training) |
| **k_slack** | 1.528 | CUSUM slack (reduces noise sensitivity) |
| **H_99** | 13.844 | Alarm threshold (1% false alarm rate) |

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
- Accumulates evidence over time (robust to single-sample noise)
- Slack parameter `k` filters normal variance
- Optimal for detecting persistent shifts (glitch causes sustained timing change)

**Mahalanobis Distance:**
- Measures "how many standard deviations from mean"
- Accounts for feature correlation (sub_a, sub_b, sub_c not independent)
- Dimensionless metric (3D → 1D)

## Testing

### Test Suite

**`scripts/test_firmware_detector.sh`** - Automated validation
- 20 clean boots → expect 0-1 false alarms (<5%)
- 20 glitch attacks → expect 18+ detections (>90%)

```bash
./scripts/test_firmware_detector.sh
```

### Manual Testing

**Test clean boot:**
```bash
make clean && make all
timeout 1 make run | grep "ATTACK DETECTED" || echo "Clean (no alarm)"
```

**Test glitch attack:**
```bash
make clean
make CFLAGS="-mcpu=cortex-m33 -mthumb -O0 -g -Wall -fno-builtin -DGLITCH_ATTACK" app.elf
timeout 1 make run | grep "ATTACK DETECTED" && echo "Detected!" || echo "Missed"
```

## Performance

### Memory Usage

**Flash (code):**
- `cusum_detector.c`: ~2 KB
- Model parameters: 80 bytes (const data)
- Total: ~2.1 KB

**RAM (runtime):**
- `cusum_state_t`: 12 bytes
- Stack for computation: ~100 bytes
- Total: ~112 bytes

**Very lightweight!** <0.5% of typical Cortex-M33 resources.

### Execution Time

**Per checkpoint:**
- Mahalanobis distance: ~300 cycles (matrix multiply + sqrt)
- CUSUM update: ~50 cycles (add, max, compare)
- Total: **~350 cycles** ≈ 3.5 μs @ 100 MHz

**Latency:** Attack detected within **1 ms** of occurring.

## Current Limitations (Phase 1)

1. **QEMU timing variance** (11% CV)
   - Host OS jitter causes high noise
   - Real hardware: <0.5% CV
   - Detection still works, but false alarm rate higher

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

2. **Recalibrate model** on hardware data (expect CV < 0.5%)

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
- **Cause:** Threshold too low, or high QEMU jitter
- **Fix:** Increase H threshold, or collect more training data

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

- [CLAUDE.md](CLAUDE.md) - Project overview and development guide
- [KNOWN_ISSUES.md](KNOWN_ISSUES.md) - Issue tracking
- [PROJECT_GUIDE.md](PROJECT_GUIDE.md) - Detailed implementation walkthrough
