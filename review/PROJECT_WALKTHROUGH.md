# Project Walkthrough: PMU-Based Fault Injection Detection in Secure Boot

Written for: the project owner (Ayush), as a reference for explaining the project end to end. Numbers come from [STATUS.md](../STATUS.md), [FAULT_MODELS.md](../FAULT_MODELS.md) and `results/`; line numbers refer to the source as of this file's commit.

---

## 1. The problem and what exists today

**The threat.** The bootrom is the first code that runs and cannot be updated. It verifies the signature of the next stage. A fault injection attack (voltage or clock glitch) disturbs the chip for nanoseconds so an instruction is skipped or a loop exits early. If the signature check is skipped, an unsigned image boots and the root of trust is lost.

**This is practical** (from [COMPREHENSIVE_LITERATURE_SURVEY.md](../Literature_Survey/COMPREHENSIVE_LITERATURE_SURVEY.md)):
- PlayStation Vita security processor: boot ROM dumped by voltage glitching, over 80% reproducible (Paper 14)
- Three commercial bootloaders (NXP LPC, STM8, Renesas 78K0) broken with a ChipWhisperer of roughly $1000 (Paper 10)
- More than a million glitches over days against STM32, MSP430, Renesas (Paper 18)
- Tegra X2 secure boot in Tesla and Mercedes ECUs (Paper 20)

**Existing defences and their gaps:**

| Approach | Example | Achieves | Limit |
|---|---|---|---|
| Hardware sensor | PLL / ring-oscillator (P2), fault-to-time converter (P11) | 92.82% detection at 0.94% false alarms (P2) | Custom silicon, platform-specific, needs calibration |
| Software redundancy | CompaSeC (P6) | Zero successful attacks in simulation | 0.21% to 484% overhead, RISC-V compiler only |
| Algorithm checks | Loop counters (P5) | 92.56% detection | Written per function |
| Neural network | EKF-tuned NN (P8) | Adaptive | Training data and heavy inference; different domain |

**Our idea.** A skipped loop makes a stage finish in fewer cycles. Most ARM cores already have a cycle counter. Measure each boot stage, learn what a clean boot looks like, flag deviations. No new hardware.

**Cautions about the survey.**
- The "no prior work" gap holds only *within the 20 papers read*. Survey Section 9.4 says a systematic prior-art search was not done.
- Survey Sections 4.3 and 6.3 quote "99% detection at 1% false alarms" and "about 8% overhead" for this approach. Those were targets, not measured results. Do not quote them; use STATUS.md.

---

## 2. The story

### Chapter 1: Python detector on a 4-checkpoint stub (7 Nov)
- Bare-metal Cortex-M33 stub in QEMU, four stages, each split into sub-stages a, b, c (3 timings per checkpoint).
- Python fits a multivariate Gaussian to clean boots, scores by Mahalanobis distance, applies CUSUM `S = max(0, S + MD - k)`.
- Why Mahalanobis: the sub-stages move together (correlation about 0.9), so a broken pattern stands out.
- Problems: ISSUE-001 (37% corrupt boots, SysTick init order; fixed, see `systick_init`), ISSUE-004 (ROC AUC 0.4988, detection and false alarms measured on mixed streams), ISSUE-002 (data not Gaussian, so thresholds are empirical), ISSUE-007 (attacks were Python arithmetic, not real faults).

### Chapter 2: Port the detector into the firmware (7 to 10 Nov)
A detector that only exists in Python is not a boot-time defence (ISSUE-008). Porting to C:
- No FPU, no libgcc: Q16.16 fixed point everywhere.
- First square root truncated to an integer, so MD 15.5 to 16.0 slipped under the threshold; replaced by a division-free bit-by-bit root that keeps the fraction.
- ISSUE-014, fail-open overflow: a squared distance of 32768 or more wrapped when narrowed to 32 bits and was zeroed, so a huge timing value read as distance 0. Found by review, fixed by saturating.
- The CUSUM runs once per boot (`S = 0`, `k = 0`), so it is a threshold on MD with `H = 1.25 x largest clean MD`.
- Freeze result: 14/1000 false alarms, 1000/1000 attacks detected. Then an external audit (F-01 to F-07).
- Known weaknesses at that point: one fault type, one monitored checkpoint, ISSUE-012 (QEMU SysTick follows host time, so partial skips are invisible), ISSUE-013 (false alarms were timing spikes).

### Chapter 3: Broaden it and the detector stops working as shipped (11 to 12 Nov)
To answer "is one fault at one checkpoint enough?": 8 checkpoints, 6 fault builds, DS-1 (300 boots per variant, provenance recorded). Collection bugs were fixed on the way (stale ELFs, a truncated clean set): the script now rebuilds every ELF and checks 8 rows per boot.

**What happened.** Fitted on all 300 unfiltered clean boots, the one-shot rule had H = 20.9 and the attack's median MD was 3.1, so it detected 1 of 300 attacks.

**Diagnosis** ([docs/MAHALANOBIS_ANALYSIS.md](../docs/MAHALANOBIS_ANALYSIS.md)):
1. About 14% of clean boots (42 of 300) have an upward timing spike at some checkpoint, probably the host pausing QEMU.
2. A two-sided distance treats a spike like a fault.
3. `H = 1.25 x max` is set by the most extreme training boot, so a few spikes inflate the covariance and push H above the faults.
4. The score itself ranks well (AUC 0.97 to 0.98); the threshold is the problem.
5. The 4-checkpoint training set had no spikes. A selection effect (the halting build probably dropped spiked boots) fits the data but is not proven.

**An important nuance, measured while writing this file.** The 2.5 x IQR outlier filter on the CP3 training data is enough to restore detection. Same data, same `H = 1.25 x max`, attack boots from `data/ds1_attack.csv` (300):

| Training set | Boots kept | H | Attack MD (median, min) | Detected |
|---|---:|---:|---|---:|
| `cal_clean.csv`, unfiltered | 300 | 13.78 | 11.2, 6.6 | 10 / 300 |
| `cal_clean.csv`, IQR-filtered (shipped) | 291 | 7.54 | 17.6, 10.9 | 300 / 300 |
| `ds1_clean.csv`, unfiltered | 300 | 20.90 | 3.1, 2.3 | 1 / 300 |
| `ds1_clean.csv`, IQR-filtered | 294 | 10.72 | 18.0, 11.3 | 300 / 300 |

(H here is recomputed in floating point, so 7.54 differs slightly from the shipped fixed-point 7.49.) So the honest statement is: **spikes in the training set hide the attack; filtering them restores detection. What the filter does not fix is false alarms on fresh clean boots (5.7%) and the compounding across CP1 to CP7.** The held-out figures fig3 and fig2 use unfiltered fits, so they show the worst case, not the shipped model. Say so when presenting.

### Chapter 4: The fix, a one-sided floor and a tiered response
**Observation.** These faults only shorten a sub-stage, and the median does not move when a boot spikes upward. So: alarm if any sub-stage is below 0.45 x its clean median. It ignores upward spikes by construction and needs only integer compares.

**Results (fresh boots, N = 300 per build):** 0 clean false alarms (95% upper bound 1.3%), 298 to 300 of 300 detected on each skipped-loop fault. Margin check: the lowest clean sub-stage in the validation set is 1.62 times its floor (0.67 of its median), so the floor is not marginal on clean boots.

**Tiered response, by confidence.**
- Floor halts the boot (no false alarms measured).
- Mahalanobis only warns, at CP3: 5.7% of clean boots trigger it (17/300), so halting would deny service to about 1 in 18 good boots. It is the only detector that sees FT-5 (extra work, +84%), which a floor cannot see.

**Validated three ways:** a Python mirror matched the firmware on all 2100 fresh boots; held-out splits; real halting builds (attack, FT-1, FT-2, FT-4 halted 300/300, FT-3 299/300, clean boots never halted).

**On "novel".** The floor rule is simple and I would not call it a new algorithm. The contribution is the application, the fixed-point port, and a measured diagnosis of why a textbook detector breaks on realistic timing, with a design that responds to it.

---

## 3. Firmware, file by file

### src/startup.c
- Vector table (lines 12-18): initial stack pointer, reset, NMI, HardFault.
- `Reset_Handler` (22-41): copies `.data` flash to RAM, zeroes `.bss`, calls `main()`.

### src/linker.ld
`mps2-an505` memory map: flash 0x10000000, RAM 0x38000000, 2 MB each. Provides `_etext`, `_sdata`, `_edata`, `_sbss`, `_ebss` for the reset handler.

### src/main.c

| Lines | What |
|---|---|
| 6-29 | Polled UART0 output (no printf) |
| 45-59 | SysTick setup (`systick_init`, line 52): 24-bit down-counter |
| 66-68 | `systick_elapsed()` = `0xFFFFFF - CVR` |
| 85-100 | `pmu_snapshot_t`, `boot_log[8]`, `pmu_checkpoint()` |
| 114-341 | Seven stage functions: time three `volatile` busy loops each |
| 352-360 | `timer_ok()` timer guard |
| 368-387 | `report_alarm()`: print the alarm, then warn or halt |
| 390-399 | `check_checkpoint()`: runs both detectors |
| 402-485 | `main()` |

Loop counts per sub-stage: CP1 200, CP2 150, CP3 500/300/200, CP4 250, CP5 300, CP6 180, CP7 120.

**Fault macros** (`-DCOLLECT_MODE` is added by the Makefile's `app_*.elf` targets so the boot never halts):

| Macro | Lines | Effect |
|---|---|---|
| `GLITCH_ATTACK` | 195-210 | CP3 sub_b removed (-89%) |
| `GLITCH_FT1_CP1_MEMCHECK` | 124-130 | CP1 sub_b removed |
| `GLITCH_FT2_CP2_COMPARE` | 213 | CP3 sub_c removed |
| `GLITCH_FT3_CP7_HANDOFF` | 321-327 | CP7 sub_a removed |
| `GLITCH_FT4_CP2_DOUBLE` | 183-194 | CP3 sub_a and sub_b removed |
| `GLITCH_FT5_CORRUPT_FLAG` | 216-221 | 50 extra iterations in CP3 sub_c (+84%) |

Some macro names keep the old numbering: `FT2_CP2_COMPARE` and `FT4_CP2_DOUBLE` act on CP3.

**Timer guard.** Under host load QEMU's SysTick can wrap or stall. A checkpoint is valid only if elapsed time rises, stays below 0xFFFFFF, and covers the three sub-stages. Otherwise both detectors are skipped (fail-open: a fault that also corrupted the timer would pass). It never fired in validation, so it is untested in firmware (ISSUE-019).

**Response logic.** `check_checkpoint` runs Mahalanobis at CP3 with `halt = 0` and the floor at every checkpoint with `halt = 1`. `report_alarm` prints `ALARM,<detector>,<cp>` and then `WARNING ONLY` or `HALTING BOOT` followed by `while(1)`.

### src/floor_detector.{h,c}, src/floor_table.h
The whole detector is `floor_check` (floor_detector.c:7-13): return 1 if any `sub[i] < FLOOR_TABLE[cp][i]`. The table is generated; never edit it by hand. Example: CP3 is `{310, 300, 234}`; the attack gives sub_b of about 92.

### src/cusum_detector.{h,c}

| What | Where |
|---|---|
| Q16.16 type, `FLOAT_TO_FIXED` | header 30-33 |
| `SUBSTAGE_ALARM_CYCLES` (4096) | header 38 (largest clean CP3 sub-stage is 3555, so the margin is thin) |
| `CUSUM_MODEL` (mu, cov_inv, k = 0, H = 7.487) | cusum_detector.c 30-48, generated |
| `fixed_sqrt` | 57-79 |
| `mahalanobis_distance` (clamp inputs at 32767, line 99; saturate q, lines 124-132) | 92-136 |
| `cusum_update` (ceiling check, MD, `S = max(0, S + MD - k)`, alarm if `S > H`) | 158-194 |

The shipped model is fitted after the 2.5 x IQR filter removes 9 of 300 boots.

### Makefile
`make` builds the halting `app.elf`. `app_*.elf` targets add `-DCOLLECT_MODE` and one fault macro. `$(OBJS): $(wildcard src/*.h)` rebuilds on any header change (a stale object once corrupted a dataset). `EXTRA_CFLAGS` lets scripts add flags.

---

## 4. Scripts

| Script | Role |
|---|---|
| `collect_fault_types.sh N PREFIX` | Rebuilds all 7 ELFs, runs N boots each, writes `data/<PREFIX>_<variant>.csv`, a per-boot file (alarms printed, host load) and `_meta.txt` |
| `calibrate_floor.py` | `floor = floor(F x median)` per cell, writes `src/floor_table.h` |
| `calibrate_firmware.py` | IQR filter, mean and covariance, `H = 1.25 x max` on fixed-point distances, prints the C block |
| `fw_model.py` | Bit-exact Python mirror of the firmware arithmetic |
| `validate_firmware.py` | Predicts the firmware's decision per boot from its telemetry; counts disagreements (0 of 2100); Wilson 95% intervals |
| `test_halting_build.sh` | Builds each variant without COLLECT_MODE, runs 300 boots, counts halted / completed / completed with warning |
| `detector_comparison.py` | Held-out comparison of Gaussian, trimmed, floor and fusion designs; synthetic severity sweep |
| `mahalanobis_failure_analysis.py` | Spike counts, AUCs and trimming experiments |
| `make_slide_plots.py` | Figures 1 to 6 and `slide_plots_data.txt` |

**Held-out protocol.** Four splits (two interleaved, two time-ordered) of the 300 clean boots: fit on one half, score the other. Without this the threshold is tested on the data that set it.

**Calibrate on the binary you validate.** The same C code runs differently across builds (ISSUE-016, cause unknown). CP3 sub_b has a median of 668 in `cal_clean.csv`, 828 in `ds1_clean.csv` and 832 in `val_clean.csv`; the validation clean medians run from 1.01 to 1.25 times the calibration medians across CP1 to CP7. Never mix numbers across builds.

**Data and results.** `data/cal_*` calibration, `data/val_*` validation, `data/ds1_*` first collection. `results/` holds validation reports, the halting log and figures. `archive/old_scripts/` holds the Chapter 1 and 2 Python pipeline, the abandoned per-checkpoint fusion script and its model, and the 4-checkpoint test harness.

---

## 5. One boot, traced
1. `Reset_Handler` runs, calls `main()`.
2. `systick_init()`, `uart_init()`, banner.
3. CP0 records the time origin.
4. For CP1 to CP7: the stage runs, `pmu_checkpoint()` stores elapsed time, `check_checkpoint()` runs:
   - `timer_ok()` validates (if not: print `TIMER_INVALID`, skip).
   - At CP3 only: `cusum_update()`; on alarm print a warning and continue.
   - `floor_check()`; on alarm print and **halt**.
5. A surviving boot prints 8 CSV rows between `DATA_START` and `DATA_END`, then `BOOT COMPLETE`.

Attack boot: CP3 sub_b is about 92, below the floor of 300, so the boot halts. FT-5 boot: sub_c grows 84%, the floor sees nothing, Mahalanobis warns, the boot completes (ISSUE-018).

---

## 6. State plainly
- Faults are loop removals at CP1, CP3 and CP7, not electrical glitches. CP2, CP4, CP5, CP6 were exercised only by clean boots.
- QEMU cannot do partial skips, so the severity curve is synthetic; the floor needs roughly a 60% reduction to be reliable.
- F = 0.45 was chosen after seeing fault data; the usable window is about 0.30 to 0.50 and fresh validation checks the calibration, not the choice of rule.
- SysTick stands in for the PMU; DWT counters arrive in Phase 2.
- The Mahalanobis story is "needs a clean training set and still false-alarms on spikes in test boots", not "cannot detect".
