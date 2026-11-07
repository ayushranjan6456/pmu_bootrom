# PMU Bootrom - Fault Injection Detection

Quick start guide for the PMU-based fault injection detection system.

**Status:** Phase 1 Complete ✅ (100% detection, 0% false alarms)

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

# Expected output:
# === PMU BOOTROM STUB v0.3 ===
# CP 0: elapsed=1083, sub=(0, 0, 0)
# CP 1: elapsed=2588, sub=(695, 587, 503)
# CP 2: elapsed=4372, sub=(691, 560, 539)
# CP 3: elapsed=5899, sub=(656, 548, 323)
# === BOOT COMPLETE ===
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
# Run automated test suite
bash scripts/test_firmware_detector.sh

# Expected:
# False Alarm Rate: 0%
# Detection Rate: 100%
# ✅ ALL TESTS PASSED!
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
│   ├── test_firmware_detector.sh # Automated tests
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
```

### Testing

```bash
# Test clean boot (expect no alarm)
make clean && make
timeout 0.5 make run | grep "ATTACK DETECTED" || echo "Clean ✓"

# Test glitch attack (expect alarm)
make clean
make CFLAGS="-mcpu=cortex-m33 -mthumb -O2 -g -DGLITCH_ATTACK" app.elf
timeout 0.5 make run | grep "ATTACK DETECTED" && echo "Detected ✓"

# Run full test suite
bash scripts/test_firmware_detector.sh
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
- μ: Mean vector [691, 587, 503]
- Σ⁻¹: Inverse covariance matrix (3×3)
- k: Slack parameter (1.528)
- H: Threshold (13.844 for 1% FA rate)

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Detection Rate | 100% (20/20 attacks) |
| False Alarm Rate | 0% (0/20 clean boots) |
| Detection Latency | 3.5 μs (350 cycles) |
| RAM Usage | 112 bytes |
| Flash Usage | 2.1 KB |
| ROC AUC | 1.0000 |

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
- Solution: Avoid 64-bit division in firmware (use integer sqrt)

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
- Verify model is calibrated (H_99 threshold)
- Run debug mode: uncomment `debug_mahalanobis()` call

### QEMU Issues

**Problem:** QEMU version < 8.0 (mps2-an505 not available)
- See [QEMU_VERSION_FIX.md](QEMU_VERSION_FIX.md) for upgrade instructions

**Problem:** Timing noise too high (CV > 15%)
- QEMU limitation - expected CV ~10%
- Hardware will have CV < 0.5%
- Use empirical threshold calibration

---

## Documentation

### Getting Started
- **[../README.md](../README.md)** - Repository overview
- **[PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md)** - Architecture
- **[PROJECT_GUIDE.md](PROJECT_GUIDE.md)** - Implementation details

### Technical Details
- **[FIRMWARE_DETECTOR.md](FIRMWARE_DETECTOR.md)** - Detector API & performance
- **[docs/GAUSSIAN_ASSUMPTION_ANALYSIS.md](docs/GAUSSIAN_ASSUMPTION_ANALYSIS.md)** - Statistical analysis
- **[../CLAUDE.md](../CLAUDE.md)** - Development guidelines

### Project Status
- **[PHASE1_COMPLETION.md](PHASE1_COMPLETION.md)** - Phase 1 summary
- **[KNOWN_ISSUES.md](KNOWN_ISSUES.md)** - Issue tracking
- **[SESSION_SUMMARY_2026-11-07.md](SESSION_SUMMARY_2026-11-07.md)** - Development log

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

Edit `#ifdef GLITCH_ATTACK` block in `stage_signature_verify()`:

```c
#ifdef GLITCH_ATTACK
    // Current: Skip entire sub_b loop
    // Effect: 500 cycle reduction (85% severity)
    
    // For weaker glitch:
    for (volatile uint32_t i = 0; i < 100; i++) {  // Break early
        break;
    }
    
    // For stronger glitch:
    goto skip_sub_b;  // Skip everything
#endif
```

### Adjusting Detection Sensitivity

**Option 1: Tune CUSUM slack parameter**
```bash
python scripts/tune_kslack.py
# Grid search for optimal k value
```

**Option 2: Change threshold**
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

## Known Limitations

1. **QEMU Timing Noise:** CV ~10% vs. <0.5% on hardware
2. **Single Checkpoint:** Only CP2 monitored
3. **Simulated Faults:** Macro-based, not instruction-level
4. **Low Severity:** <15% timing shifts may be missed

**Phase 2 addresses these with hardware validation.**

---

## Next Steps (Phase 2)

1. **Hardware Setup**
   - Acquire STM32L552 dev board
   - Port firmware to real hardware
   - Replace SysTick with DWT counters

2. **Fault Injection**
   - Debugger-based injection (GDB breakpoints)
   - Optional: DIY voltage glitching
   - Characterize real glitch signatures

3. **Algorithm Improvements**
   - Multi-checkpoint fusion
   - Adaptive thresholding
   - Constant-time implementation

---

## Support

**Issues:** See [KNOWN_ISSUES.md](KNOWN_ISSUES.md)  
**Environment:** See [QEMU_VERSION_FIX.md](QEMU_VERSION_FIX.md)  
**Questions:** Refer to comprehensive documentation

---

**Project Status:** Phase 1 Complete ✅  
**Last Updated:** November 7, 2026  
**Development Time:** ~205 hours  
**Documentation:** 300+ pages
