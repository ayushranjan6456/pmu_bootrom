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
# "!!! ATTACK DETECTED at CP3 (floor) !!!" and halts instead.
```

### 3. Collect Calibration Data

```bash
# Rebuilds all 7 ELFs and runs 300 boots of each (about 35 minutes)
bash scripts/collect_fault_types.sh 300 cal

# Output: data/cal_<variant>.csv, data/cal_<variant>_boots.csv, data/cal_meta.txt
# Calibration uses data/cal_clean.csv
```

### 4. Calibrate Detectors

```bash
source .venv/bin/activate

# Generate floor detector table (F=0.45)
python scripts/calibrate_floor.py data/cal_clean.csv 0.45

# Output: src/floor_table.h (auto-included by floor_detector.c)

# Generate Mahalanobis parameters for CP3
python scripts/calibrate_firmware.py data/cal_clean.csv 3 data/ds1_attack.csv

# Output shows C code for src/cusum_detector.c constants

# Rebuild with calibrated parameters
make clean && make
```

### 5. Validate Detectors

```bash
# Fresh validation boots, all 7 variants (a separate collection from the calibration one)
bash scripts/collect_fault_types.sh 300 val

# Test firmware detector against validation data
python scripts/validate_firmware.py

# Test real halting builds (optional, takes ~30 minutes for N=300)
bash scripts/test_halting_build.sh

# Validation results are in STATUS.md
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
│   ├── collect_fault_types.sh    # Batch QEMU collection
│   ├── calibrate_floor.py        # Generate floor_table.h
│   ├── calibrate_firmware.py     # Generate Mahalanobis constants
│   ├── validate_firmware.py      # Test detectors on validation data
│   ├── test_halting_build.sh     # Real halting-build test (300 boots/variant)
│   ├── detector_comparison.py    # Held-out comparison, severity sweep
│   ├── mahalanobis_failure_analysis.py  # Why Mahalanobis fails
│   ├── make_slide_plots.py       # Generate figures 1-6
│   └── fw_model.py               # Python mirror of firmware fixed-point
│
├── data/                         # Datasets
│   ├── cal_clean.csv             # Calibration set (300 boots)
│   ├── val_*.csv                 # Validation sets (7 variants × 300)
│   ├── ds1_*.csv                 # First collection (superseded by val_*)
│   └── *_meta.txt                # Collection provenance
│
├── results/                      # Generated plots
└── docs/                         # Technical documentation
```

---

## Common Tasks

### Build Targets

```bash
make              # halting firmware (app.elf): the floor rule stops the boot
make run          # one boot in QEMU (Ctrl-A X to quit)
make clean
make app_collect.elf app_attack.elf app_ft1.elf ... app_ft5.elf   # non-halting data-collection builds
make debug-server # QEMU paused for GDB
```

### Data collection

```bash
bash scripts/collect_fault_types.sh 300 cal   # all 7 variants, writes data/cal_*.csv
```

### Analysis

```bash
source .venv/bin/activate
python scripts/detector_comparison.py          # held-out comparison, severity sweep
python scripts/mahalanobis_failure_analysis.py # why the one-shot Mahalanobis rule fails
python scripts/validate_firmware.py            # firmware vs Python mirror on fresh boots
python scripts/make_slide_plots.py             # figures 1-6
```

### Testing

```bash
# Real halting builds, 300 boots per variant (rebuilds app.elf: run it alone)
bash scripts/test_halting_build.sh

# Host test of the fixed-point Mahalanobis code (square root, overflow, latching)
gcc -O1 -o /tmp/host_test tests/test_firmware_detector.c src/cusum_detector.c -lm && /tmp/host_test
```

The old 4-checkpoint pipeline (`build_model.py`, `cusum_detector.py`, `baseline_comparison.py`, `severity_sweep.sh`, `test_firmware_detector.sh`, ...) is in [archive/old_scripts/](archive/old_scripts/). It produced the frozen-firmware results quoted in STATUS.md and is not maintained.

---

## How It Works

### Boot flow

1. `systick_init()` starts the 24-bit cycle counter, then UART and the banner.
2. CP0 records the time origin.
3. Seven stages follow, each with three timed sub-stages (a, b, c): memory init (CP1), boot-mode detect (CP2), **signature verify (CP3, main target)**, decrypt (CP4), integrity (CP5), memory setup (CP6), handoff (CP7).
4. After each stage `check_checkpoint()` runs the **floor rule** (halts the boot) and, at CP3 only, the **Mahalanobis rule** (warns only).
5. A surviving boot prints its 8 telemetry rows and `BOOT COMPLETE`.

### Floor rule

Alarm if any sub-stage is below `0.45 x` its clean median (`src/floor_table.h`, generated by `scripts/calibrate_floor.py`).

### Mahalanobis rule (CP3)

```
MD = sqrt((x-mu)' S^-1 (x-mu))   # x = [sub_a, sub_b, sub_c], Q16.16 fixed point
S  = max(0, S + MD - k)          # called once per boot, so k = 0 and S = MD
alarm if S > H
```

`mu`, `S^-1`, `k`, `H` are `CUSUM_MODEL` in `src/cusum_detector.c`, generated by `scripts/calibrate_firmware.py`. Design and results: [FIRMWARE_DETECTOR.md](FIRMWARE_DETECTOR.md), [STATUS.md](STATUS.md).

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

**Problem:** Floor rule halts clean boots
- Likely cause: the floor table was generated from a different binary (the same code runs up to about 28% differently across builds, ISSUE-016), or the host was under heavy load
- Solution: recollect clean boots with the binary you will run, then
```bash
bash scripts/collect_fault_types.sh 300 cal   # all 7 variants, writes data/cal_*.csv
python scripts/calibrate_floor.py data/cal_clean.csv 0.45   # rewrites src/floor_table.h
python scripts/calibrate_firmware.py data/cal_clean.csv 3 data/ds1_attack.csv   # paste into src/cusum_detector.c
make clean && make
```

**Problem:** Attacks not detected
- Check `TIMER_INVALID,<cp>` in the output: an inconsistent SysTick reading makes both detectors skip that checkpoint (ISSUE-019)
- Check that the floor table and `CUSUM_MODEL` came from the same binary being run
- Extra-work faults (FT-5) are invisible to the floor rule by design; only the Mahalanobis warning sees them (ISSUE-018)

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

1. Edit `src/main.c` or a detector.
2. `make clean && make`, then `make run`.
3. Any change to boot-stage timing needs recalibration (floor table and Mahalanobis constants) on the same binary: collect, calibrate, rebuild, validate.

### Adding a boot stage

1. Add a `stage_*()` function in `main.c` with three timed sub-stages (a, b, c).
2. Call it from `main()` with `pmu_checkpoint(N)` and `check_checkpoint(N, &detector)` after it.
3. Raise `NUM_CHECKPOINTS` in `main.c` and `FLOOR_NUM_CP` in `floor_detector.h`.
4. Update `EXPECTED_CPS` in `scripts/collect_fault_types.sh` and the scripts that assume 8 checkpoints, then recollect and recalibrate.

### Fault macros (compile-time, all in `main.c`)

| Flag | Effect |
|------|--------|
| `-DGLITCH_ATTACK` | CP3 sub_b loop removed (`GLITCH_SKIP_PCT` defaults to 100) |
| `-DGLITCH_FT1_CP1_MEMCHECK` | CP1 sub_b loop removed |
| `-DGLITCH_FT2_CP2_COMPARE` | CP3 sub_c loop removed |
| `-DGLITCH_FT3_CP7_HANDOFF` | CP7 sub_a loop removed |
| `-DGLITCH_FT4_CP2_DOUBLE` | CP3 sub_a and sub_b loops removed |
| `-DGLITCH_FT5_CORRUPT_FLAG` | 50 extra iterations in CP3 sub_c |
| `-DCOLLECT_MODE` | Alarms are printed but the boot never halts, so telemetry is always printed |

Details and measured effects: [FAULT_MODELS.md](FAULT_MODELS.md). In QEMU a partial skip (`-DGLITCH_SKIP_PCT=<n>`) is not distinguishable from no skip (ISSUE-012).

### Key files

| File | Purpose |
|------|---------|
| `src/main.c` | Boot stages, timer guard, alarm response |
| `src/floor_detector.c`, `src/floor_table.h` | Floor rule and its generated table |
| `src/cusum_detector.c` | Fixed-point Mahalanobis rule and its generated constants |
| `scripts/calibrate_floor.py`, `scripts/calibrate_firmware.py` | Generate the two tables from clean boots |
| `scripts/fw_model.py` | Bit-exact Python mirror of the firmware arithmetic |
| `Makefile` | Halting build, collection builds, fault builds |

---

## Testing Strategy

- Host test of the fixed-point code: `tests/test_firmware_detector.c`.
- Firmware against its Python mirror on fresh boots: `scripts/validate_firmware.py` (0 disagreements on 2100 boots).
- Real halting builds: `scripts/test_halting_build.sh`.

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
