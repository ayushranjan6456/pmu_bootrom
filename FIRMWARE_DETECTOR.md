# Firmware-Embedded Fault Detectors

**Status:** Implemented (Phase 1), 8-checkpoint firmware
**Date:** 2026-11-12
**Files:** `src/floor_detector.{h,c}` + generated `src/floor_table.h`; `src/cusum_detector.{h,c}`; integrated in `src/main.c`

## Overview

Two detectors run during boot on the 8-checkpoint firmware, with different response levels:

| Detector | Runs | Rule | Response |
|----------|------|------|----------|
| **Floor** (`floor_detector.c`) | after every checkpoint CP1 to CP7 | alarm if any sub-stage is below `F x` its clean median (F = 0.45) | **halts the boot** |
| **Mahalanobis one-shot** (`cusum_detector.c`) | after CP3 only | alarm if the Mahalanobis distance of the CP3 features exceeds H | **warns and continues** |

Why two, and why only the floor halts: the Mahalanobis rule falsely alarms on timing spikes in clean boots and misses skipped loops that the floor catches, but it is the only rule that sees a sub-stage that got longer (FT-5). A check that is wrong on a few percent of good boots must not be able to stop the chip, so it only logs. Evidence and numbers: [docs/MAHALANOBIS_ANALYSIS.md](docs/MAHALANOBIS_ANALYSIS.md) and [STATUS.md](STATUS.md).

**Key point:** Both run **during boot**, not offline.

**Timer guard.** Before checking a checkpoint, `timer_ok()` in `main.c` rejects readings that cannot be real: SysTick elapsed not increasing, pinned at the 24-bit maximum, or a sub-stage longer than the stage. A rejected checkpoint prints `TIMER_INVALID,<cp>` and **both checks are skipped for it** (fail open). QEMU's SysTick follows host time and wraps under heavy CPU load, which otherwise reads as a skipped loop. A fault that also corrupted the timer would pass, so this is a QEMU-specific concession; DWT on real hardware does not wrap. The guard has not fired in any validation boot (idle host), so that path is untested in firmware.

**Output format.** An alarm prints `ALARM,<detector>,<cp>` and `ALARM_FEATURES,a,b,c`, then `HALTING BOOT` (floor) or `WARNING ONLY` (Mahalanobis). With `-DCOLLECT_MODE` neither halts, so telemetry is always printed.

## Architecture

### Data Flow
```
Boot stage -> checkpoint (SysTick) -> [sub_a, sub_b, sub_c] -> timer_ok? -- no --> TIMER_INVALID, skip
                                                                 | yes
                                          floor_check (every CP) --- any sub-stage < floor --> HALT
                                          cusum_update (CP3 only) --- MD > H ---------------> WARN
```

### Files

**`src/floor_detector.{h,c}`, `src/floor_table.h`** - Floor check
- `floor_check(cp, sub[3])`: returns 1 if any sub-stage is below `FLOOR_TABLE[cp][i]` (or `cp` is out of range)
- `FLOOR_TABLE` is `uint16_t[8][3]`, generated into `floor_table.h` by `scripts/calibrate_floor.py`. Integer compares only: no multiply, divide or square root.
- Size (`arm-none-eabi-size`, `-O0`): 140 bytes text (92 code + 48 table), against 1060 for `cusum_detector.o`.

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
- `check_checkpoint(cp)` runs after each stage: timer guard, then the Mahalanobis check (CP3 only), then the floor check
- `report_alarm(..., halt)`: the floor alarm halts, the Mahalanobis alarm logs a warning
- CP3 (signature verification) is the primary attack target

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

### Training Process (8-checkpoint firmware)

Calibrate from clean boots collected with the same binary that will be tested, because identical C code runs at different speeds in different binaries (CP3 `sub_b` differed by up to 22% between two builds, and by up to 18% between two runs of one build minutes apart; see ISSUE-016).

1. **Collect clean boots** with the non-halting build (nothing is dropped, so timing spikes stay in the data):
   ```bash
   bash scripts/collect_fault_types.sh 300 cal      # writes data/cal_clean.csv (and the fault variants, ~35 min)
   ```
   `data/cal_clean.csv` in the repo was collected earlier with the same boot loop for the clean build only (300 boots, load average at most 1.1); the script reproduces it.

2. **Floor table** (median of the clean boots, times F):
   ```bash
   python3 scripts/calibrate_floor.py data/cal_clean.csv 0.45    # writes src/floor_table.h
   ```

3. **Mahalanobis constants** (CP3; H is computed with the firmware's own fixed-point arithmetic, `scripts/fw_model.py`):
   ```bash
   python3 scripts/calibrate_firmware.py data/cal_clean.csv 3 data/ds1_attack.csv
   ```
   Paste the printed C code into `CUSUM_MODEL` in `src/cusum_detector.c`. That constant is the only place the model values are recorded.

4. **Rebuild** (headers now trigger recompiles, so a changed table cannot leave a stale object):
   ```bash
   make clean && make app.elf
   ```

5. **Validate on fresh boots**, not the calibration set:
   ```bash
   bash scripts/collect_fault_types.sh 300 val && python3 scripts/validate_firmware.py val
   N=300 bash scripts/test_halting_build.sh        # the real halting build
   ```

### Parameters

Floor: `FLOOR_TABLE[cp][i] = floor(F x median of the clean boots at that sub-stage)`, F = 0.45. The usable range of F is roughly 0.30 to 0.50: below 0.30 weaker faults slip through, above 0.50 sub-stages of an unfaulted checkpoint in a different build start to alarm (lowest such ratio observed 0.51). See [docs/MAHALANOBIS_ANALYSIS.md](docs/MAHALANOBIS_ANALYSIS.md) section 5. F was chosen after seeing the fault data and is confirmed only by the fresh validation set.

Mahalanobis (CP3 only):

| Parameter | Meaning |
|-----------|---------|
| **μ** | Mean cycle counts [sub_a, sub_b, sub_c] |
| **Σ⁻¹** | Inverse covariance from clean boots |
| **k_slack** | CUSUM slack. Set to 0 by `calibrate_firmware.py` because the detector runs once per boot. |
| **H** | Alarm threshold. Set to 1.25 x the largest clean-boot Mahalanobis distance. With k_slack = 0 the alarm fires when MD > H. |

Values: see `CUSUM_MODEL` in `src/cusum_detector.c`.

**Note:** The one-shot threshold is sensitive to the single largest clean MD, and on the 8-checkpoint data it is also inflated by timing spikes that stay in the training set. That is why this rule cannot be trusted to halt (see [docs/MAHALANOBIS_ANALYSIS.md](docs/MAHALANOBIS_ANALYSIS.md)). Precision: Q16.16 has steps of 1.5e-5, and the CP3 inverse-covariance entries are as small as 4e-4, so `calibrate_firmware.py` prints the quantisation error (1.2% of the largest entry here) and sets H on the fixed-point distances; a float-derived H differs from what the firmware computes.

**One-shot operation.** The firmware calls `cusum_update` once per boot with S starting at 0, so it is a threshold test on Mahalanobis distance, not a sequential detector. The Python pipeline (`build_model.py`) runs CUSUM over 20-boot windows and calibrates a different `k` and `H` for that setting; those values are not used in firmware. Sequential accumulation across checkpoints is Phase 2 work.

**Note:** Parameters must be recalibrated whenever firmware changes (timing shifts).

## Detection Algorithm

**Floor rule (halts):** for each checkpoint CP1 to CP7, `alarm = any(sub[i] < FLOOR_TABLE[cp][i])`. A skipped loop shortens the sub-stage it removes; timing spikes only lengthen sub-stages, so they cannot trigger it. It cannot see a sub-stage that got longer.

**Mahalanobis one-shot (warns), CP3 only:**

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
       print the alarm and WARNING ONLY; the boot continues
   }
```
It also alarms if any CP3 sub-stage exceeds `SUBSTAGE_ALARM_CYCLES` (4096), which is close to the largest clean CP3 value (3555), so a large timing spike trips it.

**Why CUSUM?**
- The CUSUM update `S = max(0, S + MD - k)` allows sequential accumulation of evidence over multiple checkpoints. The firmware implementation calls it once per boot (S starts at 0, k = 0), so it acts as a threshold test on Mahalanobis distance; sequential accumulation is Phase 2 work.
- Slack parameter `k` filters normal variance (set to 0 for one-shot operation).

**Mahalanobis Distance:**
- Measures "how many standard deviations from mean"
- Accounts for feature correlation (sub_a, sub_b, sub_c not independent)
- Dimensionless metric (3D → 1D)

## Testing

### Test Suite

**`scripts/validate_firmware.py`** - checks the 8-checkpoint firmware on a collection made by `collect_fault_types.sh`: recomputes the decision of both detectors for every boot from the printed telemetry (`scripts/fw_model.py` mirrors the fixed-point code bit for bit) and counts disagreements with what the firmware printed; reports false alarms and per-fault detection with Wilson intervals. Writes `results/validation_8cp.txt`.

**`scripts/test_halting_build.sh`** - runs the real halting build (no `COLLECT_MODE`) per variant and counts boots that halted, completed, or completed with a Mahalanobis warning. `N=300 bash scripts/test_halting_build.sh`, writes `results/validation_halting.log`. Run it alone: it rebuilds `app.elf`.

**`archive/old_scripts/test_firmware_detector.sh`** - the 4-checkpoint-era harness (one glitch, one monitored checkpoint). Its 1000-boot result belongs to the frozen firmware at tag `phase1-review-freeze-2`, not to this code.

Results: [STATUS.md](STATUS.md#2-results).

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

From `arm-none-eabi-size` at `-O0` (2026-11-12, 8-checkpoint firmware):

**Flash (code):**
- `floor_detector.o` text: 140 bytes (92 code + 48 table)
- `cusum_detector.o` text: 1060 bytes
- `main.o` text: 3380 bytes (includes 8 stages, `timer_ok`, `report_alarm`, `check_checkpoint`)
- Whole firmware text: 4692 bytes

**RAM (runtime):**
- BSS: 128 bytes (boot log 8 x 16 bytes; detector state is on the stack)

The 3152-byte firmware figure in earlier notes belongs to the 4-checkpoint build.

### Execution Time (not yet measured)

**Latency:** the floor check is 3 compares per checkpoint; the Mahalanobis update runs once at CP3. Neither has been timed. Measure with SysTick around `check_checkpoint` and add to a later revision. The earlier ~350-cycle estimate for the Mahalanobis update is unverified.

## Current Limitations (Phase 1)

1. **QEMU timing variance** (CV about 9 to 10%, see the Gaussian analysis)
   - Host OS jitter causes high noise
   - Real hardware: expected to be lower (hypothesis, not yet measured)
   - Detection of the large simulated fault still works; about 1% of clean boots false-alarm

2. **Lower bound only.** The floor rule cannot see a sub-stage that got longer (FT-5, +84%). Only the Mahalanobis warning at CP3 sees it, and it does not halt. A ceiling rule that catches FT-5 falsely alarms on 12 to 20% of clean boots across all sub-stages (about 1% at CP3 sub_c alone). Coarse: it catches reductions of roughly 55% or more reliably and misses reductions below about 30%.

3. **Per-build calibration.** Tables and constants are calibrated for one binary. Identical C loops ran up to 28% differently across binaries and up to 18% across runs of one binary (cause not identified), so F has little headroom above 0.5. Recalibrate after every firmware build.

4. **Timer guard fails open** on invalid SysTick readings (QEMU under host load); untested in firmware because it never fired on an idle host.

5. **Fixed threshold.** F and H are calibrated offline.

6. **Simulated faults.** Whole-loop removals and one extra loop, as compile-time macros. QEMU cannot produce partial skips (ISSUE-012). Phase 2: debugger-based injection and real glitching.

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

### "Floor alarm on a clean boot"
- **Cause:** The table was calibrated on a different binary, or F is too high. Check the lowest ratio of the alarmed sub-stage to its floor; also check `uptime` for host load.
- **Fix:** Recalibrate from a clean set of the same binary (`calibrate_floor.py`); keep F at or below 0.50.

### "Mahalanobis warnings on clean boots"
- **Cause:** Timing spikes (ISSUE-013), not a threshold problem. About 6% of clean validation boots warn.
- **Fix:** None needed: it only warns. Raising H does not remove large spikes; see STATUS.md

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
