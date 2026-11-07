# PMU BootROM Technical Guide

## Project Overview

This is a **research implementation** of PMU-based statistical detection for fault injection attacks on secure boot. The system combines:
- **Bare-metal ARM Cortex-M33 firmware** instrumented with performance counters
- **QEMU emulation environment** for data collection
- **Python statistical pipeline** for Gaussian modeling and CUSUM detection
- **Visualization suite** for performance analysis and validation

**Research Goal:** Detect voltage/clock glitch attacks on bootrom signature verification using timing anomalies, achieving >90% detection rate with <2% false alarms.

**Current Implementation Status:** Simulation infrastructure complete, Python detector validated. The firmware detector (CUSUM in embedded C) is not yet implemented.

## Important Caveats

The current setup is useful for prototyping the detection algorithm and proving the statistical approach works. It does **not** yet demonstrate detection of real fault-injection attacks:

1. **Simulated workload:** Memory, signature-verification, and key-derivation stages use `volatile` loops; they do not perform real security operations.
2. **QEMU timing:** Not representative of real hardware (no cache, pipeline stalls, or interrupts). Variance artificially low.
3. **Synthetic attacks:** `cusum_detector.py` shifts timing values in Python post-processing, not via real fault injection during execution.
4. **Python-only detector:** CUSUM algorithm runs offline in Python; firmware has no detection logic or alarm mechanism.

To make this thesis-defensible, the detector must run **inside the firmware** and respond to **real faults injected during QEMU execution** (via TCG plugin).

## Architecture Deep Dive

### Firmware Layer (src/)

#### [src/main.c](./src/main.c) (255 lines)

**Core Components:**

1. **UART Communication (lines 3-27)**
   - Hardware: UART0 @ 0x50200000
   - Functions: `uart_init()`, `uart_putc()`, `uart_print()`, `uart_print_u32()`
   - Purpose: Output telemetry in CSV format for Python analysis
   - Polling-based (no interrupts) for determinism

2. **SysTick Timer (lines 29-66)**
   - Hardware: Cortex-M SysTick @ 0xE000E010-0xE000E018
   - 24-bit down-counter, max value 0xFFFFFF (16,777,215 cycles)
   - `systick_init()`: Load max value, clear counter, enable with processor clock
   - `systick_elapsed()`: Returns cycles since init (0xFFFFFF - CVR)
   - **Note:** Real hardware should use DWT_CYCCNT for 32-bit range

3. **PMU Snapshot Structure (lines 68-98)**
   ```c
   typedef struct {
       uint32_t elapsed_cycles;  // Absolute cycles since boot
       uint32_t sub_a;           // Sub-stage A duration
       uint32_t sub_b;           // Sub-stage B duration  
       uint32_t sub_c;           // Sub-stage C duration
   } pmu_snapshot_t;
   ```
   - 4-dimensional feature vector per checkpoint
   - `boot_log[NUM_CHECKPOINTS]` array stores all measurements
   - `pmu_checkpoint(id)` captures elapsed time at each stage

4. **Boot Stages with Sub-Stage Timing (lines 100-196)**

   **Stage 1: Memory Initialization** (`stage_memory_init()`)
   - Sub_a: Stack/BSS scan simulation (200 iterations, addition)
   - Sub_b: Peripheral probing (200 iterations, XOR)
   - Sub_c: Clock/PLL config (200 iterations, rotate)
   - Typical timing: ~600-800 cycles per substage

   **Stage 2: Signature Verification** (`stage_signature_verify()`) ⚠️ ATTACK TARGET
   - Sub_a: Hash computation (SHA-256 simulation, 500 iterations)
   - Sub_b: Public key load + modular reduction (300 iterations)
     - **GLITCH INJECTION POINT:** `#ifdef GLITCH_ATTACK` breaks at i=100
     - Simulates voltage glitch causing instruction skip
     - Effect: sub_b cycles drop by ~33% (200 cycles → 100 cycles)
   - Sub_c: Signature comparison (200 iterations)
   - Typical timing: sub_a=1400, sub_b=700, sub_c=400 cycles

   **Stage 3: Key Derivation** (`stage_key_derivation()`)
   - Sub_a: TRNG read simulation (100 iterations)
   - Sub_b: KDF mixing (100 iterations, LCG)
   - Sub_c: Key storage (100 iterations)
   - Typical timing: ~300-500 cycles per substage

   **Key Design Decision:** `volatile` prevents compiler optimization
   - Ensures deterministic cycle counts across boots
   - Essential for Gaussian modeling assumption

5. **Main Boot Flow (lines 199-255)**
   ```c
   systick_init();
   uart_init();
   SYST_CVR = 0;                    // Reset counter
   pmu_checkpoint(0);               // CP0: baseline
   stage_memory_init(1);            // Stage 1
   pmu_checkpoint(1);               // CP1
   stage_signature_verify(2);       // Stage 2 (attack target)
   pmu_checkpoint(2);               // CP2
   stage_key_derivation(3);         // Stage 3
   pmu_checkpoint(3);               // CP3
   // Print CSV between DATA_START / DATA_END markers
   ```

#### [src/startup.c](./src/startup.c) (41 lines)

**Bare-Metal Startup Sequence:**
1. Stack pointer loaded from first vector table entry (`_estack`)
2. `Reset_Handler()` called on power-up/reset
3. Copy `.data` from FLASH to RAM (initialized variables)
4. Zero `.bss` in RAM (uninitialized variables)
5. Call `main()`, trap if returns

**Interrupt Vector Table:**
- Only 4 vectors defined: stack pointer, reset, NMI, HardFault
- Minimal ISR configuration for bare-metal determinism

#### [src/linker.ld](./src/linker.ld) (41 lines)

**Memory Layout:**
```
FLASH: 0x10000000 (2MB) - Code and constants
RAM:   0x38000000 (2MB) - Data and stack
```

**Sections:**
- `.text`: Code + rodata in FLASH
- `.data`: Initialized data, loaded from FLASH to RAM at startup
- `.bss`: Uninitialized data, zeroed at startup
- Stack grows down from `_estack = 0x38200000`

### Python Analysis Pipeline (scripts/)

#### [scripts/collect.sh](./scripts/collect.sh) (30 lines)

**Data Collection Loop:**
```bash
for i in 1..500:
    qemu-system-arm -kernel app.elf > temp.txt &
    wait 0.8 seconds
    kill QEMU
    extract DATA_START..DATA_END block
    append to nominal_boots.csv
```

**Output Format:**
```csv
boot_id,cp,elapsed,sub_a,sub_b,sub_c
1,0,15,0,0,0
1,1,2104,593,662,597
1,2,4315,1405,707,402
1,3,5619,351,357,371
2,0,15,0,0,0
...
```

**Performance:** ~0.8s per boot × 500 = ~7 minutes total

#### [scripts/build_model.py](./scripts/build_model.py) (288 lines)

**Step 1: Data Cleaning (lines 23-46)**
- Load `nominal_boots.csv`
- Remove boots with CP0 elapsed > 100,000 (SysTick wrap before init)
- Remove boots with CP1 sub_a > 100,000 (uint32 underflow during stage)
- Typical: ~5-10 corrupt boots out of 500

**Step 2: IQR Outlier Filtering (lines 48-80)**
- Focus on CP2 (signature verification stage)
- For each feature (sub_a, sub_b, sub_c):
  - Compute Q1 (25th percentile), Q3 (75th percentile)
  - IQR = Q3 - Q1
  - Outliers: values outside [Q1 - 2.5×IQR, Q3 + 2.5×IQR]
- Drop entire boot if ANY feature is outlier
- Rationale: OS scheduling jitter on QEMU host causes rare 3-5× spikes
- Result: ~450 clean CP2 observations

**Step 3: Gaussian Model Fitting (lines 82-105)**
```python
X = df_cp2[['sub_a', 'sub_b', 'sub_c']].values  # (n, 3) array
mu = X.mean(axis=0)                             # Mean vector
cov = np.cov(X.T)                               # Covariance matrix
cov_inv = np.linalg.inv(cov)                    # For Mahalanobis distance
```

**Typical Values (QEMU):**
```
mu = [1405.2, 707.4, 401.8]
std = [2.1, 1.8, 1.5]
CV (coefficient of variation) = ~0.2% (very low, QEMU artifact)
```

**Normality Tests:**
- Shapiro-Wilk per feature: typically p > 0.05 (Gaussian)
- Slight right skew from OS jitter (acceptable)

**Step 4: CUSUM K_SLACK Calibration (lines 108-132)**

**Theory:**
- CUSUM statistic: `S_n = max(0, S_{n-1} + MD_n - k)`
- `k` is the "allowance" — how much evidence is forgiven per observation
- Too low k → false alarms on normal variance
- Too high k → slow detection, high miss rate

**Calibration Method:**
```python
MD_nominal = Mahalanobis_distance(X, mu, cov_inv)  # All clean observations
K_SLACK = percentile(MD_nominal, 70)               # 70th percentile
```

**Rationale:**
- During clean boots: ~30% of observations push S upward, ~70% push downward
- Net drift is zero on average
- During attack: most observations push S upward strongly
- Typical value: K_SLACK ≈ 2.0-2.5

**Step 5: Threshold H Calibration (lines 134-219)** 🔥 **CRITICAL INNOVATION**

**The Problem with Naive Approach:**
```python
# WRONG: Using single-observation MD distribution
H_wrong = percentile(MD_nominal, 99)  # e.g., 3.5
# Result: 8-10% false alarm rate (not 1%!)
```

**Why This Fails:**
- CUSUM accumulates over multiple observations
- Even if each MD < 99th percentile, their sum can exceed threshold
- Must calibrate from *sequence-level* CUSUM distribution

**Correct Method:**
```python
N_CAL = 10,000     # Number of simulation trials
SEQ_LEN = 20       # Boots per monitoring window

max_S = []
for trial in range(N_CAL):
    sequence = sample_with_replacement(X, size=SEQ_LEN)
    S = 0.0
    for x in sequence:
        MD = mahalanobis_distance(x, mu, cov_inv)
        S = max(0, S + MD - K_SLACK)
    max_S.append(max(S_over_sequence))

H_99 = percentile(max_S, 99)    # 1% false alarm target
H_999 = percentile(max_S, 99.9)  # 0.1% false alarm target
```

**Typical Values:**
```
H_99 ≈ 5.2   (1% FA rate)
H_999 ≈ 8.7  (0.1% FA rate)
```

**Verification (lines 192-218):**
```python
# Run 2000 held-out sequences through detector
false_alarms = count_alarms_on_clean_sequences(2000, H_99)
measured_FA_rate = false_alarms / 2000
# Should be ~0.01 ± 0.005
```

**Step 6: Save Model (lines 220-232)**
```python
np.savez('data/model.npz',
         mu=mu,
         cov=cov,
         cov_inv=cov_inv,
         X=X,                    # For future analysis
         MD_nom=MD_nominal,      # Distribution reference
         K_SLACK=K_SLACK,
         H_99=H_99,
         H_999=H_999)
```

**Step 7: Visualization (lines 234-288)**
- `results/model_distributions.png`: Histograms + Q-Q plots per feature
- `results/threshold_calibration.png`: MD distribution + CUSUM S distribution

#### [scripts/cusum_detector.py](./scripts/cusum_detector.py) (271 lines)

**Purpose:** Simulate glitch attacks at various severity levels, measure detection performance.

**Core CUSUM Function (lines 41-71):**
```python
def run_cusum(stream, mu, cov_inv, H, k):
    S_trace = []
    MD_trace = []
    s = 0.0
    alarm_index = -1
    
    for i, x in enumerate(stream):
        # Compute Mahalanobis distance
        d = x - mu
        md = sqrt(d @ cov_inv @ d)
        
        # Update CUSUM statistic
        s = max(0, s + md - k)
        
        # Check for alarm
        if s > H and alarm_index == -1:
            alarm_index = i
            
        S_trace.append(s)
        MD_trace.append(md)
    
    return alarm_index, S_trace, MD_trace
```

**Glitch Injection Model (lines 73-101):**
```python
def make_glitch_stream(X_nom, mu, severity, n_nominal=10, n_glitch=10):
    # Build stream: 10 clean boots + 10 glitched boots
    clean_boots = sample(X_nom, n_nominal)
    glitched_boots = sample(X_nom, n_glitch).copy()
    
    # Apply glitch: reduce sub_b by severity fraction
    shift = severity * mu[1]           # e.g., 0.20 * 707 = 141 cycles
    noise = normal(0, shift * 0.05)    # 5% noise on shift
    glitched_boots[:, 1] -= (shift + noise)
    glitched_boots = clip(glitched_boots, 1, inf)  # Prevent negatives
    
    return vstack([clean_boots, glitched_boots])
```

**Physical Interpretation:**
- Voltage glitch → instruction fetch fails → loop iteration skipped
- sub_b has 300 iterations, glitch causes ~20% to skip → 60 iterations lost
- Each iteration ≈ 2.3 cycles → 138 cycle reduction
- Matches 20% severity: 0.20 × 707 = 141 cycles

**Detection Rate Experiment (lines 103-146):**
```python
SEVERITIES = [0.05, 0.10, 0.20, 0.30, 0.50]
N_TRIALS = 1000

for sev in SEVERITIES:
    detections = 0
    false_alarms = 0
    misses = 0
    
    for trial in range(N_TRIALS):
        stream = make_glitch_stream(X_nom, mu, sev, N_NOMINAL=10, N_GLITCH=10)
        alarm_idx, _, _ = run_cusum(stream, mu, cov_inv, H_99, K_SLACK)
        
        if alarm_idx == -1:
            misses += 1                      # No alarm
        elif alarm_idx < N_NOMINAL:
            false_alarms += 1                # Alarm during clean phase
        else:
            detections += 1                  # Correct detection
            lag = alarm_idx - N_NOMINAL      # Boots after attack started
```

**Results Table:**
```
Severity | Detection Rate | FA Rate | Mean Lag
---------|---------------|---------|----------
5%       | 0.485         | 0.012   | 8.2 boots
10%      | 0.782         | 0.010   | 5.1 boots
20%      | 0.951         | 0.011   | 2.9 boots
30%      | 0.988         | 0.009   | 1.8 boots
50%      | 0.999         | 0.010   | 1.1 boots
```

**ROC Curve Generation (lines 148-187):**
```python
H_sweep = linspace(0.1, H_999 * 1.5, 80)  # 80 threshold values
roc_det = []
roc_fa = []

for H in H_sweep:
    det_count = 0
    fa_count = 0
    
    for _ in range(N_ROC=300):
        stream = make_glitch_stream(..., severity=0.20)
        alarm, _, _ = run_cusum(stream, mu, cov_inv, H, K_SLACK)
        
        if alarm >= N_NOMINAL:
            det_count += 1
        elif alarm != -1:
            fa_count += 1
    
    roc_det.append(det_count / N_ROC)
    roc_fa.append(fa_count / N_ROC)

# Sort by FA rate for proper AUC
sort_idx = argsort(roc_fa)
auc = trapezoid(roc_det[sort_idx], roc_fa[sort_idx])
# Typical: AUC ~ 0.992 at 20% severity
```

**Visualization (lines 189-271):**
- Plot 1: MD trace (shows when glitch happens)
- Plot 2: CUSUM S trace (shows accumulation and alarm)
- Plot 3: Detection rate vs severity
- Plot 4: ROC curve with operating point marked

#### [scripts/cusum_detector2.py](./scripts/cusum_detector2.py) (91 lines)

**Purpose:** Test detector on REAL firmware attack data (not synthetic).

**Workflow:**
1. Load model from `model.npz`
2. Load `attack_boots.csv` (collected via `make collect-attack`)
3. Build stream: 100 clean boots + 50 attacked boots
4. Run CUSUM detector
5. Check if alarm fires in attacked region

**Key Difference from cusum_detector.py:**
- Uses actual firmware glitch (`#ifdef GLITCH_ATTACK`)
- Not synthetic Python perturbation
- Tests if model generalizes to real glitch signature

**Typical Result:**
```
✓ ALARM SUCCESSFULLY TRIGGERED at boot 103 (Lag: 3 boots)
```

This validates that the calibrated model detects the firmware-level instruction skip.

#### [scripts/data_quality.py](./scripts/data_quality.py) (33 lines)

**Quick Data Inspection:**
- Total rows, unique boot_ids
- Missing values check
- Per-checkpoint statistics (mean, std, min, max, unique values)
- Duplicate check (tests QEMU determinism)

**Sample Output:**
```
Total rows: 2000
Unique boot_ids: 500
Checkpoints per boot: 4

Checkpoint 2 (n=450):
  elapsed    mean=4315.2  std=3.41  min=4308  max=4325
  sub_a      mean=1405.3  std=2.08  min=1401  max=1412
  sub_b      mean=707.4   std=1.83  min=704   max=713
  sub_c      mean=401.8   std=1.52  min=399   max=406
```

#### [scripts/visualize.py](./scripts/visualize.py)

**Interactive Plotting:**
- Feature trends across boot sequence
- Distribution histograms
- Helps spot outliers, visualize stability

#### [scripts/tune_kslack.py](./scripts/tune_kslack.py)

**Grid Search Optimization:**
- Tests K_SLACK values from 50th to 90th percentile
- For each k, measures detection rate and false alarm rate
- Finds optimal balance

**Typical Result:** k at 70th percentile gives best tradeoff.

### Build System (Makefile)

#### Key Targets

```makefile
all:             # Build app.elf (nominal firmware)
run:             # Run in QEMU
clean:           # Remove artifacts
collect:         # Collect 500 nominal boots
app_attack.elf:  # Build with -DGLITCH_ATTACK
collect-attack:  # Collect 50 attacked boots
debug-server:    # Start QEMU paused for GDB
```

#### Compiler Flags
```makefile
CFLAGS = -mcpu=cortex-m33 -mthumb -O0 -g -Wall -fno-builtin
LDFLAGS = -nostartfiles -nostdlib -T src/linker.ld
```

**Important:**
- `-O0`: No optimization (preserves volatile loop timing)
- `-nostartfiles -nostdlib`: Bare-metal (no C runtime)

## Data Flow and File Dependencies

### Complete Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. BUILD FIRMWARE                                               │
│    make → gcc → app.elf                                         │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│ 2. COLLECT NOMINAL DATA (500 boots, ~7 minutes)                │
│    make collect → scripts/collect.sh → QEMU × 500              │
│    Output: data/nominal_boots.csv (2000 rows)                  │
│    Format: boot_id,cp,elapsed,sub_a,sub_b,sub_c                │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│ 3. VALIDATE DATA QUALITY                                        │
│    python scripts/data_quality.py                              │
│    Check: row counts, missing values, outliers                 │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│ 4. BUILD STATISTICAL MODEL                                      │
│    python scripts/build_model.py                               │
│    Inputs: data/nominal_boots.csv                              │
│    Outputs:                                                     │
│      - data/model.npz (μ, Σ⁻¹, K_SLACK, H_99, H_999)          │
│      - data/nominal_cp2_clean.csv                              │
│      - results/model_distributions.png                         │
│      - results/threshold_calibration.png                       │
└────────────────────────┬────────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────────┐
│ 5. RUN DETECTOR SIMULATION                                      │
│    python scripts/cusum_detector.py                            │
│    Inputs: data/model.npz                                       │
│    Outputs: results/cusum_results.png                          │
│    (Synthetic attacks at 5 severity levels, ROC curves)        │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ OPTIONAL: TEST ON REAL FIRMWARE ATTACK                          │
│ make app_attack.elf → make collect-attack                      │
│ python scripts/cusum_detector2.py                              │
│ Output: results/empirical_attack.png                           │
└─────────────────────────────────────────────────────────────────┘
```

### File Dependencies

**Source Files (Tracked in Git):**
- `src/*.c`, `src/*.ld`: Firmware source
- `scripts/*.py`, `scripts/*.sh`: Analysis pipeline
- `Makefile`: Build automation

**Generated Artifacts (Not in Git):**
- `*.elf`: Compiled firmware binaries
- `data/*.csv`: Collected timing measurements
- `data/*.npz`: Fitted statistical models
- `results/*.png`: Analysis visualizations

**Regeneration Rules:**
1. If firmware changes → rebuild `.elf` → recollect data → refit model
2. If collection changes → refit model → rerun detector
3. Model files (`model.npz`) are tightly coupled to the dataset that created them

### Important Notes

- All scripts expect to run from `/home/ayush/work/PMU_Project/pmu_bootrom/`
- Paths are relative: `data/`, `results/`, `scripts/`
- `make collect` **overwrites** `nominal_boots.csv` at start (not append)
- Interrupt during collection → partial file → rerun from scratch

## Usage Guide

### Prerequisites

**System Requirements:**
- Linux (tested on Ubuntu 22.04 in WSL)
- ARM cross-compiler: `arm-none-eabi-gcc` (bare-metal toolchain)
- QEMU ARM emulator: `qemu-system-arm` with `mps2-an505` machine support
- Python 3.12+ with virtual environment

**Install Dependencies (Ubuntu):**
```bash
# ARM toolchain
sudo apt install gcc-arm-none-eabi

# QEMU ARM
sudo apt install qemu-system-arm

# Python packages (in virtual environment)
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**requirements.txt:**
```
numpy>=1.24.0
pandas>=2.0.0
matplotlib>=3.7.0
scipy>=1.10.0
```

### Quick Start: Single Boot Test

```bash
cd /home/ayush/work/PMU_Project/pmu_bootrom

# Build firmware
make clean
make

# Run single boot in QEMU
make run
```

**Expected Output:**
```
=== PMU BOOTROM STUB v0.2 ===
Counter: SysTick (processor clock, 24-bit)
Features: elapsed_cycles | sub_a | sub_b | sub_c

DATA_START
cp,elapsed,sub_a,sub_b,sub_c
0,15,0,0,0
1,2104,593,662,597
2,4315,1405,707,402
3,5619,351,357,371
DATA_END

=== STAGE DURATIONS ===
Stage 1: 2089 cycles total
Stage 2: 2211 cycles total
Stage 3: 1304 cycles total

=== BOOT COMPLETE ===
```

**Exit QEMU:** Press `Ctrl+A`, release, then press `X`

### Full Pipeline: Model Building

```bash
# Activate Python environment
source .venv/bin/activate

# Step 1: Collect 500 nominal boots (~7 minutes)
make collect
# Output: data/nominal_boots.csv (2000 rows)

# Step 2: Validate data quality
python scripts/data_quality.py
# Check output for: 500 unique boot_ids, no missing values

# Step 3: Fit Gaussian model and calibrate CUSUM
python scripts/build_model.py
# Outputs:
#   - data/model.npz
#   - results/model_distributions.png
#   - results/threshold_calibration.png

# Step 4: Run detector simulation (synthetic attacks)
python scripts/cusum_detector.py
# Output: results/cusum_results.png
# Shows: Detection rate vs severity, ROC curves

# Step 5 (Optional): Visualize raw timing data
python scripts/visualize.py
```

### Testing with Real Firmware Attacks

```bash
# Build firmware with GLITCH_ATTACK macro
make app_attack.elf

# Collect 50 attacked boots (~1 minute)
make collect-attack
# Output: data/attack_boots.csv (200 rows)

# Test detector on real attack data
python scripts/cusum_detector2.py
# Output: results/empirical_attack.png
# Shows: sub_b drop, CUSUM accumulation, alarm trigger
```

### Debugging with GDB

**Terminal 1: Start QEMU GDB Server**
```bash
make debug-server
# QEMU waits at PC=0x10000000 (reset vector)
```

**Terminal 2: Connect GDB**
```bash
arm-none-eabi-gdb app.elf
(gdb) target remote :1234
(gdb) break main
(gdb) continue
(gdb) print boot_log[2]
$1 = {elapsed_cycles = 4315, sub_a = 1405, sub_b = 707, sub_c = 402}
```

**VSCode Debugging:**
- Use `.vscode/launch.json` configuration
- F5 to start, breakpoints work
- Peripheral registers visible via SVD files

### Common Operations

**Rebuild Everything:**
```bash
make clean
make
make collect
python scripts/build_model.py
python scripts/cusum_detector.py
```

**Change Model Parameters:**
Edit `scripts/build_model.py`:
- Line 125: `K_SLACK = np.percentile(MD_nom, 70)` → change percentile
- Line 154: `N_CAL = 10000` → more calibration samples
- Line 155: `SEQ_LEN = 20` → longer monitoring windows

**Change Glitch Severity:**
Edit `scripts/cusum_detector.py`:
- Line 109: `SEVERITIES = [0.05, 0.10, 0.20, 0.30, 0.50]`
- Add more levels or test specific range

**Modify Firmware Glitch:**
Edit `src/main.c`:
- Line 158: `if (i == 100) break;` → change injection point
- Try different sub-stages (sub_a, sub_c) or boot stages (CP1, CP3)

## Understanding the Results

### Interpreting Model Outputs

**Model Distributions Plot ([results/model_distributions.png](./results/model_distributions.png)):**

Top row: Feature histograms with fitted Gaussian curves
- Blue: sub_a (hash computation, ~1405 cycles)
- Orange: sub_b (key reduction, ~707 cycles)  ← Attack target
- Green: sub_c (signature comparison, ~402 cycles)

**What to look for:**
- ✅ Histogram matches bell curve → Gaussian assumption valid
- ✅ Coefficient of variation (CV) < 1% → Deterministic execution
- ⚠️ Long right tail → OS jitter on QEMU host (handled by IQR filter)

Bottom row: Q-Q plots (quantile-quantile)
- Points should lie on diagonal line
- Deviations at extremes are acceptable (small sample effects)

**Threshold Calibration Plot ([results/threshold_calibration.png](./results/threshold_calibration.png)):**

Left: Nominal MD distribution
- Shows Mahalanobis distances from clean boots
- K_SLACK marked as vertical line (70th percentile)
- Most clean observations below k → S stays near zero

Right: CUSUM S distribution under H0
- Shows max(S) from 10,000 simulated clean sequences
- H_99 marked (orange) → 1% false alarm target
- H_999 marked (red) → 0.1% false alarm target

**Key Insight:** H is NOT derived from MD distribution (common mistake!)

### Interpreting Detector Results

**CUSUM Results Plot ([results/cusum_results.png](./results/cusum_results.png)):**

**Plot 1: Mahalanobis Distance Trace**
- X-axis: Boot sequence index
- Y-axis: MD score per boot
- Red dashed line: Glitch injection point (boot 10)
- Gray dotted line: K_SLACK threshold

**What you see:**
- Boots 0-10: MD fluctuates around 1.5-2.5 (normal variance)
- Boots 10-20: MD jumps to 6-7 (glitch effect)
- MD alone is noisy → hard to set single threshold

**Plot 2: CUSUM Statistic Trace**
- Purple line: CUSUM S accumulation
- Orange line: H_99 alarm threshold
- Green vertical line: Alarm trigger point

**What you see:**
- S drifts slightly during clean phase (some observations > k_slack)
- S surges when glitch starts (persistent MD elevation)
- S crosses H_99 → Alarm fires after 2-3 glitched boots

**Plot 3: Detection Rate vs Severity**
- Green line: Detection rate (TP rate)
- Red line: False alarm rate
- Gray line: Target FA = 1%

**Interpretation:**
- 5% severity: ~50% detection (subtle, easy to miss)
- 10% severity: ~80% detection (moderate confidence)
- 20% severity: ~95% detection (high confidence)
- False alarms stay ~1% across all severities (good calibration)

**Plot 4: ROC Curve**
- X-axis: False alarm rate
- Y-axis: Detection rate
- Blue curve: Detector performance
- Diagonal: Random guessing (AUC=0.5)
- Vertical gray line: Operating point (FA=1%)

**Metrics:**
- AUC ≈ 0.99 → Excellent discriminative power
- At FA=1%, detection rate ≈ 95% (good tradeoff)
- Curve hugs top-left corner → strong detector

### Interpreting Empirical Attack Results

**Empirical Attack Plot ([results/empirical_attack.png](./results/empirical_attack.png)):**

**Top Panel: sub_b Cycle Count**
- Boots 0-100: Stable around 707 cycles (clean baseline)
- Boots 100-150: Drops to ~450 cycles (firmware glitch active)
- Red line: Attack starts (firmware switch to app_attack.elf)

**Bottom Panel: CUSUM Score**
- Clean phase: S stays near zero
- Attack phase: S climbs rapidly
- Red dot: Alarm trigger point

**Typical Output:**
```
✓ ALARM SUCCESSFULLY TRIGGERED at boot 103 (Lag: 3 boots)
```

**This validates:**
1. Model calibrated on clean boots generalizes to real attacks
2. Firmware glitch produces detectable signature
3. Detection lag is low (3 boots ≈ 0.3 seconds at 10 Hz boot rate)

### Common Patterns and What They Mean

**Pattern 1: High False Alarm Rate (>5%)**
```
Possible causes:
- H threshold too low → recalibrate with more N_CAL samples
- K_SLACK too low → increase percentile (try 75th or 80th)
- Dataset has high variance → check for OS jitter, hardware issues
```

**Pattern 2: Low Detection Rate (<80% at 20% severity)**
```
Possible causes:
- K_SLACK too high → decrease percentile (try 65th or 60th)
- Model fitted on wrong checkpoint → verify using CP2
- Glitch effect too subtle → increase attack severity for testing
```

**Pattern 3: S Drifts Upward on Clean Boots**
```
Possible causes:
- Right-skewed MD distribution → K_SLACK should be higher percentile
- Model overfits to training set → need more diverse clean samples
- Non-stationary process → check for temperature drift, aging
```

**Pattern 4: Alarm Never Fires on Attack**
```
Possible causes:
- Attack doesn't change feature vector → verify glitch is active
- Feature not monitored → check which checkpoint is under attack
- Threshold too high → inspect S_trace, should see accumulation
```

## Advanced Topics

### Statistical Theory Behind CUSUM

**Problem Statement:**
Detect when boot timing shifts from nominal distribution P₀ to attack distribution P₁.

**Binary Hypothesis Testing:**
- H₀: Current boot ~ N(μ₀, Σ)  (clean)
- H₁: Current boot ~ N(μ₁, Σ)  (glitched)

Where μ₁ = μ₀ + δ, and δ = glitch shift vector (e.g., [0, -141, 0] for 20% sub_b reduction)

**Log-Likelihood Ratio:**
```
LLR_t = log(P₁(x_t) / P₀(x_t))
      = -0.5 * [(x-μ₁)ᵀΣ⁻¹(x-μ₁) - (x-μ₀)ᵀΣ⁻¹(x-μ₀)]
      = δᵀΣ⁻¹(x-μ₀) - 0.5*δᵀΣ⁻¹δ
```

**CUSUM Statistic:**
```
S_t = max(0, S_{t-1} + LLR_t - k)
```

Where k is the slack parameter (forgiveness for false starts).

**Our Simplification:**
We use Mahalanobis distance as a proxy:
```
MD_t = √[(x-μ₀)ᵀΣ⁻¹(x-μ₀)]
S_t = max(0, S_{t-1} + MD_t - k_slack)
```

This is **not** the true LLR (which requires knowing μ₁), but works well when:
- μ₁ is unknown (we don't know attack signature a priori)
- Any deviation from μ₀ is suspicious (omnibus test)
- Computationally simpler for embedded implementation

**Detection Guarantees (Stein's Lemma):**
```
P(miss detection after n boots) ≤ exp(-n * D_KL)
```

Where D_KL = KL divergence between P₀ and P₁.

For Gaussian shift: `D_KL = 0.5 * δᵀΣ⁻¹δ`

**Example Calculation (20% severity):**
```
δ = [0, -141, 0]
D_KL = 0.5 * δᵀΣ⁻¹δ ≈ 0.5 * (141)² / (1.8)² ≈ 3.06 nats

After n=10 boots:
P(miss) ≤ exp(-10 * 3.06) = 1.5e-13 (virtually zero)
```

This explains why detection rate is ~95% at 20% severity with just 2-3 boots.

### Why Threshold Calibration Matters

**Common Mistake (leads to 8-10% false alarms):**
```python
# WRONG: Use single-observation percentiles
MD_nominal = [mahalanobis(x, mu, Σ⁻¹) for x in X_clean]
H_wrong = percentile(MD_nominal, 99)  # e.g., 3.5
k_wrong = percentile(MD_nominal, 70)  # e.g., 2.0

# Run detector with H_wrong
false_alarms_observed = 8-10%  # NOT 1%!
```

**Why This Fails:**
- CUSUM accumulates evidence over sequence
- Even if each MD < 99th percentile, rare upward fluctuations accumulate
- Example: 5 observations at 98th percentile → S can exceed 3.5

**Correct Method (achieves 1% false alarms):**
```python
# RIGHT: Calibrate from sequence-level S distribution
for _ in range(10000):
    sequence = sample_clean_boots(20)
    S = run_cusum(sequence, k_slack)
    max_S_values.append(max(S))

H_correct = percentile(max_S_values, 99)  # e.g., 5.2

# Result: Exactly 1% of clean sequences trigger alarm
```

This is the **key contribution** that makes our detector work reliably.

### Feature Engineering Insights

**Why Sub-Stage Timing?**

**Alternative 1: Single Cycle Counter**
```c
uint32_t total_cycles = stage_signature_verify();
```
**Problem:**
- Glitch anywhere in stage → total shifts
- Can't localize where glitch occurred
- 1-dimensional feature → less information

**Alternative 2: Full Instruction Mix**
```c
cycles, instructions, CPI, LSU_stalls, branch_misses
```
**Problem:**
- Requires DWT counters (not available in QEMU)
- Higher dimensionality → needs more training data
- Some counters may not exist on all ARM variants

**Our Choice: 3 Sub-Stages**
```c
t0 = timer(); stage_a(); t1 = timer();
stage_b(); t2 = timer();
stage_c(); t3 = timer();
features = [t1-t0, t2-t1, t3-t2]
```

**Advantages:**
- Localizes glitch effect (only affected sub-stage shifts)
- 3D feature space → richer than 1D, manageable sample size
- Works in QEMU simulation (just timer reads)
- Generalizes to real hardware (replace with DWT)

**Example:**
```
Clean boot:     [1405, 707, 402]
Glitch in B:    [1405, 465, 402]  ← Only sub_b changed
Mahalanobis distance = 6.8 (high!)

vs. single counter:
Clean:   2514 cycles total
Glitch:  2272 cycles total (9.6% drop)
Harder to distinguish from normal variance
```

### QEMU vs. Real Hardware

| Aspect | QEMU | Real Hardware |
|--------|------|---------------|
| **Cycle Variance** | Very low (~2 cycles) | Moderate (~10-20 cycles) |
| **Causes of Variance** | Host OS jitter | Cache misses, pipeline stalls, interrupts |
| **Determinism** | Near-perfect (same ROM → same cycles) | Probabilistic (same ROM → distribution) |
| **Glitch Injection** | Software simulation (`#ifdef`) or TCG plugin | Physical (ChipWhisperer, voltage glitch) |
| **Model Implications** | Gaussian assumption holds easily | May need wider tolerance, higher k_slack |
| **Detection Difficulty** | Easier (low noise) | Harder (higher noise baseline) |

**Expected Changes for Real Hardware:**
1. **Higher Variance:**
   - QEMU: std(sub_b) ≈ 1.8 cycles
   - Hardware: std(sub_b) ≈ 8-12 cycles (5-6× increase)

2. **Adjusted Parameters:**
   - k_slack may need to increase (75th-80th percentile)
   - H_99 threshold will be higher (more accumulation needed)
   - Detection lag may increase (3-5 boots instead of 2-3)

3. **Still Detectable:**
   - 20% severity = 141 cycle shift
   - Even with std=12, shift is 11.75σ away
   - Detection rate should remain >90%

### Porting to Firmware (Future Work)

**Challenge:** Python uses floating-point Numpy operations. Firmware needs fixed-point arithmetic.

**Fixed-Point Representation:**
```c
// Q16.16 format: 16 integer bits, 16 fractional bits
typedef int32_t fixed_t;
#define FP_SCALE 65536  // 2^16
#define FP_MUL(a, b) (((int64_t)(a) * (b)) >> 16)
#define FP_DIV(a, b) (((int64_t)(a) << 16) / (b))

// Convert float to fixed
fixed_t to_fixed(float f) {
    return (fixed_t)(f * FP_SCALE);
}
```

**Mahalanobis Distance (Fixed-Point):**
```c
fixed_t mahalanobis_q16(int32_t obs[3], const model_t *model) {
    // d = obs - mu
    fixed_t d[3];
    for (int i = 0; i < 3; i++) {
        d[i] = (obs[i] << 16) - model->mu[i];
    }
    
    // temp = cov_inv @ d
    fixed_t temp[3] = {0, 0, 0};
    for (int i = 0; i < 3; i++) {
        for (int j = 0; j < 3; j++) {
            temp[i] += FP_MUL(model->cov_inv[i][j], d[j]);
        }
    }
    
    // result = sqrt(d @ temp)
    int64_t sum = 0;
    for (int i = 0; i < 3; i++) {
        sum += (int64_t)d[i] * temp[i];
    }
    sum >>= 16;  // Scale down once
    return (fixed_t)int_sqrt_q16(sum);
}
```

**Memory Footprint:**
```c
typedef struct {
    fixed_t mu[3];           // 12 bytes
    fixed_t cov_inv[3][3];   // 36 bytes
    fixed_t k_slack;         // 4 bytes
    fixed_t H_99;            // 4 bytes
} model_t;                   // Total: 56 bytes

typedef struct {
    fixed_t S;               // 4 bytes
    uint8_t alarm;           // 1 byte
} cusum_state_t;             // Total: 5 bytes
```

**Total RAM overhead:** ~60 bytes (negligible for modern MCUs)

**Cycle Overhead:**
- Mahalanobis: ~150 cycles (3×3 matrix multiply + sqrt)
- CUSUM update: ~10 cycles (add, max, compare)
- Per checkpoint: ~160 cycles
- 4 checkpoints: ~640 cycles (~8% overhead on 8000-cycle boot)

### Next Steps Roadmap

See [../Project_update](../Project_update) for comprehensive roadmap. Key priorities:

**Week 1-2: Firmware CUSUM (80 hours)**
1. Implement fixed-point Mahalanobis distance in C
2. Port CUSUM update logic to firmware
3. Generate `model_params.h` from `model.npz`
4. Integrate detector into boot flow
5. Print CUSUM S values over UART for validation

**Week 3-4: Real Glitch Injection (60 hours)**
1. Write QEMU TCG plugin for instruction-level faults
2. Implement SKIP, REPEAT, CORRUPT fault modes
3. Build parametric sweep script (cycle, mode, severity)
4. Validate that firmware detector catches injected faults

**Week 5-6: End-to-End Loop (40 hours)**
1. Automated campaign: inject 1000 glitches at 5 severity levels
2. Parse firmware UART for "ALARM" messages
3. Generate real ROC curves from firmware detection
4. Compare Python vs. firmware detector performance

**Success Criteria for Phase 1 Review:**
- ✅ Live demo: QEMU injects glitch → firmware prints "ALARM"
- ✅ Detection: >90% at <2% FA for 20% severity
- ✅ Code quality: Clean C implementation, well-documented
- ✅ Theoretical grounding: Stein's Lemma bounds derivation
- ✅ Multi-checkpoint: Monitor all 4 boot stages

## Validation Methodology

### Current Limitations

**This is a proof-of-concept simulation, not a validated security defense.** To make it thesis-defensible:

1. ✅ **Measurement defined:** 4D feature vector per checkpoint
2. ✅ **Representative clean data:** 500 boots collected (QEMU)
3. ❌ **Train/test split:** Currently trains and tests on same distribution
4. ✅ **Robust fitting:** IQR outlier removal, regularized covariance
5. ⚠️ **Detector calibration:** Sequence-level H, but only validated synthetically
6. ❌ **Real attack evaluation:** Only tested on firmware simulation
7. ✅ **Reproducibility:** Fixed random seed (Python), deterministic (QEMU)

### Path to Rigorous Validation

**Phase 1 (Simulation - Current):**
- Collect nominal data from QEMU
- Fit Gaussian model
- Inject synthetic attacks (Python perturbation)
- Measure detection performance

**Phase 2 (Firmware Integration - Next 150 hours):**
- Port detector to embedded C (fixed-point)
- Inject real faults (QEMU TCG plugin)
- Firmware raises alarm, Python analyzes UART log
- Generate ROC curves from firmware detection

**Phase 3 (Hardware Validation - Future 80 hours):**
- Port firmware to real Cortex-M33 dev board
- Collect clean data from hardware (500 boots)
- Refit model on hardware distribution (higher variance)
- Physical glitch injection (ChipWhisperer if available)
- Measure detection on physical attacks

**Phase 4 (Baseline Comparison - Future 50 hours):**
- Implement redundant execution defense
- Implement control-flow integrity checks
- Compare detection rate, false alarms, overhead
- Demonstrate CUSUM-PMU is superior

Until Phase 2-3 complete, describe results as **"synthetic proof-of-concept that demonstrates feasibility of the approach"** not **"validated security defense."**

## Troubleshooting

### Build Issues

**Error: `arm-none-eabi-gcc: command not found`**
```bash
sudo apt install gcc-arm-none-eabi binutils-arm-none-eabi
```

**Error: `undefined reference to '_estack'`**
- Check linker script path in Makefile
- Verify `linker.ld` defines `_estack`, `_sdata`, `_edata`, `_sbss`, `_ebss`

**Error: QEMU hangs on boot**
- Check UART initialization (baudrate, enable bit)
- Verify memory addresses match mps2-an505 machine
- Try `-d in_asm` flag to see executed instructions

### Data Collection Issues

**Problem: `nominal_boots.csv` has <2000 rows**
- Check `collect.sh` completed all 500 iterations
- Verify UART output has `DATA_START` / `DATA_END` markers
- Increase sleep time in `collect.sh` (0.8s → 1.0s)

**Problem: Many corrupt boots (>10%)**
- SysTick wrapping too early
- Increase boot stage timing (more loop iterations)
- Or handle wrap in firmware (track wrap count)

**Problem: sub_a/sub_b/sub_c all identical across boots**
- Compiler optimized away `volatile` somehow
- Check objdump: `arm-none-eabi-objdump -d app.elf | grep -A20 stage_signature`
- Verify optimization level is `-O0`

### Model Fitting Issues

**Problem: Shapiro-Wilk test fails (p < 0.05)**
- Check for multimodal distribution (two firmware versions mixed?)
- Increase IQR threshold (2.5× → 3.0×)
- Inspect histogram: is tail very long?

**Problem: Covariance matrix singular**
- Features are perfectly correlated
- Check if sub_a, sub_b, sub_c are all identical
- Add regularization: `cov += 1e-6 * np.eye(3)`

**Problem: K_SLACK too high (>mean(MD))**
- Distribution is right-skewed
- Try median instead of 70th percentile
- Or use robust estimator (MAD)

### Detection Issues

**Problem: 100% false alarms**
- H threshold too low
- Check threshold calibration ran correctly
- Verify using sequence-level S distribution, not MD

**Problem: 0% detections**
- H threshold too high
- K_SLACK too high (forgives all anomalies)
- Check glitch actually affects measured features
- Print MD values during attack to verify shift

**Problem: Inconsistent results across runs**
- Random seed not set (`np.random.seed(42)`)
- Sampling bias (small N_TRIALS)
- Check model file version (stale model.npz?)
