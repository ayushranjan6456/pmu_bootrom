# Story Deck Guide: PMU-Based Fault Detection Review

**Target:** 20 to 25 minutes | **Audience:** Technical review panel | **Status:** Phase 1 complete, pending approval

This guide walks through your presentation slide-by-slide, with visualizations that show exactly how the detector works and what happened at each stage.

---

## Overview

The deck tells the story of Phase 1 as a journey through four stages, where each stage solved one problem and exposed the next. The flow:

1. **Part A: Setup** (slides 1–6): problem, literature, the idea, testbed, and roadmap
2. **Part B: The Four Stages** (slides 7–22): each stage gets 3 to 4 slides showing the code, the method, results, and what failed
3. **Part C: Phase 2 and Summary** (slides 23–25): what the limits mean, the Phase 2 plan, and the lesson learned

**Timing:** About 22 minutes (1 min title, 4 min setup, 14 min stages, 3 min Phase 2). Leave 3 minutes for buffer and questions.

---

## Deck At A Glance

**Main slides (25 total):**

### Part A: Introduction and Setup (6 slides, ~4 min)
- **Slide 1:** Title
- **Slide 2:** Problem statement and boot chain
- **Slide 3:** Literature survey – what others built
- **Slide 4:** The idea: timeline with PMU checkpoints
- **Slide 5:** Testbed: QEMU, ARM Cortex-M33, SysTick
- **Slide 6:** Roadmap: four stages, each fixes the last

### Part B: The Four Stages (16 slides, ~14 min)

**Stage 1: Python Simulation** (4 slides, ~3.5 min)
- **Slide 7:** main.c flow with fault injection point
- **Slide 8:** Why Mahalanobis (MD captures the pattern)
- **Slide 9:** CUSUM accumulates evidence
- **Slide 10:** Results and limits (in-sample, Python-only)

**Stage 2: C Port and Fixed-Point** (4 slides, ~3.5 min)
- **Slide 11:** Detector in firmware, checkpoint 2
- **Slide 12:** Q16.16 fixed-point arithmetic
- **Slide 13:** Two silent bugs and their fixes
- **Slide 14:** Results and slow-boot false alarms

**Stage 3: Eight Checkpoints** (4 slides, ~3.5 min)
- **Slide 15:** 8-checkpoint flow with six fault variants
- **Slide 16:** Why it collapsed (spread, two-sided distance)
- **Slide 17:** What failed (7 of 300 clean boots above attack median)
- **Slide 18:** Spikes accumulate across checkpoints; trimming helps detection but not false alarms

**Stage 4: Floor Rule** (4 slides, ~3.5 min)
- **Slide 19:** Direction matters: faults go down, spikes go up
- **Slide 20:** The floor table (21 numbers, 140 bytes)
- **Slide 21:** Tiered response: floor halts, Mahalanobis warns
- **Slide 22:** Results: 0% clean false alarms for floor, near-perfect detection

### Part C: Phase 2 and Wrap-Up (3 slides, ~3 min)
- **Slide 23:** Seven Phase 1 limits become Phase 2 questions
- **Slide 24:** Phase 2 plan: STM32L552, DWT counters, real glitches
- **Slide 25:** Summary: four-stage journey, one lesson

**Backup slides (3 total):**
- **B1:** Stage 2 slow-boot heatmap (false-alarm detail)
- **B2:** Choosing F (0.30–0.50 window, synthetic severity sweep)
- Other backups from earlier materials as needed

---

## Part A: Introduction and Setup

### Slide 1: Title
**Figure:** *(no figure, title slide)*

**Content:**
- Title: "PMU-Based Statistical Detection of Fault Injection Attacks in Secure Boot"
- Your name, ID, institution, date
- Mentor acknowledgment

**What to say:** (30 sec) Introduce the project. "This is Phase 1 of a two-phase project. Today I'll walk through how we built and refined a fault detector, stage by stage, and what we learned about what works and what doesn't in emulation."

---

### Slide 2: The Problem and Boot Chain
**Figure:** `slide02_problem_boot_chain.png`

The figure shows a secure boot chain (boot ROM → signature check → app firmware → execution) with a voltage glitch hitting the signature check, and the consequence: unsigned code runs.

**What to say:** (40 sec) "Boot ROM firmware verifies the next stage before jumping to it. An attacker with physical access can inject a voltage or clock glitch during that verification loop, skip the check, and run their own unsigned code. The attack takes microseconds. Our goal: detect it before the boot completes."

---

### Slide 3: Literature Survey
**Figure:** `slide03_literature_defences.png`

Four cards showing prior defences: redundant execution, control-flow integrity (CFI), FAME (DWT counter anomaly checks), and CompaSeC (compiler-based fault detection).

**What to say:** (50 sec) "Others have built defences. Redundant execution repeats critical sections twice — expensive. CFI checks that jumps land where they should. FAME uses ARM's DWT counters to catch timing anomalies. CompaSeC embeds checks at compile time. Each has trade-offs: overhead, coverage, or complexity. We wanted something lightweight that could run in a boot ROM with limited code space."

**Honesty note:** The numbers on these cards (e.g., overhead %) come from the review notes and should be spot-checked against the original papers if you're asked.

---

### Slide 4: The Idea
**Figure:** `slide04_idea_timeline.png`

A timeline of boot stages with PMU checkpoints, showing how timing deviations at one checkpoint reveal a glitch.

**What to say:** (40 sec) "The core idea: boot firmware is deterministic. Each stage runs in nearly the same number of cycles every time. We insert checkpoints that snapshot the cycle counter after each stage. A skipped loop shortens one stage. We compare the timing to a statistical model of clean boots and raise an alarm if it doesn't fit."

---

### Slide 5: Testbed
**Figure:** `slide05_testbed.png`

Diagram of QEMU 8.2.2, ARM Cortex-M33, mps2-an505, SysTick timer as the cycle counter.

**What to say:** (40 sec) "Phase 1 runs in QEMU emulation on an ARM Cortex-M33. The SysTick timer counts cycles. We compile with `-DGLITCH_ATTACK` to simulate a fault: the code breaks out of a verification loop early. Real hardware and real glitches come in Phase 2. This emulation let us iterate fast and validate the algorithm before porting to silicon."

**Honesty note:** SysTick follows host time, so partial skips are invisible (ISSUE-012). The fault is compile-time, not electrical.

---

### Slide 6: Roadmap
**Figure:** `slide06_roadmap.png`

Four cards showing Stage 1 (Python simulation), Stage 2 (C port, fixed-point), Stage 3 (8 checkpoints), Stage 4 (floor rule). Each card previews what it built and what it exposed.

**What to say:** (50 sec) "Phase 1 had four stages. Stage 1 built the statistical model in Python and validated CUSUM detection. It worked, but the attacks were fake — Python-subtracted timing, not real firmware faults. Stage 2 ported the detector to C with fixed-point arithmetic. It ran in firmware, but slow boots caused false alarms. Stage 3 added more checkpoints and more fault variants, but false alarms multiplied. Stage 4 switched to a one-sided floor rule that ignores timing spikes. Let me walk through each."

---

## Part B: The Four Stages

### Stage 1: Python Simulation

#### Slide 7: main.c Flow and Fault Injection
**Figure:** `slide07_stage1_main_flow.png`

Flowchart of the original 4-checkpoint main.c, with boxes for each boot stage (ROM verify, memory init, signature verify, key derivation) and pmu_checkpoint calls. The fault injection point is highlighted in the signature verification loop's sub_b section.

**What to say:** (40 sec) "This was the original boot stub. Four checkpoints, each capturing three sub-stage timings. Checkpoint 2 is signature verification: 500 iterations in sub_a, 300 in sub_b, 200 in sub_c. The simulated fault breaks the sub_b loop early, at iteration 100. That cuts sub_b's time by about two-thirds. The question: can we detect that cut statistically?"

---

#### Slide 8: Why Mahalanobis
**Figure:** `slide08_stage1_why_mahalanobis.png`

Scatter plot and worked example showing that a 20% cut to sub_b shifts MD from 1.79 to 4.47, even though sub_b alone is only 0.3 standard deviations below the mean.

**What to say:** (50 sec) "We collect 496 clean boots at checkpoint 2. Each boot has three numbers: cycles in sub_a, sub_b, sub_c. They're correlated about 0.9: when the emulator slows down, all three go up together. A simple threshold on sub_b misses small cuts. Mahalanobis distance accounts for the correlation. Here, cutting sub_b by 20% makes it only slightly below average, but sub_a and sub_c are both high. That breaks the pattern. MD jumps from 1.79 to 4.47. That's the signal."

---

#### Slide 9: CUSUM Accumulation
**Figure:** `slide09_stage1_cusum.png`

A trace of one simulated run: MD and CUSUM statistic S over 20 boots (10 clean, 10 faulted). S rises during the glitched boots and crosses threshold H at boot 12.

**What to say:** (50 sec) "One odd boot isn't proof. CUSUM accumulates evidence. S = max(0, S + MD - k). When MD is below k, S decays toward zero. When MD is above k repeatedly, S climbs. If S crosses H, we alarm. Here k = 1.685 (70th percentile of clean MD) and H = 10.14 (99th percentile of the max S over 10,000 simulated 20-boot sequences). The first glitched boot is boot 10. By boot 12 the cumulative score crosses H and the detector alarms."

---

#### Slide 10: Stage 1 Results
**Figure:** `slide10_stage1_results.png`

Bar chart: detection rate vs severity (5/10/20/30/50% cuts), false-alarm rates, ROC AUC 0.9933. Side panel lists four limits: synthetic faults, in-sample, 10-boot window, Python-only.

**What to say:** (60 sec) "Results: at 10% cut, detection is 86%. At 20%, 99.7%. False alarms 0.1 to 0.5%. ROC AUC 0.9933. It works. But four problems. One: the faults were fake — Python subtracted cycles after the firmware recorded them. Nothing in the firmware changed. Two: it's in-sample. The attack data comes from the same 496 boots that fitted the model. Three: the test assumes 10 faulted boots in a row. A real boot decides once. With one glitched boot at 20%, detection is only 2.3%. Four: it's Python-only. A boot-time defence has to run inside the ROM. So Stage 2 ported it to C."

**Honesty note:** Link to [STATUS.md Section 2.1](../STATUS.md) for these numbers. The firmware glitch code from Stage 2 onward is real (compiled in), not Python-subtracted.

---

### Stage 2: C Port and Fixed-Point Arithmetic

#### Slide 11: Detector in Firmware
**Figure:** `slide11_stage2_main_flow.png`

Flowchart showing the firmware check_checkpoint flow after checkpoint 2: timer_ok guard, then cusum_update with the Mahalanobis distance and CUSUM logic, then alarm or continue.

**What to say:** (40 sec) "Stage 2 moved the detector into the firmware. After checkpoint 2, main.c calls check_checkpoint, which computes Mahalanobis distance in Q16.16 fixed-point, updates the CUSUM statistic, and halts if it crosses the threshold. The model parameters — mu, covariance inverse, k, H — are compiled into the binary. This is the one-shot version: k = 0, H = 1.25 times the largest clean MD, so a single glitched boot that crosses H is caught immediately."

---

#### Slide 12: Fixed-Point Arithmetic
**Figure:** `slide12_stage2_fixed_point.png`

Diagram of Q16.16 format, the bit-by-bit square root, and the Mahalanobis formula steps (delta, matrix multiply, dot product, sqrt).

**What to say:** (50 sec) "The Cortex-M33 has no FPU. We use Q16.16 fixed-point: 16 integer bits, 16 fractional. Square root is bit-by-bit, no division, so we keep the fractional part. The Mahalanobis computation: (1) delta = obs - mu, (2) y = covariance inverse times delta, (3) q = dot product, (4) distance = sqrt(q). All done in 64-bit intermediate arithmetic to avoid overflow, then clamped to the representable range."

---

#### Slide 13: Two Silent Bugs
**Figure:** `slide13_stage2_bugs.png`

Three panels: the sqrt bug (returned 0), the decimal-truncation bug (MD 15.5 became 15, threshold 15.37), and the fixes (clamp inputs, saturate distance, ceiling 4096 cycles).

**What to say:** (60 sec) "Two bugs failed silently. First, the square root returned zero for every input — wrong bit shift. That made every MD zero, so nothing ever alarmed. Second, after fixing that, I truncated the result to an integer. MD 15.5 to 16.0 became 15, and the threshold was 15.37, so the attack slipped under. The fix: keep the fractional part. A third issue: huge timing values wrapped the distance back to small numbers, failing open. The fix: clamp inputs at 32,767 cycles, saturate distance at the max representable value, and alarm immediately if any sub-stage exceeds 4096 cycles. The lesson: silent bugs are worse than crashes."

---

#### Slide 14: Stage 2 Results
**Figure:** `slide14_stage2_results.png`

Table: 1000/1000 attacks detected, 14/1000 clean false alarms (1.4%). Side note: all false alarms were slow boots (MD 11.8 to 120.7, up to 6.2x the median in one sub-stage).

**What to say:** (50 sec) "With the fixes, Stage 2 caught all 1000 attack boots. But 14 of 1000 clean boots alarmed. That's 1.4%, not the targeted 1%. All 14 were slow boots: one sub-stage up to 6.2 times the median, MD 11.8 to 120.7. These spikes don't exist in the training set of 496 boots, so the model doesn't expect them. We think it's the host pausing QEMU, not proven. The detector's size: 1,060 bytes. Total firmware 3,152 bytes. Stage 2 worked, but only for one checkpoint. Stage 3 scaled to eight."

**Backup:** Slide B1 shows a heatmap of the 14 slow boots, with their MD and the highest sub-stage value per boot.

---

### Stage 3: Eight Checkpoints and Six Fault Variants

#### Slide 15: Eight Checkpoints and Six Faults
**Figure:** `slide15_stage3_flow_faults.png`

Flowchart of main.c with 8 checkpoints (CP0 to CP7, monitoring CP1 to CP7), and six fault macros shown at their injection points: GLITCH_ATTACK (CP3 sub_b), FT-1 (CP1 sub_b), FT-2 (CP3 sub_c), FT-3 (CP7 sub_a), FT-4 (CP3 sub_a + sub_b), FT-5 (CP3 sub_c +84%).

**What to say:** (50 sec) "Stage 3 grew to 8 checkpoints. Checkpoint 0 is boot entry; we monitor CP1 through CP7. Six fault builds: the original attack at CP3 sub_b, four variants cutting different sub-stages at different checkpoints, and FT-5 — the outlier — which adds 50 extra iterations to CP3 sub_c instead of removing them. Each build: 300 boots, clean or glitched. We fit a Gaussian model per checkpoint and applied the Stage 2 rule: k = 0, H = 1.25 times max clean MD."

---

#### Slide 16: Why It Collapsed
**Figure:** `slide16_stage3_collapse.png`

Detection rates: 1/300 attack, 0/300 FT-1, 0/300 FT-2, 3/300 FT-3, 0/300 FT-4, 0/300 FT-5. Panel showing the problem: attack median MD = 3.1, but 7 of 300 clean boots have MD above that. Reasons: two-sided distance, max-based threshold.

**What to say:** (60 sec) "It collapsed. Detection: 1 out of 300 for the main attack. Zero for FT-1, FT-2, FT-4, FT-5. Three for FT-3. Why? At CP3, the attack's median MD is 3.1. But 7 of 300 clean boots have MD above 3.1. The threshold H is 20.9, set from the max clean MD times 1.25. The attack doesn't cross it. Two reasons. One: Mahalanobis is two-sided. A spike (high timing) and a cut (low timing) both increase MD, so spikes inflate the clean distribution. Two: the threshold comes from the maximum clean MD. One spiked boot in 300 sets a high bar. The attack is weaker than that spike."

---

#### Slide 17: What Failed
**Figure:** `slide17_stage3_why_failed.png`

Ranking of all 300 clean boots at CP3 by MD, with 7 boots above the attack median line (MD 3.1). Table of those 7 boots, showing which sub-stage spiked and by how much.

**What to say:** (40 sec) "Here are the 7 clean boots ranked by MD at CP3. Boot 280, MD 16.7, has sub_c = 3,588 cycles — 6.9 times the median. Boot 203, MD 11.5, has sub_b = 3,790. These spikes don't appear in the calibration set of 496 boots, but they appear 14 times in 300 boots when we switch to collect mode. That 2.3% is noisier than the 0% in calibration. Why the difference? Unknown."

---

#### Slide 18: Spikes Accumulate Across Checkpoints
**Figure:** `slide18_stage3_spikes_accumulate.png`

Left: cumulative percentage of clean boots with a spike somewhere, as we add checkpoints (CP1 alone: 2.3%, CP1–7: 14%). Right: trimming training boots above 1.5x or 3x median helps detection at CP3 (from 0.8% to 2.3%) but false alarms grow (from 2.3% to 15.7% across CP1–7).

**What to say:** (50 sec) "The more checkpoints we monitor, the more chances for a spike. At CP1 alone, 2.3% of clean boots have a spike above 1.5x the median. Across CP1 to CP7, 14%. That's a 1 in 7 chance. Trimming spiked boots from training helps detection at CP3 — from 0.8% to 2.3% — but false alarms grow across all checkpoints, from 9% to 15.7%. The fundamental problem: two-sided distance treats up and down the same, but our faults only go one way."

---

### Stage 4: Floor Rule (One-Sided Test)

#### Slide 19: Direction Matters
**Figure:** `slide19_stage4_direction.png`

Scatter plot of CP3 sub_b timing (log scale, normalized by median): clean boots cluster near 1.0x, attack boots cluster at 0.1x, timing spikes spread to 5x. Floor alarm zone highlighted (below 0.45x). Annotations: "skipped loops only go down", "spikes only go up".

**What to say:** (50 sec) "Stage 4 insight: skipped loops only shorten a stage, and spikes only lengthen it. They go opposite directions. Mahalanobis counts both. A floor test only asks: is any sub-stage suspiciously short? Here's CP3 sub_b, normalized by the clean median. Clean boots cluster near 1.0x. Attack boots land at 0.1x. Spikes scatter up to 5x. The floor at 0.45x catches the attacks and ignores the spikes. Exception: FT-5 adds work, making the stage longer. Only Mahalanobis catches that, so we kept both rules."

---

#### Slide 20: The Floor Table
**Figure:** `slide20_stage4_floor_table.png`

The 7×3 FLOOR_TABLE from src/floor_table.h, with CP3 highlighted. Right panel: floor_check C code (3 lines), worked example at CP3 (clean median 690.5/668/522, floor 310/300/234), and example boots (clean passes, spiked boot 203 passes, attack boot fails at sub_b = 93 < 300).

**What to say:** (60 sec) "The floor rule: 21 numbers. For each checkpoint and sub-stage, the floor is 0.45 times the clean median, rounded down. This table comes from 300 calibration boots. The code: 3 lines. Loop over the three sub-stages; if any sub-stage is below its floor, return 1. At CP3, the floors are 310, 300, 234 cycles. A clean boot with sub_b = 860 passes. The spiked boot 203, sub_b = 3790, passes — every value above its floor. The attack boot, sub_b = 93, fails. 93 < 300, so the floor halts the boot. Code size: 92 bytes plus 48-byte table = 140 bytes."

**Honesty note:** The footnote explains calibration drift: fresh validation boots had medians 1 to 25% higher, so the floors acted as 0.36 to 0.44 of the fresh median, still within the usable 0.30–0.50 range. This is a dataset artifact, not a flaw in the rule.

---

#### Slide 21: Tiered Response
**Figure:** `slide21_stage4_tiered_flow.png`

Flowchart of check_checkpoint in main.c: timer_ok guard, then floor_check (if alarm, halt), then cusum_update at CP3 only (if alarm, warn only). Two parallel streams for floor halts and Mahalanobis warnings.

**What to say:** (50 sec) "The final detector uses both rules. After each checkpoint, timer_ok checks the timer is sane. Then floor_check runs for every checkpoint. If the floor alarms, the firmware prints FLOOR_ALARM and halts. If the floor passes, cusum_update runs at checkpoint 3 only. If Mahalanobis alarms, it prints MAHALANOBIS_ALARM but continues — a warning, not a halt. This tiered response gives the floor rule priority: it's faster, smaller, and has zero false alarms. Mahalanobis catches the FT-5 outlier. The timer guard is untested (ISSUE-019): it's meant to fail open if the timer wrapped, but we didn't validate that path."

---

#### Slide 22: Stage 4 Results
**Figure:** `slide22_stage4_results.png`

Table: floor rule caught 299 to 300 of 300 for attack/FT-1/FT-2/FT-3/FT-4 (FT-3 missed one), 0 of 300 for FT-5. Clean false alarms: floor 0/300, Mahalanobis 17/300 (5.7%). Mahalanobis caught attack/FT-2/FT-4/FT-5 perfectly (300/300).

**What to say:** (60 sec) "Fresh validation boots, 300 per build. Floor rule: zero false alarms on clean boots. Detection: 299 or 300 out of 300 for every fault except FT-3, which missed one boot, and FT-5, which the floor cannot see because FT-5 makes the stage longer, not shorter. Mahalanobis: 5.7% false alarms (17 of 300 clean boots), but it catches FT-5 perfectly — all 300. Halting-build test: 293 clean boots completed, 0 halted, 7 completed with a warning. Every faulted boot halted except FT-5, which warned. Stage 4 met the goal."

**Backup:** Slide B2 shows how F was chosen: the usable range is 0.30 to 0.50; F = 0.45 catches faults starting around 40% severity, and misses less than 2% by F = 0.30. Below F = 0.30, too many faults slip through. Above F = 0.50, healthy checkpoints start alarming.

**Honesty note:** F was chosen after seeing the fault data (not blind); synthetic severity sweeps in QEMU are flat due to ISSUE-012; the Mahalanobis false-alarm gap (1.4% in Stage 2, 5.7% here) is unexplained.

---

## Part C: Phase 2 and Summary

### Slide 23: Seven Limits Become Seven Questions
**Figure:** `slide23_phase2_questions.png`

Seven rows: each Phase 1 limit on the left (compile-time faults, QEMU timer hides partial skips, floor needs 60% cut, host spikes broke Mahalanobis, faults only at CP1/3/7, build-to-build variation, per-checkpoint rules only) maps to a Phase 2 question on the right (does a real glitch change timing like a skipped loop? the real severity curve with DWT counters; the mildest fault on hardware; do spikes exist on silicon?; inject at every checkpoint; recalibrate per build; multi-checkpoint fusion). Three rows marked with "(*)" .

**What to say:** (60 sec) "Every Phase 1 limit becomes a Phase 2 question. One: faults were compile-time macros. Does a real voltage glitch change timing like a skipped loop? Two: QEMU's timer hides partial skips. What's the real severity curve with DWT counters on hardware? Three: the floor needs about a 60% cut and can't catch extra work like FT-5. What's the mildest fault we can catch on hardware, and can we test for longer stages? Four: host spikes broke Mahalanobis. Do spikes exist on silicon? If not, does Mahalanobis work there? Five: faults were only at CP1, CP3, CP7. Can we inject at every checkpoint? Six: same code ran 28% differently across builds. Is recalibrating per build enough? Seven: per-checkpoint rules only. Can we fuse checkpoints without multiplying false alarms? The asterisks mark questions that follow from the Phase 1 results but aren't yet written in STATUS.md Section 7. I'll confirm those with my mentor."

**Honesty note:** The three "(*)" rows are proposed additions, not yet in STATUS.md Phase 2 plan.

---

### Slide 24: Phase 2 Plan
**Figure:** `slide24_phase2_plan.png`

Table comparing Phase 1 (QEMU, SysTick, compile-time faults, one rule per checkpoint, infinite-loop alarm, 7 builds × 300 boots, no comparison) to Phase 2 (STM32L552, DWT counters, debugger-based injection or voltage glitching, multi-checkpoint fusion, TrustZone-M lockout, larger datasets, comparison against redundant execution).

**What to say:** (50 sec) "Phase 2 replaces every stand-in. Platform: STM32L552, a real Cortex-M33 with TrustZone-M. Counters: DWT gives us cycle count, CPI, load-store count, and folded instructions. Faults: debugger-based injection for repeatability, optionally voltage glitching for realism. Detection: multi-checkpoint fusion; we'll revisit Stein's Lemma for combining p-values without multiplying false alarms. Alarm: TrustZone-M lockout, not just a loop. Data: larger glitched-boot datasets. Comparison: benchmark against redundant execution. Phase 2 is about 400 hours."

---

### Slide 25: Summary
**Figure:** `slide25_summary.png`

Four-stage journey diagram (same as slide 6 roadmap, with results added per stage). Bottom text: "Lesson: skipped loops shorten a stage and spikes lengthen it, so a one-sided test wins. Extra work (FT-5) is the exception."

**What to say:** (50 sec) "To summarize Phase 1: Stage 1 validated CUSUM in Python, but the faults were fake and it needed a 10-boot window. Stage 2 ported to C with fixed-point, caught all attacks, but 1.4% of clean boots alarmed due to slow spikes. Stage 3 scaled to 8 checkpoints and 6 fault types, but false alarms multiplied because Mahalanobis treats up and down the same. Stage 4 switched to a one-sided floor rule: zero false alarms, near-perfect detection for shortened stages, and Mahalanobis warns for the FT-5 outlier. The lesson: skipped loops shorten a stage and spikes lengthen it, so a one-sided test wins. Extra work is the exception. That's what Phase 1 delivered. Thank you."

---

## Backup Slides

### B1: Stage 2 Slow-Boot Heatmap
**Figure:** `backupB1_stage2_slow_boots.png`

Heatmap of the 14 false-alarm boots from Stage 2, showing their boot ID, MD, and which sub-stage value was highest (colored from normal to extreme).

**Use if asked:** "Here's a closer look at the 14 slow boots. Boot 280: MD 120.7, sub_c was 6.2x the median. Boot 203: MD 92.9, sub_b was 5.3x. These are way above the attack's MD of 22.3. All 14 had at least one sub-stage more than 2x the median. These spikes don't exist in the 496-boot training set, which is why the model doesn't expect them."

---

### B2: Choosing F (Floor Fraction)
**Figure:** `backupB2_stage4_choosing_f.png`

Three panels: (1) faults missed vs F (misses 94% at F=0.20, drops to 1.7% at F=0.30, under 0.5% from F=0.40 onward); (2) alarms at untouched checkpoints vs F (stays at 0% until F=0.50, then jumps to 1% at F=0.55 and 9.2% at F=0.70); (3) synthetic severity sweep (floor detection 0/26/33/96% at 30/40/50/60% cuts, reliable from about 60%).

**Use if asked:** "The usable range for F is 0.30 to 0.50. Below 0.30, too many faults slip through. Above 0.50, healthy checkpoints start alarming. At F = 0.45, we miss less than 1% of real faults and the alarm rate at untouched checkpoints is zero. The right-hand panel shows synthetic cuts to CP3 sub_b: the floor catches about 26% of 40% cuts, 96% of 60% cuts. Because QEMU's timer follows host time, partial skips are invisible (ISSUE-012), so this is an upper bound. On hardware with DWT, we'll measure the real curve."

**Honesty note:** F was chosen after seeing the fault data, not blind. The fresh boots validated the calibration, not the choice of F itself.

---

## Likely Questions and Answers

**Q1: Why didn't you test on real hardware in Phase 1?**
A: Phase 1 was algorithm development. Emulation let us iterate fast without waiting for hardware bring-up. We collected 2,100 boots in Phase 1; doing that in a debugger with manual fault injection would have taken weeks per experiment. Phase 2 moves to STM32L552 now that the detector design is validated.

**Q2: How do you know the spikes are from the host and not the firmware?**
A: We don't, definitively. The spikes only appeared when we switched from the halting firmware (which alarms and stops) to collect mode (which records and continues). The timing pattern — one sub-stage 3 to 6 times longer while the others stay normal — suggests a host pause, not firmware branching. Phase 2 on silicon will test whether spikes exist there.

**Q3: What happens if the attacker glitches the detector itself?**
A: The detector runs after every stage, so glitching it would itself be a timing anomaly. The floor rule is 3 lines of C; there are no loops to skip in floor_check. The Mahalanobis code has loops, but they're fixed-iteration (3 elements, 7 checkpoints). A glitch that breaks the loop would either crash (out-of-bounds read) or produce a nonsense distance, likely triggering the 4096-cycle ceiling. That said, we haven't explicitly tested this. It's on the Phase 2 list.

**Q4: Why does the floor rule miss FT-5?**
A: FT-5 adds 50 iterations to CP3 sub_c instead of removing them. That makes the stage 84% longer, not shorter. The floor only alarms when a value is below its threshold, so it can't catch extra work. Mahalanobis sees it because MD measures distance in any direction. That's why we kept both rules: floor for shortened stages (zero false alarms), Mahalanobis for the FT-5 outlier (some false alarms, but acceptable as a warning).

**Q5: What's the 1.25 factor in the one-shot threshold?**
A: It's a margin. The threshold H = 1.25 × max clean MD. Without the margin, the largest clean boot would sit exactly on the threshold, and any noise would cause a false alarm. 1.25 gives a 25% buffer. We chose it empirically: 1.1 gave too many false alarms in Stage 2, 1.5 missed some attacks in early tests, 1.25 worked. Phase 2 will revisit this with cross-validation on hardware.

**Q6: Can the attacker train the model with glitched boots to poison it?**
A: The model is calibrated offline during manufacturing or firmware provisioning, then compiled into the ROM. An attacker with physical access during boot can glitch the boot, but they can't rewrite the calibration data in ROM. If they could rewrite ROM, they wouldn't need a glitch — they'd just replace the firmware. The threat model is: attacker has transient physical access (glitching equipment) but not persistent write access to boot ROM.

**Q7: Why did the same code run 28% differently across builds (ISSUE-016)?**
A: We don't know. The source, compiler flags, and hardware are identical. It's not the glitch: it happens in clean boots too, and across builds with different faults. It's not optimization non-determinism: the .elf binaries are bit-identical across re-compiles of the same source. Our hypothesis: QEMU's instruction timing model has some hidden state that shifts between builds, or the host's CPU governs timing in a way that depends on the binary's layout. Phase 2 on hardware will show whether this is real or an emulator artifact.

**Q8: What's the false-alarm rate across a real boot?**
A: In Stage 4, the floor rule had 0 false alarms in 300 clean boots (95% CI: 0 to 1.3%). Mahalanobis had 17/300 = 5.7%, but it only warns at CP3, doesn't halt. Across 7 monitored checkpoints, 7 of 293 clean boots got a Mahalanobis warning somewhere. The floor never halted a clean boot. Phase 2 will measure this on hardware with larger datasets.

**Q9: How does this compare to redundant execution?**
A: We haven't implemented redundant execution yet. That's a Phase 2 task. Conceptually, redundant execution repeats critical sections twice and compares the results. It catches faults that change control flow or data, but doubles execution time for those sections. The floor rule runs once and adds about 21 comparisons (7 checkpoints × 3 sub-stages) plus the table lookup. In Phase 2 we'll measure overhead and compare detection rates side-by-side.

**Q10: Why is F = 0.45 the right choice, not 0.40 or 0.50?**
A: It's not "the" right choice, it's "a" valid choice. The usable range is 0.30 to 0.50. At F = 0.30, we miss 1.7% of faults (the mildest cuts). At F = 0.50, we start getting alarms at healthy checkpoints (1% by F = 0.55). F = 0.45 is in the middle of that range: it misses under 0.5% of faults and causes zero healthy-checkpoint alarms in our data. The trade-off is between "catch the mildest faults" and "don't alarm on a spike in an untouched stage." We chose to lean toward catching faults.

---

## Delivery Notes

1. **Timing discipline:** This deck can run long if you elaborate. Stick to 1 minute per slide in Part B (stages). The figures do the explaining; your words add context and link slides together.

2. **Pointer to figures:** When presenting, refer to the figure explicitly. "On the left, you see..." "The orange dots are..." People miss details if you don't direct their eyes.

3. **Honesty first:** The Phase 1 limits are not failures, they're boundaries. Frame them as "what we learned" and "what Phase 2 will test," not "what went wrong." The panel respects honesty more than perfection.

4. **Status.md is the source of truth:** If a number here ever conflicts with STATUS.md, STATUS.md wins. During your talk, you can say "the full results are in STATUS.md, Section 2" if asked for more detail.

5. **The three "(*)" rows on slide 23:** Explicitly say "these three follow from the Phase 1 results but aren't yet written in STATUS.md Section 7; I'll confirm them with my mentor." Don't present them as decided facts.

6. **FT-5 exception:** Mention it every time you say "faults make stages shorter": "except FT-5, which adds work." It's the one counterexample, and ignoring it would be dishonest.

7. **Build-to-build variation (ISSUE-016):** If asked, say "we measured it, we don't have an explanation yet, Phase 2 will test whether it exists on hardware." Don't speculate during the talk.

8. **Figure 3 vs shipped model:** The Stage 4 results figures (slides 20, 22) show the calibration model and fresh validation boots. The shipped firmware in src/ has a slightly different model (from data/cal_clean.csv, H = 7.487). The methods are identical; the numbers differ by about 10%. If asked, say "the methods are the same; the plot uses one dataset and the firmware uses another, both from the same experimental setup."

9. **Questions you can't answer:** "That's a Phase 2 question" is a valid answer. Don't guess.

10. **Rehearse the lesson:** The lesson on slide 25 is the punchline. "Skipped loops shorten a stage and spikes lengthen it, so a one-sided test wins. Extra work is the exception." Practice saying it out loud until it's automatic.

---

## Final Checklist

Before the review:

- [ ] Render all 26 figures (`python3 review/figures/make_story_figures.py` from pmu_bootrom/)
- [ ] Insert figures into your slide deck (PowerPoint, Beamer, Google Slides)
- [ ] Verify the numbers on slides 10, 14, 16, 22 match STATUS.md Section 2
- [ ] Spot-check the literature survey numbers (slide 3) against the original papers
- [ ] Confirm the three "(*)" Phase 2 items (slide 23) with your mentor
- [ ] Add the calibration-drift footnote to slide 20 (it's in the figure)
- [ ] Add the FT-5 exception note to slide 19 subtitle (it's in the figure)
- [ ] Rehearse out loud once, time yourself, adjust if over 23 minutes
- [ ] Print or bookmark STATUS.md, KNOWN_ISSUES.md, and this guide for reference during Q&A

Good luck. You built something that works, you know its limits, and you're honest about both. That's what a review panel wants to see.
