# Stage 3: Broaden the Test, and the Detector Stops Working

Study notes in plain language. Numbers come from [STATUS.md](../STATUS.md), [FAULT_MODELS.md](../FAULT_MODELS.md), [docs/MAHALANOBIS_ANALYSIS.md](../docs/MAHALANOBIS_ANALYSIS.md) and `results/mahalanobis_failure_analysis.txt`; if a number here differs from STATUS.md, STATUS.md wins.

**Period:** 11 to 12 Nov 2026 (commits a0b5214 to 785e7f0). **Data:** `data/ds1_*.csv`.

---

## Why this stage existed

At the freeze we had one fault at one checkpoint. A reviewer would ask: does it still work if the fault is somewhere else, or a different kind? So we widened the test.

## What we built

- **8 checkpoints instead of 4,** to look more like a real boot: hardware init, boot mode, signature verify, decrypt, integrity check, memory setup, handoff.
- **6 fault builds:** the original attack plus five more. Four skip a loop at different places. FT-5 adds extra work instead, so its timing goes up.
- **300 boots of each build** (7 builds including clean). The script records the QEMU version, the git commit and a hash of every build.

## Our own mistake first

The first dataset was invalid and we withdrew it:

- **Stale builds.** The script reused old 4-checkpoint builds, so five of the seven builds produced 4 rows per boot instead of 8.
- **The clean set came from the halting build.** That build stops when its detector alarms, so 19 of 300 clean boots were dropped. The training data was silently missing its odd boots. This is the same kind of filtering we suspected behind the Stage 2 result.
- **FT-5 did nothing.** Its extra loop ran after the last timestamp, so no timing changed.

The script now rebuilds every build each time and checks for 8 rows per boot. Clean data comes from a build that never halts.

## The result

With valid data we ran the Stage 2 rule: one threshold per checkpoint, at 1.25 times the largest clean distance (in-sample, Python floating point).

| Fault | Where | Detected |
|---|---|---:|
| Attack | CP3 | 1 / 300 |
| FT-1 | CP1 | 0 / 300 |
| FT-2 | CP3 | 0 / 300 |
| FT-3 | CP7 | 3 / 300 |
| FT-4 | CP3 | 0 / 300 |
| FT-5 | CP3 | 0 / 300 |

The faults are as big as before: each skipped loop removes 78 to 89% of that sub-stage's time. The detector simply stopped seeing them.

## Why it failed

**1. Clean boots have timing spikes.** 14% of clean boots (42 of 300) have a sub-stage more than 1.5 times its normal time at some checkpoint. The likely cause is the host pausing QEMU. Real examples at CP3:

| Boot | Spiked sub-stage | Normal | Boot's distance (MD) |
|---|---|---:|---:|
| 280 | `sub_c` = 3,588 | 572 | 16.7 (the largest clean one) |
| 203 | `sub_b` = 3,790 | 828 | 11.5 |
| Attack boot | `sub_b` = 92 | 828 | 3.1 (median) |

Boot 203 is a perfectly good boot, yet its distance is 3.7 times the attack's. To a distance score, the harmless spike looks far more alarming than the real attack.

**2. Distance has no direction.** Mahalanobis distance only measures "far from average". It cannot tell too slow from too fast. Our faults only ever make a stage faster.

**3. The threshold chases the worst boot.** The threshold is 1.25 times the largest clean distance, and that largest one was the spike in boot 280 (16.7). So the threshold became 20.9, while the attack's median distance was 3.1.

**4. Spikes also stretch the yardstick.** CP3's `sub_b` spread is 286 cycles with the spiked boots and 113 without. The attack's drop of 736 cycles is 2.6 spreads away with them and 6.5 without.

The score itself is fine. A faulted boot scores above a clean boot about 97 to 98% of the time. The cutoff is what fails: any line low enough to catch the faults also flags the spikes.

## Could we rescue it?

All held-out: fit on one half of the clean boots, test on the other half, four splits.

| Attempt | Faults caught (worst split, of 300 each) | Clean boots falsely alarmed |
|---|---|---|
| Looser threshold (97.5th percentile, robust fit) | attack 299, FT-4 300, but FT-1 42, FT-2 1, FT-3 5 | 16 of 600 at CP3; 112 of 600 across CP1 to CP7 |
| Remove spiked boots (above 1.5 times normal) from training | between 192 and 300, depending on the fault | 14 of 600 (2.3%) at CP3; 94 of 600 (16%) across CP1 to CP7 |
| Stage 1's outlier filter (2.5 x IQR), measured ad hoc, not saved in the repo | between 192 and 300 | 14 of 600 (2.3%) at CP3; 91 of 600 (15%) across CP1 to CP7 |

Every checkpoint adds its own chance of a spike, so watching more checkpoints multiplies the false alarms. The original plan was one detector per checkpoint with an alarm on any of them. In our tests that did not work.

**A nuance.** Filtering spikes out of the training set does restore detection at CP3. On the calibration data, in-sample, the unfiltered fit caught 10 of 300 attacks and the filtered fit 300 of 300. That is what the shipped model uses. But held-out, the worst split still misses some faults, and filtering does not remove the false alarms. The firmware's fresh-boot test of the shipped model gave 5.7% (17 of 300), higher than the 2.3% above. Both are single runs on different data, and we do not explain the gap.

## Why Stage 2 had looked fine

- The frozen training set had no spiked boots at the watched checkpoint: 0 of 496.
- Its own 1000-boot test did have them. 11 of the 14 false alarms had a sub-stage above 1.5 times normal. If the spike rate were even 1.1% (what the test boots showed), seeing none in 496 boots would have about a 0.4% chance.
- Together with the dropped boots in our invalid dataset, the likely story is that the halting build filtered its own training set. That fits the data but is not proven.

## One more finding: same code, different speed

The same C loop runs at different speeds in different builds. CP3's `sub_b` has a median of 828 in most builds and 598 in the FT-1 build. One untouched sub-stage in a fault build ran at only 0.51 of its clean-build value. The cause is unknown (ISSUE-016). So we must calibrate on the same build we test. Comparing a clean build to a fault build mixes the fault with the build effect.

## Where this leaves us

The faults are real and large, but a two-sided distance cannot separate them from upward spikes. Our faults only ever shorten a stage, so we need a test that looks only downward. That is Stage 4: the floor rule, and a response that depends on how sure each detector is.
