# PMU Bootrom - Fault Injection Detection

Quick start guide for the PMU-based fault injection detection system.

**Status and results:** see [STATUS.md](STATUS.md)

---

## Quick Start

### 1. Setup Environment

```bash
# Install dependencies (Ubuntu/Debian)
sudo apt install gcc-arm-none-eabi qemu-system-arm

# Create Python virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Build and Test

```bash
# Build firmware
make clean && make

# Run single boot
make run

# Expected output: banner, then a DATA_START ... DATA_END CSV block
# (cp,elapsed,sub_a,sub_b,sub_c per checkpoint), stage durations,
# and "=== BOOT COMPLETE ===". A glitched build prints
# "!!! ATTACK DETECTED at CP2 !!!" and halts instead.
```

### 3. Train Detector Model

```bash
# Collect training data (500 boots, ~7 minutes)
make collect

# Build statistical model
source .venv/bin/activate
python scripts/build_model.py

# Output: data/model.npz
```

### 4. Calibrate Firmware

```bash
# Generate firmware parameters
python scripts/calibrate_firmware.py

# Output shows C code to paste into src/cusum_detector.c
# Update CUSUM_MODEL const with the generated values

# Rebuild with calibrated model
make clean && make
```

### 5. Test Detection

```bash
# Run automated test suite (one at a time: it runs make clean and rebuilds the shared app.elf)
bash scripts/test_firmware_detector.sh

# Prints the false alarm rate and detection rate; PASS means <=5% false alarms and >=90% detection.
# Measured values for the 1000-boot run are in STATUS.md.
```

---

## Project Structure

```
pmu_bootrom/
├── src/                          # Firmware source
│   ├── main.c                    # Boot stages with instrumentation
│   ├── startup.c                 # Reset handler & vector table
│   ├── cusum_detector.{h,c}      # Embedded detector
│   └── linker.ld                 # Memory layout
│
├── scripts/                      # Analysis pipeline
│   ├── build_model.py            # Train Gaussian model
│   ├── cusum_detector.py         # Detector simulation
│   ├── calibrate_firmware.py    # Model → C code generator
│   ├── test_firmware_detector.sh # Automated tests (clean + glitched boots)
│   ├── baseline_comparison.py    # Mahalanobis vs plain sub_b thresholds
│   ├── severity_sweep.sh         # Partial-skip glitch builds (see limitation)
│   ├── visualize.py              # Data visualization
│   └── data_quality.py           # Dataset validation
│
├── data/                         # Datasets
│   ├── nominal_boots.csv         # Clean boot telemetry
│   └── model.npz                 # Trained model
│
├── results/                      # Generated plots
└── docs/                         # Technical documentation
```

---

## Common Tasks

### Build Targets

```bash
make all          # Build nominal firmware
make clean        # Clean build artifacts
make run          # Run in QEMU
make collect      # Collect 500 boot samples
make debug-server # Start QEMU for GDB
```

### Data Collection

```bash
# Collect nominal boots
make collect
# Output: data/nominal_boots.csv

# Verify data quality
python scripts/data_quality.py
```

### Analysis

```bash
source .venv/bin/activate

# Train model and calibrate thresholds
python scripts/build_model.py

# Run detector simulation with ROC curves
python scripts/cusum_detector.py

# Visualize cycle stability
python scripts/visualize.py

# Compare Mahalanobis against plain sub_b thresholds (run from pmu_bootrom/)
python scripts/baseline_comparison.py
# Needs data/nominal_boots.csv and data/attack_boots.csv. Results: STATUS.md
```

### Testing

```bash
# Test clean boot (expect no alarm)
make clean && make
timeout 0.5 make run </dev/null | grep "ATTACK DETECTED" || echo "Clean ✓"

# Test glitch attack (expect alarm)
make clean
make CFLAGS="-mcpu=cortex-m33 -mthumb -O0 -g -Wall -fno-builtin -DGLITCH_ATTACK" app.elf
timeout 0.5 make run </dev/null | grep "ATTACK DETECTED" && echo "Detected ✓"

# Run full test suite
bash scripts/test_firmware_detector.sh

# Partial-skip glitch sweep (N boots per setting, default 20)
# Run these scripts one at a time: both run `make clean` and rebuild the shared app.elf.
PCTS="25 50 75" N=20 bash scripts/severity_sweep.sh
# Rebuilds app.elf at the end. In QEMU the result does not depend on the skip
# percentage (see STATUS.md, "Firmware partial-severity sweep"), so use it
# for the experiment, not for a detection-versus-severity claim.
```

---

## How It Works

### Boot Flow

1. **SysTick Init** - Start 24-bit cycle counter
2. **CUSUM Init** - Initialize detector state (S=0)
3. **Boot Stages** - Four stages with checkpoints:
   - CP0: UART Init
   - CP1: Memory Init
   - CP2: Signature Verify (PRIMARY TARGET)
   - CP3: Key Derivation
4. **Detection** - Check timing anomaly at CP2
5. **Response** - Halt boot if attack detected

### Feature Vector

Each checkpoint captures 4D vector:
- `elapsed`: Total cycles since boot start
- `sub_a`, `sub_b`, `sub_c`: Per-substage execution times

### CUSUM Algorithm

```
For each checkpoint:
  1. MD = sqrt((x-μ)' Σ⁻¹ (x-μ))    # Mahalanobis distance
  2. S = max(0, S + MD - k)          # CUSUM update
  3. if S > H: ALARM                 # Threshold check
```

**Parameters:**
- μ: Mean vector, Σ⁻¹: inverse covariance matrix (3×3)
- k, H: see `CUSUM_MODEL` in `src/cusum_detector.c`. Firmware runs once per boot, so k = 0 and the alarm is MD > H.
  The Python simulation uses a different, sequential k and H (see FIRMWARE_DETECTOR.md).

---

## Performance

Measured results, and which figures are still unmeasured estimates, are in [STATUS.md](STATUS.md).

---

## Troubleshooting

### Build Issues

**Problem:** `arm-none-eabi-gcc: command not found`
```bash
sudo apt install gcc-arm-none-eabi
```

**Problem:** `qemu-system-arm: command not found`
```bash
sudo apt install qemu-system-arm
```

**Problem:** Link error `undefined reference to __aeabi_ldivmod`
- Solution: Avoid 64-bit division in firmware (`fixed_sqrt` uses a division-free bit-by-bit method)

### Runtime Issues

**Problem:** Data corruption (CP0 elapsed = 16777215)
- Solution: Fixed in v0.3 (SysTick initialization order)
- Verify fix: `make run` should show CP0 elapsed < 2000

**Problem:** False alarms on clean boots
- Likely cause: Model not calibrated for current firmware
- Solution: Recollect data and retrain model
```bash
make collect
python scripts/calibrate_firmware.py
# Update src/cusum_detector.c with new parameters
make clean && make
```

**Problem:** Attacks not detected
- Check glitch severity in main.c (should skip entire sub_b loop)
- Verify the model was regenerated with `scripts/calibrate_firmware.py` and pasted into `src/cusum_detector.c` (alarm when MD > H)
- Compute the Mahalanobis distance of a boot offline from its `sub_a`, `sub_b`, `sub_c` values using the embedded `mu` and `cov_inv`

### QEMU Issues

**Problem:** QEMU version < 8.0 (mps2-an505 not available)
- Install QEMU 8.0 or newer (the project was run on 8.2.2); older releases lack the `mps2-an505` machine or have a UART bug

**Problem:** QEMU 6.2.0 has a SysTick bug that causes alarm on every boot
- Symptoms: Every clean boot prints "Timer with period zero, disabling" then `ALARM_FEATURES,0,0,0`
- Solution: Use QEMU 8.2+ (check with `qemu-system-arm --version`)
- If multiple QEMU versions are installed, ensure the correct one is in your PATH (e.g., `/usr/local/bin` before `/usr/bin`)

**Problem:** Timing noise too high (CV > 15%)
- QEMU limitation - expected CV ~10%
- Hardware variance is expected to be lower; this is a hypothesis to test in Phase 2
- Use empirical threshold calibration

---

## Documentation

See the document map in [STATUS.md](STATUS.md#8-document-map).

---

## Development Workflow

### Typical Development Cycle

1. **Modify firmware** - Edit `src/main.c` or detector
2. **Rebuild** - `make clean && make`
3. **Test** - `make run` or test suite
4. **Iterate** - Fix issues and repeat

### Adding New Boot Stages

1. Edit `main.c`: Add new `stage_*()` function
2. Split into 3 substages (A, B, C)
3. Call `pmu_checkpoint(N)` after stage
4. Increment `NUM_CHECKPOINTS` constant
5. Update all scripts to handle new CP index
6. Recollect data and retrain model

### Modifying Attack Simulation

The glitch lives in the `#ifdef GLITCH_ATTACK` block in `stage_signature_verify()` (`src/main.c`). It shortens the sub-stage B loop (300 iterations clean).

| Build flag | Effect |
|------------|--------|
| `-DGLITCH_ATTACK` | Skips the whole sub-stage B loop (default, `GLITCH_SKIP_PCT=100`) |
| `-DGLITCH_SKIP_PCT=<n>` | Skips n percent of the iterations (loop bound becomes `300 * (100 - n) / 100`) |
| `-DCOLLECT_MODE` | Detector reports but does not halt, so telemetry is still printed (used by `make collect-attack`) |

```bash
make CFLAGS="-mcpu=cortex-m33 -mthumb -O0 -g -Wall -fno-builtin -DGLITCH_ATTACK -DGLITCH_SKIP_PCT=50" app.elf
```

Note: in QEMU, `sub_b` barely changes until the loop is removed completely, so partial skips are not distinguishable from a clean boot. Details and numbers: [STATUS.md](STATUS.md), section "Firmware partial-severity sweep".

### Adjusting Detection Sensitivity

**Option 1: Firmware threshold.** The firmware runs once per boot, so `k = 0` and the alarm is MD > H. Change `MARGIN` in `scripts/calibrate_firmware.py` (H = MARGIN x largest clean MD), regenerate, and paste the output into `src/cusum_detector.c`. Then re-run the validation.

**Option 2: Python detector threshold** (`k` is the 70th percentile of clean MD, set in `build_model.py`)
- Edit `build_model.py` after line fitting
- Use `H_99` (1% FA) or `H_999` (0.1% FA)
- Regenerate model with `make collect && python scripts/build_model.py`

---

## Key Files Reference

| File | Purpose | When to Edit |
|------|---------|--------------|
| `src/main.c` | Boot stages | Add stages, change attack |
| `src/cusum_detector.c` | Embedded model | After calibration |
| `scripts/build_model.py` | Model training | Change threshold, features |
| `scripts/calibrate_firmware.py` | C code gen | Model structure change |
| `Makefile` | Build system | Add sources, change flags |

---

## Testing Strategy

### Unit Tests (Manual)
- Fixed-point arithmetic verification
- Mahalanobis distance calculation
- CUSUM update logic

### Integration Tests (Automated)
- `test_firmware_detector.sh` - Full detection test
- Clean boot FA test (20 boots)
- Attack detection test (20 boots)

### System Tests (Manual)
- End-to-end boot with detector
- Memory footprint measurement
- Timing latency measurement

---

## Limitations and Phase 2 plan

See [STATUS.md](STATUS.md#6-limitations) and [STATUS.md](STATUS.md#7-phase-2-plan).

---

## Support

**Issues:** See [KNOWN_ISSUES.md](KNOWN_ISSUES.md)  
**Environment:** QEMU 8.0 or newer, see Troubleshooting above  
**Questions:** Refer to comprehensive documentation

---

Project status, effort and results: [STATUS.md](STATUS.md)
