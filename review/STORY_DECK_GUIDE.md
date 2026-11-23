# Story Deck Guide: 25 Slides, One Figure Each

**Talk length:** about 20 minutes of speaking (table below), leaving up to 5 minutes of buffer inside the 20 to 25 minute limit.
**Audience:** IIT Madras Phase 1 review panel. **Presenter:** Ayush Ranjan (EE24M504).

Every number here was taken from [STATUS.md](../STATUS.md), [FAULT_MODELS.md](../FAULT_MODELS.md), [LITERATURE_SLIDES.md](LITERATURE_SLIDES.md), the four stage notes in this folder, or `results/`. If a number here ever differs from STATUS.md, STATUS.md wins.

The pictures are in [figures/](figures/). Re-create them with `python3 review/figures/make_story_figures.py` (run from `pmu_bootrom/`). Insert each PNG full-width; the figure already carries its own title.

---

## The story in one minute

1. **Problem.** An attacker glitches the boot ROM so the signature check is skipped.
2. **Idea.** A skipped loop makes a boot stage finish early. Learn how long clean boots take, and alarm when a stage is wrong.
3. **Stage 1.** In Python, on fake faults, it works.
4. **Stage 2.** We moved it into C firmware. It caught all 1000 attack boots and falsely alarmed on 14 of 1000 clean ones.
5. **Stage 3.** We widened the test to 8 checkpoints and 6 faults. The detector almost stopped working: harmless slow spikes looked more alarming than the real faults.
6. **Stage 4.** Our faults only make stages shorter, so we test only for "too short". That gave 0 false alarms and 298 to 300 detections out of 300 on the five skipped-loop faults.
7. **Phase 2.** Real hardware, real fault injection, and the things Phase 1 could not test.

Say this shape out loud on slide 6 so the panel knows where you are going.

## Deck at a glance

| Part | Slides | Time |
|---|---|---:|
| A. Introduction: title, problem, literature, idea, testbed, roadmap | 1 to 6 | 4 min 15 s |
| Stage 1: Python simulation | 7 to 10 | 3 min 20 s |
| Stage 2: firmware port | 11 to 14 | 3 min 15 s |
| Stage 3: broaden, then failure | 15 to 18 | 3 min 15 s |
| Stage 4: floor rule | 19 to 22 | 3 min 40 s |
| C. Towards Phase 2: limits, plan, summary | 23 to 25 | 2 min 30 s |
| | **25 slides** | **20 min 15 s** |

Each stage follows the same four beats: the **question** it asked, **what we built**, the **result**, and the **problem that pushed us to the next stage**.

| Slide | Figure file |
|---|---|
| 1 | none (title) |
| 2 | slide02_problem_boot_chain.png |
| 3 | slide03_literature_defences.png |
| 4 | slide04_idea_timeline.png |
| 5 | slide05_testbed.png |
| 6 | slide06_roadmap.png |
| 7 | slide07_stage1_main_flow.png |
| 8 | slide08_stage1_why_mahalanobis.png |
| 9 | slide09_stage1_cusum.png |
| 10 | slide10_stage1_results.png |
| 11 | slide11_stage2_main_flow.png |
| 12 | slide12_stage2_fixed_point.png |
| 13 | slide13_stage2_bugs.png |
| 14 | slide14_stage2_results.png |
| 15 | slide15_stage3_flow_faults.png |
| 16 | slide16_stage3_collapse.png |
| 17 | slide17_stage3_why_failed.png |
| 18 | slide18_stage3_spikes_accumulate.png |
| 19 | slide19_stage4_direction.png |
| 20 | slide20_stage4_floor_table.png |
| 21 | slide21_stage4_tiered_flow.png |
| 22 | slide22_stage4_results.png |
| 23 | slide23_phase2_questions.png |
| 24 | slide24_phase2_plan.png |
| 25 | slide25_summary.png |
| Backup | backupB1_stage2_slow_boots.png, backupB2_stage4_choosing_f.png, backupB8_literature_references.png |

---

# PART A: INTRODUCTION (4 min 15 s)

## Slide 1: Title (30 s)

No figure. Title, your name and roll number, IIT Madras, mentor's name, date.

**Say:** "This is the Phase 1 review of PMU-based statistical detection of fault injection in secure boot. I will tell it as a story: four stages, where each stage ended with something that did not work, and that is what started the next one."

## Slide 2: The problem (45 s)

**Figure:** slide02_problem_boot_chain.png. A five-box boot chain; the signature check is highlighted, a glitch hits it, and the two outcomes are shown: bad signature stops the boot, glitched check skipped lets unsigned code run.

**Say:** "A boot ROM checks the signature of the next stage before running it. An attacker with physical access can glitch the voltage or clock at exactly that moment and skip the check. Then unsigned code runs with full trust at the root of trust. Our Phase 1 stub has one such check and no redundancy, which the literature calls anti-pattern A7."

**Watch out:** For real-world evidence you can add one spoken line from [LITERATURE_SLIDES.md](LITERATURE_SLIDES.md), slide L1 (PlayStation Vita boot ROM, Nvidia Tegra X2 in cars). Spot-check those against the papers first; the author notes there say the numbers were not checked against the PDFs.

## Slide 3: What the literature does (55 s)

**Figure:** slide03_literature_defences.png. Five cards: two hardware sensors (He et al. 92.82%; Muttaki et al. 0.4% of LUTs), software redundancy (Geier et al., CompaSeC, 0.21 to 484% overhead), an algorithm-level check (Lee et al. 92.56%), and "this project: firmware only".

**Say:** "Hardware sensors detect well but need silicon area and per-platform calibration. Software redundancy prevents rather than detects, and can cost a lot. Algorithm-level checks work one function at a time. Our idea is firmware only: a statistical timing detector inside the boot ROM. The numbers on these cards come from different platforms and fault models, so they are not comparable with each other or with ours. Within the 20 papers we surveyed, we found none that uses statistical detection on on-chip timing inside a boot ROM. That claim holds only within those 20 papers; a systematic prior-art search is still to be done."

**Watch out:** Do not put our detection rates next to these numbers. See also the Q&A on novelty.

## Slide 4: The idea (40 s)

**Figure:** slide04_idea_timeline.png. Two timelines of the signature-verify stage cut into three timed blocks: a clean boot (742, 828, 572 cycles) and a skipped-loop boot where `sub_b` is 92. The gap is 736 cycles.

**Say:** "A boot stage runs the same code every time, so it takes about the same number of cycles. We read a timer at four points to get three block times, sub_a, sub_b and sub_c. If a glitch skips a loop, one block becomes much shorter. We learn how long each block normally takes, and raise an alarm when a block is wrong."

## Slide 5: The testbed (40 s)

**Figure:** slide05_testbed.png. A loop: main.c with six fault macros, built with arm-none-eabi-gcc, run in QEMU 8.2.2 (mps2-an505, Cortex-M33, SysTick), UART text, shell script, CSV files, Python scripts, and tables fed back into C.

**Say:** "Everything runs in QEMU on a Cortex-M33 model. Each boot prints its timings on the serial port, a script collects them into CSV files, Python learns the numbers, and those numbers go back into the C code. Two limits to keep in mind: the faults are compile-time macros, not electrical glitches, and QEMU's timer follows host time, so partial skips are invisible (ISSUE-012)."

## Slide 6: Roadmap (45 s)

**Figure:** slide06_roadmap.png. Four cards with the question each stage asked, and under each the problem it left behind.

**Say:** "Stage 1: can timing alone reveal a skipped loop? Yes, but the faults were Python subtraction. Stage 2: can it run in firmware with no floating point? Yes, but there was one fault at one checkpoint, and the false alarms came from timing spikes. Stage 3: does it hold with 8 checkpoints and 6 faults? No: a two-sided score cannot tell slow spikes from fast faults. Stage 4: is any stage suspiciously short? That works, and what is still open is Phase 2."

---

# STAGE 1: PYTHON SIMULATION (3 min 20 s)

## Slide 7: Where the fault goes in main.c (45 s)

**Figure:** slide07_stage1_main_flow.png. A vertical flow of the original 4-checkpoint main(); signature verify is highlighted. A detail panel shows its three loops (500, 300, 200 iterations) between four timer reads, with the fault on the `sub_b` loop under `-DGLITCH_ATTACK`.

**Say:** "This is the original firmware. After the timer and serial port start, checkpoint 0 marks the time origin, then three stages run and each is followed by a checkpoint, four checkpoints in all. Signature verification is the primary target. Inside it are three loops, each timed, and the fault shortens or skips the key-load loop, sub_b. Notice the last line: there is no detector in this firmware yet. In Stage 1 the Python scripts read the CSV afterwards, and the cut was applied to the recorded numbers in Python (ISSUE-007)."

## Slide 8: Why Mahalanobis distance (50 s)

**Figure:** slide08_stage1_why_mahalanobis.png. Scatter of 496 clean boots (sub_a against sub_b); a clean boot and the same boot with `sub_b` cut by 20%; a table of what a plain threshold and Mahalanobis distance (MD) each see.

**Say:** "We recorded 496 clean boots at the signature stage. The three timings rise and fall together, with correlation about 0.9, because when the host is slow all three get slower. Cut sub_b by 20% and it is only 0.3 standard deviations below its mean, so a plain threshold sees nothing. But sub_a and sub_c are above average, so sub_b should be too. A low sub_b beside two high ones breaks the pattern, and the distance rises from 1.79 to 4.47."

## Slide 9: CUSUM, the running total (50 s)

**Figure:** slide09_stage1_cusum.png. Left: one simulated stream of 10 clean then 10 cut boots, with MD, the running total S, threshold H and slack k. Right: histogram showing how H was chosen.

**Say:** "One odd boot is not proof, so we keep a running total: S becomes the larger of zero and S plus MD minus k. Below k the total drifts back to zero; above k boot after boot it climbs. Here k is 1.685. H is 10.14, the 99th percentile of the highest total seen in 10,000 simulated clean 20-boot sequences. In this stream the first cut boot is boot 10, and the alarm fires at boot 12, the third faulted boot."

## Slide 10: Stage 1 result and why it was not enough (55 s)

**Figure:** slide10_stage1_results.png. Left: detection by cut size. Right: detection by the number of faulted boots in a row. Bottom: four boxes on why this was not enough.

**Say:** "With 10 faulted boots in a row, detection is 4.5% at a 5% cut, 86.2% at 10%, 99.7% at 20%, and 99.6% at 30 and 50%. False alarms are 0.1 to 0.5%. ROC AUC at 20% is 0.9933. But four problems. The faults were Python subtraction, not real. The test is in-sample: streams came from the same 496 boots that fitted the model. It needs repeated faults: one faulted boot at a 20% cut is detected only 2.3% of the time, three boots 83%, ten boots 100%. And it exists only in Python; a defence must run inside the boot ROM and stop the boot (ISSUE-008). So Stage 2 ported it to C."

**Honesty note:** The first data collection (7 Nov) had about 500 usable boots; the model on the slides is from the re-collection (496 boots), which is what STATUS.md reports.

---

# STAGE 2: THE FIRMWARE PORT (3 min 15 s)

## Slide 11: The detector inside main() (40 s)

**Figure:** slide11_stage2_main_flow.png. The frozen 4-checkpoint firmware: after `pmu_checkpoint(2)`, build the three features, call `cusum_update`, test S > H. Yes leads to "ATTACK DETECTED at CP2" and the boot halts; no leads to the next stage. A side panel lists where the code lives.

**Say:** "In Stage 2 the detector became C code that runs during boot, right after checkpoint 2. If the alarm fires, the firmware prints the features and halts. The numbers come from a Python script that calibrates on clean boots and prints C code. Because firmware sees one boot at a time, the threshold became a one-shot rule: k is 0 and H is 1.25 times the largest clean distance, which is 10.84. This is the frozen firmware, tagged phase1-review-freeze-2."

## Slide 12: No floating point (45 s)

**Figure:** slide12_stage2_fixed_point.png. A 32-bit register split 16 and 16 bits (Q16.16), and a five-step pipeline for one attack boot (difference, multiply, dot product, square root, compare): 22.3 against H = 10.84.

**Say:** "A boot ROM has no floating-point unit and no maths library. So every number is stored as a whole number counting in 1/65536ths. 1.5 is stored as 98,304, and the range is about plus or minus 32,768. The five steps are subtract the average, multiply by the inverse covariance, take the dot product, take the square root, and compare. The square root is built one bit at a time with only compare, subtract and shift, because the chip has no 64-bit division. For this attack boot the firmware gets a distance of 22.29 against a threshold of 10.84."

## Slide 13: Two silent failures and the fixes (60 s)

**Figure:** slide13_stage2_bugs.png. Three panels: the square root throwing away decimals; the overflow that failed open (ISSUE-014); the three-layer fix.

**Say:** "Two bugs failed silently. First, the square root. The first version always returned zero, so nothing ever alarmed. The first fix kept only the whole number, and that threw away decimals: with the alarm line at 15.37, true distances of 15.5 and 15.9 both became 15 and were missed. The final version keeps the decimals and is within one step over 2 million test values. Second, overflow. We found it by reading the code. Above a squared distance of 32,768 the value wrapped and was set to zero. Re-running the old code showed 3,000 cycles alarmed and 16 million alarmed, but 40,000 and a wrapped timer of 4,294,967,295 did not. That is the dangerous kind of bug, because it looks fine in casual testing. The fix has three layers: cap every input at 32,767, saturate the distance at 181.02, and alarm outright if any sub-stage is over 4,096 cycles."

## Slide 14: Stage 2 result (50 s)

**Figure:** slide14_stage2_results.png. Distances on a log scale for 50 attack boots, 496 clean boots, and the 14 clean boots that false-alarmed. Right: key numbers.

**Say:** "On 1000 attack boots, all 1000 were detected. On 1000 clean boots, 14 false-alarmed, which is 1.4%. The largest clean distance in training was 8.7 and attack distances were 19.1 to 31.9, so detection was easy. The detector is 1,060 bytes and the whole firmware is 3,152 bytes. Now look at the 14 false alarms: every one we examined was a slow boot, one or two sub-stages far too slow. The likely cause is the host pausing QEMU; that is not confirmed. The training set held no such boots, 0 in 496. This was the warning sign, and Stage 3 tested the detector on a messier world."

**Backup:** B1 shows the 14 boots as a heat map: every slow sub-stage is 1.5 to 6.2 times its normal time and no cell is below 0.91.

---

# STAGE 3: BROADEN THE TEST (3 min 15 s)

## Slide 15: Eight checkpoints, six faults (45 s)

**Figure:** slide15_stage3_flow_faults.png. Seven stages (CP1 to CP7), three timed blocks each with their loop counts. Blocks changed by a fault macro are orange and labelled.

**Say:** "To look more like a real boot we grew to eight checkpoints, seven of them monitored. We built six fault builds. The original attack skips the CP3 sub_b loop. FT-1 skips CP1 sub_b, FT-2 skips CP3 sub_c, FT-3 skips CP7 sub_a, and FT-4 skips CP3 sub_a and sub_b. FT-5 is different: it adds an extra loop at CP3 sub_c, so that stage gets about 84% longer. We collected 300 boots of every build, and the script records the QEMU version, git commit and a hash of each build."

**Honesty note:** The first Stage 3 dataset was invalid and we withdrew it (stale builds, a clean set that came from the halting build, and FT-5 timestamps taken after the extra loop). The data on these slides is the corrected set.

## Slide 16: The same rule, almost no detections (55 s)

**Figure:** slide16_stage3_collapse.png. Horizontal bars: Stage 2 result for reference (1000/1000), then attack 1/300, FT-1 0/300, FT-2 0/300, FT-3 3/300, FT-4 0/300, FT-5 0/300. A text box gives the fault sizes, the faulted boots' median distance (2.5 to 7.1) and the thresholds (17.6 to 20.9).

**Say:** "We applied the Stage 2 rule unchanged: one Gaussian per checkpoint, threshold at 1.25 times the largest clean distance. It flagged 1 of 300 attack boots and 0 to 3 of 300 on every other fault. The faults are as large as before: each skipped loop removes 78 to 89% of that sub-stage's time, and FT-5 adds 84%. But a faulted boot's median distance is only 2.5 to 7.1, against thresholds of 17.6 to 20.9. The top bar is a different test, so do not compare it directly."

**Checked against `data/ds1_*.csv`:** all six counts (1, 0, 0, 3, 0, 0), the per-build median distances (3.09, 3.73, 3.05, 2.51, 7.11, 2.73) and thresholds (20.9, 20.73, 20.9, 17.56, 20.9, 20.9) reproduce exactly.

**Watch out:** This is the plain in-sample fit, using all 300 clean boots of the Stage 3 data, with no outlier filter. The shipped CP3 model is different: `calibrate_firmware.py` first drops outlier boots with a 2.5 x IQR filter (291 of 300 clean boots kept) and ends with H = 7.49, not 20.9. On fresh boots it does catch the attack (300/300, slide 22) but false-alarms on 5.7% of clean boots. The Stage 3 note says that on the calibration data, in-sample, the unfiltered fit caught 10 of 300 attacks and the filtered fit 300 of 300. Say this if asked why the firmware's Mahalanobis catches the attack when this slide says 1 of 300.

## Slide 17: Why it failed (50 s)

**Figure:** slide17_stage3_why_failed.png. Left: the 300 clean boots at CP3 ranked by distance, with the attack's median distance (3.1), the threshold (20.9) and a note that 7 boots score higher than the attack's median, 6 of them with a spiked sub-stage. Right: sub-stage times as a multiple of normal; Mahalanobis only asks "how far from the middle?".

**Say:** "Left: all 300 clean boots at CP3, ranked by distance. Seven of them score higher than the attack's median of 3.1, and six of those seven have a timing spike. Boot 203 is a perfectly good boot with sub_b at 3,790 cycles, 4.6 times normal, and its distance, 11.5, is 3.7 times the attack's. Boot 280, with sub_c at 3,588, 6.3 times normal, scores 16.7, so the threshold, 1.25 times that, sits at 20.9. Right: distance has no direction. It cannot tell too slow from too fast, but our faults only ever make a stage faster. Spikes also stretch the yardstick: sub_b's spread is 286 cycles with them and 113 without."

**Checked against `data/ds1_clean.csv` and `ds1_attack.csv`:** the 7 boots above the attack median are boots 280, 203, 101, 150, 201, 19 (all spiked) and 93 (MD 3.42, not spiked). Boot 203 is 3.72 times the attack's median distance. Excluding boots whose sub_b is over 1.5 times its median, sub_b's spread is 113.3 against 286.0 with them, which makes the 736-cycle drop 6.5 spreads away instead of 2.6.

**Watch out:**
- Do not say "14% of clean boots have a spike" over this slide. The 14% (42 of 300) counts a spike at any of the seven checkpoints and belongs to slide 18. At CP3 alone, 6 of 300 clean boots (2%) have one.
- The attack boots' untouched `sub_c` sits about 24% above the clean build's (708 against 572), so part of the attack's distance of 3.1 is a build effect, not the fault (ISSUE-016). The figure notes this.
- This is an in-sample fit on all 300 clean boots, with no outlier filter.

## Slide 18: More checkpoints, more false alarms (45 s)

**Figure:** slide18_stage3_spikes_accumulate.png. Left: the share of clean boots with a spike somewhere as checkpoints are added (1.3% at CP1 to 14% at CP1 to CP7). Right: clean boots falsely alarmed after trimming spiked boots from training.

**Say:** "Every checkpoint adds its own chance of a spike, so watching all seven means 14% of clean boots have a spike somewhere. We tried to rescue the rule, always held-out, fit on half the clean boots and tested on the other half. Removing spiked boots from training does bring detection back at CP3: 192 to 300 of 300 on the faults we tried, instead of 0 to 3. But false alarms grow: from 0.8% to 2.3% at CP3 and from 9% to 15.7% across CP1 to CP7. Any line low enough to catch the faults also flags the spikes. We needed a test that looks only downward."

---

# STAGE 4: THE FLOOR RULE (3 min 40 s)

## Slide 19: Skipped loops go down, spikes go up (50 s)

**Figure:** slide19_stage4_direction.png. CP3 `sub_b` as a multiple of the clean median on a log scale: clean boots near 1x with a few spikes out to about 5x, attack boots near 0.1x. The floor zone below 0.45x is shaded; Mahalanobis is shown as a two-sided test.

**Say:** "A skipped loop only makes a stage shorter, and a spike only makes it longer. So instead of asking whether a boot is strange, we ask whether any stage is suspiciously short. The floor sits at 0.45 times the clean median. The attack boots sit far inside it, and the spikes sit on the other side, where the floor never looks. There is one exception, FT-5, which adds work. A floor cannot see it, and I will come back to that."

## Slide 20: The floor rule (55 s)

**Figure:** slide20_stage4_floor_table.png. The 7 by 3 table of floors with CP3 highlighted; the `floor_check` code; a worked example at CP3; and a footnote on calibration.

**Say:** "For each of the 21 sub-stages, take the median over 300 clean calibration boots, multiply by 0.45 and round down. The median barely moves with spikes. At boot, if any sub-stage is under its floor, alarm. At CP3 the floors are 310, 300 and 234. A clean boot with sub_b of 860 continues. Boot 203, with sub_b of 3,790, also continues. The attack boot has sub_b of 93, below 300, so the boot halts. The code is 92 bytes plus a 48-byte table, 140 bytes in total, with no multiplies and no square root."

**Watch out:** The medians on this slide (690, 668, 522) differ from slides 4 and 17 (742, 828, 572). They come from different collection runs (slides 4 and 17 from the Stage 3 data, slide 20 from the separate calibration set), and the same code runs at different speeds across builds and runs (ISSUE-016). The footnote also says that on the fresh validation boots the medians were 1 to 25% higher, so the same floors acted as 0.36 to 0.44 of the fresh median, still inside the usable window of 0.30 to 0.50.

## Slide 21: The tiered response (50 s)

**Figure:** slide21_stage4_tiered_flow.png. `check_checkpoint(cp)` after every checkpoint: timer check, then Mahalanobis at CP3 (warning only), then the floor check (halt).

**Say:** "After every checkpoint the firmware first checks the timer is sane. At CP3 it runs the Mahalanobis rule, but that only prints a warning and the boot continues, because it false-alarms on 5.7% of clean boots and halting on it would stop about 1 good boot in 18. Then the floor check runs at every checkpoint, and it halts the boot, because it had no false alarm on 300 clean boots. The rule of thumb: a halt must be safe. We keep Mahalanobis only because it is the only rule that sees FT-5, the extra-work fault."

**Honesty note:** The timer check fails open and has never fired in validation, so its skip path is untested in firmware (ISSUE-019). See backup B4.

## Slide 22: Stage 4 result (65 s)

**Figure:** slide22_stage4_results.png. Left: faults detected out of 300 for the floor (green) and for Mahalanobis at CP3 (violet). Right: false alarms on clean boots. Bottom: the real halting-build test.

**Say:** "On 300 fresh boots per build, using the final binary: the floor falsely alarmed on 0 of 300 clean boots, upper bound 1.3%. It detected 299 of 300 on the attack, 299 on FT-1, 300 on FT-2, 298 on FT-3 and 300 on FT-4. On FT-5 it caught 0, as expected. Mahalanobis, which only watches CP3, detected all 300 of 300 on the four faults at that checkpoint (attack, FT-2, FT-4 and FT-5), but false-alarmed on 17 of 300 clean boots, 5.7%. The Python version of the rules agreed with what the firmware printed on all 2,100 boots. We also ran real halting builds: of 300 clean boots, 0 halted, 293 completed and 7 completed after a warning. The attack, FT-1, FT-2 and FT-4 halted 300 of 300, FT-3 299 of 300, and FT-5 was never halted but warned on all 300."

**Honesty notes:**
- We chose F = 0.45 after seeing the fault data. The fresh boots check the calibration, not the choice of rule.
- The floor needs roughly a 60% cut to be reliable (synthetic sweep: 0%, 26%, 33% and 96% at 30, 40, 50 and 60%). QEMU cannot make partial skips, so that curve is simulated.
- Faults were injected only at CP1, CP3 and CP7.
- The Mahalanobis false-alarm rate was 7 of 300 (2.3%) in the halting run and 17 of 300 (5.7%) in the collect-mode run. Both are single runs and we do not explain the gap.

---

# PART C: TOWARDS PHASE 2 (2 min 30 s)

## Slide 23: Every limit becomes a question (60 s)

**Figure:** slide23_phase2_questions.png. Seven rows: a Phase 1 limit on the left, the Phase 2 question on the right. Three right-hand items are marked (*).

**Say:** "Each thing Phase 1 could not show becomes something Phase 2 will measure. Faults were compile-time macros, so: does a real glitch change timing like a skipped loop? QEMU's timer hides partial skips, so we need the real severity curve with DWT counters. The floor needs about a 60% cut and is blind to extra work. Host timing spikes broke Mahalanobis, so: do spikes exist on silicon? Faults were only at CP1, CP3 and CP7. The same code ran up to 28% differently across builds. And we have per-checkpoint rules only, so we want multi-checkpoint fusion that does not multiply false alarms."

**Watch out:** The three (*) items follow from the Phase 1 limits but are not yet written in STATUS.md Section 7. Say so, and confirm them with your mentor before the review.

## Slide 24: The Phase 2 plan (45 s)

**Figure:** slide24_phase2_plan.png. Phase 1 stand-in on the left, Phase 2 replacement on the right: platform, counter, faults, detection, alarm response, data, comparison.

**Say:** "Phase 2 replaces the stand-ins one by one. QEMU becomes an STM32L552 with TrustZone-M. SysTick becomes the DWT cycle, CPI, load-store and fold counters. Compile-time macros become debugger-based fault injection, optionally voltage glitching. One rule per checkpoint becomes multi-checkpoint fusion, and we revisit the Stein's Lemma bounds once we have hardware data. The infinite-loop alarm becomes a TrustZone-M lockout. We also want larger glitched-boot datasets and a comparison against redundant execution. The Phase 2 budget is about 400 hours."

## Slide 25: Summary (45 s)

**Figure:** slide25_summary.png. The four stages again, each with its result, and the problem it exposed; Stage 3 highlighted.

**Say:** "Stage 1: the idea works on simulated faults, AUC 0.9933, but the faults were not real. Stage 2: in C, 1000 of 1000 attacks caught, 14 of 1000 false alarms. Stage 3: widened to 8 checkpoints and 6 faults, it broke, and 14% of clean boots had timing spikes. Stage 4: a one-sided floor, 0 of 300 false alarms and 298 to 300 of 300 on the five skipped-loop faults. The lesson: skipped loops shorten a stage and spikes lengthen it, so a one-sided test wins. Extra work, FT-5, is the exception, and Phase 2 will test all of this on real hardware."

---

# BACKUP SLIDES

**B1: Stage 2 slow boots** (backupB1_stage2_slow_boots.png). Heat map of the 14 false-alarming boots, each cell a sub-stage time divided by the training mean. The slowest sub-stage of each is 1.5 to 6.2 times normal; the lowest cell anywhere is 0.91, so none of these boots was fast. Likely cause: host pausing QEMU (not confirmed). The training set held 0 spiked boots in 496; the halting build probably dropped its own alarm boots (fits the data, not proven). Across two runs, 23 of 2,000 clean boots false-alarmed (about 1%).

**B2: Choosing F** (backupB2_stage4_choosing_f.png). Held-out sweep. Below 0.30 faults slip through: the worst fault is missed 1.7% of the time at 0.30, 36% at 0.25, 94% at 0.20. From 0.30 to 0.50 nothing alarms at an untouched checkpoint. Above that healthy checkpoints alarm: 1% at 0.55, 5% at 0.60. The lowest healthy sub-stage in clean data is 0.68 of its median, and an untouched sub-stage in a fault build reached 0.51, so 0.45 sits just under that. F was chosen after seeing the fault data. The right-hand panel is synthetic (ISSUE-012).

**B3: Fixed-point details.** Q16.16 resolution is 0.0000153, so the matrix entry 0.001665 is stored as 109 and reads back as 0.001663. The first firmware used the Python values (k 1.53, H 13.84), which meant it alarmed only above MD 15.37. On 10 Nov we switched to the one-shot rule (k = 0, H = 1.25 x largest clean MD).

**B4: Timer guard.** Under heavy host load QEMU's timer can wrap or stall and report zeros, which a floor would read as a skipped loop. In an earlier 60-boot load test, 28 boots had no usable readings and the floor alarmed on 27 of the 60 (from a note made at the time; no raw data was saved). `timer_ok` checks that elapsed time rises, stays under 2^24 and covers the three sub-stages; if not, both detectors skip that checkpoint and print `TIMER_INVALID`. It fails open, and it never fired in validation, so the skip path is untested in firmware (ISSUE-019).

**B5: The six fault builds.** Attack: CP3 sub_b, about 89% shorter. FT-1: CP1 sub_b, about 86%. FT-2: CP3 sub_c, about 83%. FT-3: CP7 sub_a, about 78%. FT-4: CP3 sub_a and sub_b, about 82% and 89%. FT-5: CP3 sub_c, about 84% longer. Details in [FAULT_MODELS.md](../FAULT_MODELS.md).

**B6: Same code, different speed (ISSUE-016).** CP3 sub_b has a median of 828 in the clean, FT-2, FT-3 and FT-5 builds but 598 in the FT-1 build. Rebuilding the same sources shifted CP3 sub_b by up to 22%, and re-running one binary five minutes later shifted a sub-stage median by up to 18%. The cause is unknown. Consequence: calibrate on the same build you test, and keep F at or below 0.50.

**B7: Scope against the proposal** (STATUS.md Section 5). Done early: Q16.16 fixed-point C port and halting on alarm. Partial: simulation environment with fault injection (compile-time macro, no QEMU plugin), 3-dimensional timing vectors at 8 checkpoints instead of 5-dimensional PMU vectors at 10, footprint measured but latency not. Not done: 10,000 glitched boots at 5 severity levels, Stein's Lemma bounds, TrustZone-M lockout, comparison against redundant execution.

**B8: Papers behind the literature survey** (backupB8_literature_references.png). Use when the panel asks "which papers did you read?". Two to three lines per paper are in [LITERATURE_PAPERS_README.md](LITERATURE_PAPERS_README.md). All 20 papers of the survey, numbered P1 to P20 as in the survey, with first author, year, title and venue. The four papers shown on slide 3 (P2 He, P5 Lee, P6 Geier, P11 Muttaki) carry a blue dot. Authors, years and venues were read from each paper's own PDF in `Literature_Survey/papers/`. Three things to know if asked:
- P19 (Luo, Luo, Fei, 2016) is a hardware clock-glitch detector, directly relevant prior work; its PDF is a preprint with no venue stated, so the slide says so.
- P12 (Obermaier et al.) is listed as "Applied Electronics 2017" from its DOI prefix (10.23919/AE.2017) and the University of West Bohemia ISBN in the PDF; the PDF text does not spell the conference name out.
- The survey's own reference list (Section 8 of `COMPREHENSIVE_LITERATURE_SURVEY.md`) has wrong author names for most papers and "Conference/Journal TBD" for almost all. This slide follows `papers_list.csv` and the PDFs instead, so do not read names from the survey file.

---

# LIKELY QUESTIONS

**Is this novel?** Within the 20 papers surveyed, yes: none combines statistical detection with on-chip timing in a boot ROM. Our firmware is a one-shot threshold; sequential accumulation is Phase 2. We have not done a systematic prior-art search yet.

**Why not use a hardware sensor?** Sensors need FPGA or ASIC primitives and per-platform calibration. Ours is a firmware update, and the trade-off is detection latency and generality.

**How does it compare with CompaSeC?** Different goal: CompaSeC prevents attacks with redundancy, we detect them from timing. The numbers are not comparable (RISC-V with synthesised faults against Cortex-M33 in QEMU with simulated skipped loops).

**Does QEMU predict hardware?** Not yet. Its SysTick follows wall-clock time, not executed work, so partial skips are invisible (ISSUE-012). That is why DWT counters on the STM32L552 are the first Phase 2 step.

**Where do the false alarms come from?** Timing spikes: one or two sub-stages far too slow. The likely cause is the host pausing QEMU; we have not confirmed it. Phase 2 will show whether spikes exist on silicon.

**Why not just tune the Mahalanobis threshold?** We tried (slide 18). A looser threshold, a robust fit and trimming spiked training boots either miss faults or raise false alarms to 2.3% at CP3 and about 16% across CP1 to CP7. The score ranks faults well, with AUC 0.97 to 0.98; the problem is that no cutoff separates faults from spikes.

**Why F = 0.45?** The usable window is 0.30 to 0.50 (backup B2). We chose 0.45 after seeing the fault data, so the fresh boots validate the calibration, not the choice of rule.

**What does the floor miss?** Longer stages (FT-5, 0 of 300), mild faults (it needs about a 60% cut), faults at checkpoints we did not inject (CP2, CP4, CP5, CP6), and any new binary until its table is regenerated.

**Where does 1.25 come from?** It is a margin over the largest clean distance, set as `MARGIN = 1.25` in `calibrate_firmware.py`. I found no record of a sweep over it in the notes, so do not claim it is optimal or was tuned; say it is a fixed margin. STATUS.md Section 6 gives the sensitivity of the frozen threshold: it needs roughly a 40 to 50% `sub_b` reduction before it alarms.

**Can an attacker glitch the detector itself?** Nothing in the Phase 1 notes tests that. The detector is ordinary code with no redundancy, like the signature check. Real fault injection and the TrustZone-M lockout are where that belongs, in Phase 2.

**Why did the Mahalanobis false-alarm rate differ between runs (2.3% against 5.7%)?** Both are single runs on different days with different binaries, and we do not explain the gap. The floor had 0 false alarms in both.

**How much effort?** See STATUS.md Section 4. The 600 hours there are an allocation, not a time log.

---

# DELIVERY NOTES

1. **Point at the figure.** Say "the orange dots", "the shaded zone", "the highlighted row". Do not read the slide.
2. **One honest line per stage.** Stage 1: faults were not real. Stage 2: one fault, one checkpoint. Stage 3: our own first dataset was invalid. Stage 4: F was chosen after seeing the faults. The panel trusts you more for saying these first.
3. **Say the FT-5 exception** every time you say "faults make stages shorter".
4. **Say that the numbers differ between data sets.** Medians are 742/828/572 on slides 4 and 17 and 690/668/522 on slide 20, because they come from different collection runs (ISSUE-016).
5. **Do not mix firmware generations.** The 1000-boot results (slides 11, 14) are the frozen 4-checkpoint firmware. The 300-boot results (slides 15 to 22) are the current 8-checkpoint firmware.
6. **Do not quote the literature numbers as comparisons.** They are on different platforms and fault models.
7. **"That is a Phase 2 question"** is a fine answer when it is true. Do not guess.

# BEFORE THE REVIEW

- [ ] Insert the 25 figures in order. Regenerate them if you change the script.
- [ ] Spot-check the literature numbers on slide 3 against the PDFs (LITERATURE_SLIDES.md says they have not been checked against the PDF text).
- [ ] Confirm the three (*) rows on slide 23 with your mentor.
- [ ] Re-check the numbers on slides 10, 14, 16, 20 and 22 against STATUS.md.
- [ ] Time one full rehearsal. It should come to about 20 minutes.
- [ ] [PPT_OUTLINE.md](PPT_OUTLINE.md), [DEMO_SCRIPT.md](DEMO_SCRIPT.md) and [SLIDE_GUIDE.md](SLIDE_GUIDE.md) are older, 4-checkpoint versions. Use this guide instead.
