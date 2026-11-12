# Fault Models (8-checkpoint firmware)

Six compile-time faults, each a skipped (or, for FT-5, extended) busy loop in one sub-stage. All fault builds use `-DCOLLECT_MODE`, so the detector does not halt and telemetry is always printed. Data: `data/ds1_*.csv`, 300 boots per variant, collected by `scripts/collect_fault_types.sh` (provenance in `data/ds1_meta.txt`).

Macro names keep the old checkpoint numbering: `GLITCH_FT2_CP2_COMPARE` and `GLITCH_FT4_CP2_DOUBLE` act on CP3 (signature verification), not CP2.

## Measured effect at the target sub-stage

Median over 300 boots of the fault build against the median of the clean build (`app_collect.elf`) at the same checkpoint.

| Build | Macro | Target | Clean median | Fault median | Change |
|-------|-------|--------|-------------:|-------------:|-------:|
| `app_attack.elf` | `GLITCH_ATTACK` | CP3 sub_b | 828 | 92 | -89% |
| `app_ft1.elf` | `GLITCH_FT1_CP1_MEMCHECK` | CP1 sub_b | 685 | 94 | -86% |
| `app_ft2.elf` | `GLITCH_FT2_CP2_COMPARE` | CP3 sub_c | 572 | 97 | -83% |
| `app_ft3.elf` | `GLITCH_FT3_CP7_HANDOFF` | CP7 sub_a | 584 | 131 | -78% |
| `app_ft4.elf` | `GLITCH_FT4_CP2_DOUBLE` | CP3 sub_a and sub_b | 742 and 828 | 136 and 91 | -82% and -89% |
| `app_ft5.elf` | `GLITCH_FT5_CORRUPT_FLAG` | CP3 sub_c (extra loop) | 572 | 1051 | +84% |

## Detection with a per-checkpoint one-shot threshold

Per-checkpoint Gaussian fitted on all 300 clean boots, `H = 1.25 x` the largest clean Mahalanobis distance (the firmware rule). In-sample, computed in Python floating point, not the firmware's fixed-point code.

| Build | Checkpoint | Median MD | H | Detected |
|-------|-----------:|----------:|--:|---------:|
| attack | CP3 | 3.09 | 20.90 | 1 / 300 |
| ft1 | CP1 | 3.73 | 20.73 | 0 / 300 |
| ft2 | CP3 | 3.05 | 20.90 | 0 / 300 |
| ft3 | CP7 | 2.51 | 17.56 | 3 / 300 |
| ft4 | CP3 | 7.11 | 20.90 | 0 / 300 |
| ft5 | CP3 | 2.73 | 20.90 | 0 / 300 |

For comparison, the frozen 4-checkpoint firmware separated the same kind of fault (glitched MD 19.1 to 31.9 against a clean maximum of 8.7, see [STATUS.md](STATUS.md)). That training set had no timing spikes. This one does (below).

## What the data shows about the clean set

- **Timing spikes are present.** Counting a boot as spiked when any sub-stage exceeds 3x its checkpoint median: 24 of 300 clean boots at some checkpoint (CP1 to CP7), 4 of 300 at CP3. The CP3 rate (1.3%) is close to the 1.4% false-alarm rate of the frozen validation. This supports, but does not prove, the earlier hypothesis that the halting collection build dropped spiked boots from the training set.
- **The spikes destroy sensitivity.** Four spiked boots raise the CP3 standard deviation of sub_b from 156 to 286 cycles. With them removed, the attack's median MD is 7.5 instead of 3.1, still below the resulting threshold (16.6): 3 of 300 detected.
- **Two alarms per boot do not combine for free.** If every checkpoint were monitored and any alarm halted the boot, about 8% of clean boots would contain a spike somewhere.
- **Untouched sub-stages differ between builds.** The same C loop takes different time in different binaries: CP3 sub_b has a median of 828 in the clean, ft2, ft3 and ft5 builds but 598 in the ft1 build, and CP3 sub_c is 24% higher in the attack build. A clean-versus-fault comparison across two binaries therefore mixes the fault with this build effect. The cause is not identified. The frozen firmware has the same structure (separate clean and attack binaries).
- **Host drift.** 39 boots of the frozen firmware on this host on 2026-11-12 gave CP2 medians 747 / 624 / 546, against a frozen training mean of 695 / 583 / 502.

## Not covered

QEMU's SysTick follows host time, so partial skips cannot be measured (ISSUE-012, [STATUS.md](STATUS.md)). These faults are all whole-loop removals or a fixed extra loop.
