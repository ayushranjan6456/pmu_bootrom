# Phase 1 Review: Slide Deck Guide

Replaces the 16-slide plan in [PPT_OUTLINE.md](PPT_OUTLINE.md), which describes the old 4-checkpoint firmware. Every number below is from [STATUS.md](../STATUS.md), [FAULT_MODELS.md](../FAULT_MODELS.md) or `results/slide_plots_data.txt`. Re-check against those files before typing a number onto a slide.

**Format:** 15 slides, about 23.5 minutes of speaking, leaving 1 to 1.5 minutes of buffer in a 25-minute slot. Live demo is optional (see the end); the story works without it. Backup slides are for questions only.

**The one-sentence story (say it in slide 1 and slide 15):** *We built a software-only timing detector for a skipped signature check in a simulated bootrom. Our first statistical detector (Mahalanobis) was unreliable on realistic data, so we added a simple one-sided floor rule that halts the boot with no false alarms, and we measured both honestly.*

| # | Slide | Min | Figure |
|---|-------|----:|--------|
| 1 | Title | 0.5 | none |
| 2 | Problem | 1.5 | none |
| 3 | Related work and the gap | 1.5 | none |
| 4 | Idea and approach | 1.0 | block diagram |
| 5 | Testbed and firmware | 1.5 | boot-flow diagram |
| 6 | Fault models | 1.5 | fig1 |
| 7 | Detector 1: Mahalanobis + CUSUM | 1.5 | formula |
| 8 | Why Mahalanobis fell short | 2.5 | fig2 (+ fig6 backup) |
| 9 | Detector 2: the floor, and the tiered design | 2.0 | fig5 |
| 10 | Validation results | 3.0 | table + fig3 |
| 11 | How big a fault can we see? | 1.5 | fig4 |
| 12 | Embedded engineering | 1.0 | small table |
| 13 | Limitations | 1.5 | none |
| 14 | Phase 2 plan | 1.5 | roadmap |
| 15 | Summary and asks | 1.0 | none |

Design rules: one message per slide, the slide title is the takeaway sentence, at most 5 bullets, figures large and unshared. The figures already use one palette (blue = clean, orange = faulted, violet = Mahalanobis, green = floor); reuse it for diagrams so colours mean the same thing throughout.

---

## 1. Title (0.5 min)
**On the slide:** PMU-Based Statistical Detection of Fault Injection Attacks in Secure Boot. Ayush Ranjan (EE24M504), M.Tech, IIT Madras. Mentor organisation: Texas Instruments. Phase 1 review.

**Say:** Name, project, and the one-sentence story above. Tell the panel the structure: problem, approach, what worked, what did not, what is next.

---

## 2. Problem (1.5 min)
**Title:** The bootrom is the root of trust, and a glitch can make it skip its own check

**On the slide:**
- BOOTROM runs first, is immutable, and verifies the next stage's signature
- A voltage or clock glitch can skip instructions, for example exit the verification loop early, so an unsigned image boots
- Hardware defences (voltage and clock sensors, redundant execution) cost area, power and latency
- Question: can software watch on-chip timing and flag a skipped check while the bootrom is still running?

**Say:** One small code picture helps (a verification loop with an early exit). Stress that the cost of a hardware sensor is why a software-only option is worth studying, and that this is a question, not a claim that it replaces hardware.

**If asked:** "Why timing?" A skipped loop executes fewer instructions, so the stage finishes in fewer cycles. That is the observable.

---

## 3. Related work and the gap (1.5 min)
**Title:** Existing defences are hardware or redundancy; statistical timing detection inside a boot ROM is thin

**On the slide:** three columns: hardware sensors, software redundancy / algorithm checks, our angle. Under each, one limitation. Footer: "20 papers surveyed, [Literature_Survey]".

**Say:** Use the three or four strongest papers from [LITERATURE_SLIDES.md](LITERATURE_SLIDES.md) (real attacks on deployed boot ROMs, then the defences). State the gap carefully: *within the papers we surveyed* we did not find statistical detection from on-chip timing telemetry sized for a ROM. Mahalanobis distance and CUSUM are standard tools; the contribution is applying them here and fitting them into a ROM.

**Do not:** put our detection rates beside the papers' numbers (different platforms and faults), or claim a systematic prior-art search.

---

## 4. Idea and approach (1 min)
**Title:** Learn what a clean boot looks like, flag boots that deviate

**On the slide (diagram):** clean boots → timing per checkpoint → model → score at boot time → alarm / continue. Mark "Phase 1: QEMU, SysTick" and "Phase 2: STM32L552, DWT/PMU".

**Say:** Offline we record timing of many clean boots. In firmware, each checkpoint compares its timing to that model. Be upfront now: SysTick stands in for the PMU counters because QEMU has no DWT events. The project title says PMU; Phase 1 proves the algorithm, Phase 2 uses the real counters.

---

## 5. Testbed and firmware (1.5 min)
**Title:** An 8-checkpoint bootrom stub on emulated Cortex-M33

**On the slide:** boot-flow diagram CP0 to CP7 (boot start, hardware init, boot mode, **signature verify**, decrypt, integrity, memory setup, handoff), each with sub-stages a, b, c; QEMU `mps2-an505`; SysTick as cycle counter; 3 numbers per checkpoint.

**Say:** Each stage is busy loops, not real crypto, so timing is controllable. Each checkpoint records time for sub-stages a, b, c. CP3, signature verification, is the main target. The firmware grew from 4 checkpoints to 8 during Phase 1 to be closer to a real boot flow.

**Note:** CP0 has no sub-stages; detectors run at CP1 to CP7.

---

## 6. Fault models (1.5 min)
**Title:** Six simulated faults: five skipped loops and one extra loop

**On the slide:** fig1 (`fig1_clean_vs_faulted_timing.png`). Short legend table: attack (CP3 b), FT-1 (CP1 b), FT-2 (CP3 c), FT-3 (CP7 a), FT-4 (CP3 a+b), FT-5 (CP3 c, +84%).

**Say:** Read the picture: blue is 300 clean boots per sub-stage, orange is the faulted sub-stage. Skipped loops land at 10 to 25% of normal; the dashed line is where our final rule sits. Note the blue dots *above* the cloud: clean boots occasionally run several times slower. That observation drives slides 8 and 9, so plant it here ("remember the blue outliers on top").

**State clearly:** these are compile-time loop removals that model a skipped check. They are not electrical glitches and not partial skips (QEMU cannot do partial skips, slide 11).

---

## 7. Detector 1: Mahalanobis + CUSUM (1.5 min)
**Title:** First detector: how far is this boot from the clean cloud?

**On the slide:**
- Feature vector at CP3: [sub_a, sub_b, sub_c]
- MD = sqrt((x - mu)' S^-1 (x - mu)), fitted on 300 clean boots
- Why multivariate: sub-stages move together (correlation about 0.9), so a break in the pattern stands out
- Firmware: one-shot threshold, k = 0, H = 1.25 x largest clean MD; Q16.16 fixed point, no FPU
- Python version: sequential CUSUM over 20-boot windows

**Say:** The firmware calls the CUSUM update once per boot, so it is really a calibrated one-shot threshold; the sequential form is in the Python simulation and is Phase 2 for firmware. Say this yourself before a panel member does.

---

## 8. Why Mahalanobis fell short (2.5 min)
**Title:** The score ranks faults well, but the threshold cannot separate faults from timing spikes

**On the slide:** fig2 (left: Mahalanobis histogram, attack inside the clean range; right: floor view). Three bullets underneath:
- About 14% of clean boots have an upward timing spike somewhere in CP1 to CP7 (42 of 300 above 1.5x median)
- A two-sided distance treats a spike like a fault; a max-based threshold is set by the most extreme training boot
- Score quality is fine (AUC 0.97 to 0.98); the cut-off is the problem

**Say, in order:**
1. On the earlier 4-checkpoint firmware this detector gave 14/1000 false alarms and 1000/1000 detections. That training set had no spikes.
2. On the 8-checkpoint data, fitted on all 300 clean boots, the threshold lands at 20.9 and the attack's median distance is only 3.1: 1 of 300 attacks detected (fig2 left).
3. What we shipped: filter outliers (2.5 x IQR removes 9 of 300 boots) and refit, H = 7.49. That detects 300/300 attacks but still false-alarms on 5.7% of fresh clean boots (17/300). Halting on that would deny service to about 1 in 18 good boots.
4. Possible rescue: trimming spiked boots helps at CP3 only (about 2% false alarms) and does not extend across CP1 to CP7 (about 16%). Detail in [docs/MAHALANOBIS_ANALYSIS.md](../docs/MAHALANOBIS_ANALYSIS.md); keep fig6 as a backup slide.

**Why this is a strength:** you found the failure, diagnosed it with data, and changed the design. Present it as a result, not an apology.

**Hedge correctly:** why the earlier training set had no spikes is *probably* that the halting build dropped boots where it alarmed (4 ids missing); that is consistent with the data, not proven.

---

## 9. Detector 2: the floor, and the tiered design (2 min)
**Title:** A one-sided floor halts the boot; Mahalanobis only warns

**On the slide:** the rule `alarm if any sub-stage < 0.45 x its clean median` (7 checkpoints x 3 sub-stages = 21 constants, integer compares, 140 bytes), fig5 (choice of f), and a two-row table:

| | Floor | Mahalanobis |
|---|---|---|
| Where | CP1 to CP7 | CP3 only |
| Response | **halt boot** | **warn, continue** |
| Why | no false alarms on clean data, so halting is safe | 5.7% false alarms, so halting is not |

**Say:** Faults here only make a sub-stage shorter, and the median is not moved by upward spikes, so a one-sided rule ignores the spikes. The response is tiered by confidence, which is normal embedded practice. Fig5: f = 0.45 sits inside a usable window of about 0.30 to 0.50; below 0.30 faults slip through, above about 0.55 untouched checkpoints in other builds start to alarm.

**Say honestly:** f was chosen after seeing fault data; the fresh validation (next slide) checks the calibration, not the choice of rule. FT-5 (extra work) is invisible to a floor and is covered only by the Mahalanobis warning.

---

## 10. Validation results (3 min)
**Title:** On fresh boots the floor halts 99% or more of skipped-loop faults with no false alarms

**On the slide:** the table below plus fig3 on a second panel or as the next click.

300 fresh boots per build, firmware's own output, load 1.0 to 1.5 ([results/validation_8cp.txt](../results/validation_8cp.txt)):

| Build | Floor (own CP) | Mahalanobis (CP3) |
|---|---:|---:|
| Clean (false alarms) | 0 / 300 | 17 / 300 (5.7%) |
| Attack, CP3 b | 299 / 300 | 300 / 300 |
| FT-1, CP1 b | 299 / 300 | not monitored |
| FT-2, CP3 c | 300 / 300 | 300 / 300 |
| FT-3, CP7 a | 298 / 300 | not monitored |
| FT-4, CP3 a+b | 300 / 300 | 300 / 300 |
| FT-5, CP3 c +84% | 0 / 300 | 300 / 300 |

Then the real halting builds (300 boots each, [results/validation_halting.log](../results/validation_halting.log)): clean 0 halted and 7 completed with a warning; attack, FT-1, FT-2, FT-4: 300/300 halted; FT-3: 299/300; FT-5: 0 halted, 300 warned.

**Say:** Three evidence layers: (a) fresh collection matched by a Python mirror on all 2100 boots (0 disagreements), so the firmware does what the analysis says; (b) held-out splits (fig3: floor about 100% vs one-shot Mahalanobis 1 to 18% unfiltered); (c) real halting builds. Read the intervals: 0/300 means a 95% upper bound of 1.3% false alarms, not zero.

**Be ready to say:** the Mahalanobis column looks strong because the faults are large and the model is the filtered one; do not present it as evidence it is the better detector.

---

## 11. How big a fault can we see? (1.5 min)
**Title:** Large faults are caught reliably; reductions below about a third are not

**On the slide:** fig4 (synthetic severity sweep, held-out) and one line: "QEMU cannot produce partial skips".

**Say:** Because QEMU's SysTick follows host time, skipping 99% of a loop looks the same as skipping 0% (measured: median sub_b changes about 4%, within noise; removing the whole loop drops it about 84%). So the severity curve is synthetic: scale clean CP3 boots by (1 - r). The floor needs roughly a 55 to 60% reduction to detect reliably (about 0% at 30%, 26% at 40%, 33% at 50%, 96% at 60% for sub_b alone). Faults in real silicon can be subtle, which is exactly why Phase 2 needs hardware counters.

**Do not claim** firmware sensitivity to subtle faults.

---

## 12. Embedded engineering (1 min)
**Title:** It fits: 1.2 KB of detector code, no FPU, no libgcc

**On the slide:** small table: floor module 140 B; Mahalanobis module 1060 B; whole firmware 4692 B text (`-O0`); Q16.16, division-free integer square root. Underneath, "bugs found and fixed": SysTick init, ROC mixing, sqrt truncation, a fail-open overflow (a huge timing value wrapped to zero and was not flagged), plus a timer-validity guard.

**Say:** The overflow is the story to tell: a security-relevant flaw, found, fixed with saturation, verified by host test. Mention the timer guard skips both checks when SysTick readings are inconsistent (fail-open); say plainly it has never fired in validation and is untested in firmware.

**Not measured:** latency. Do not quote a cycle count.

---

## 13. Limitations (1.5 min)
**Title:** What Phase 1 does not show

**On the slide (5 bullets):**
- Faults are compile-time loop removals at three checkpoints (CP1, CP3, CP7), not electrical glitches; CP2, CP4, CP5, CP6 were exercised only by clean boots
- QEMU timing follows host time: no partial skips, spikes from host pauses
- Thresholds are tied to one binary; the same code varies up to about 28% across builds (cause unknown), so each build must be calibrated
- f chosen after seeing faults; little headroom (untouched sub-stages go down to 0.51 of the clean median)
- SysTick is not the PMU; extra-work faults (FT-5) are only warned

**Say:** Pre-empt the hard questions in one pass. Link: [STATUS.md](../STATUS.md#6-limitations) and [KNOWN_ISSUES.md](../KNOWN_ISSUES.md).

---

## 14. Phase 2 plan (1.5 min)
**Title:** Next: real counters, real faults

**On the slide (roadmap, left to right):** STM32L552 port with DWT (CYCCNT, CPICNT, LSUCNT, FOLDCNT) → measure hardware timing noise and whether spikes persist → debugger-based fault injection with partial skips → multi-checkpoint sequential CUSUM, retry-then-lockout response, latency → comparison with redundant execution. Effort: about 400 hours ([STATUS.md](../STATUS.md#7-phase-2-plan)).

**Say:** Each limitation on slide 13 maps to a Phase 2 item. The first hardware measurement decides whether the Mahalanobis detector is worth reviving: if hardware counters have no host-pause spikes, the two-sided score may work as originally intended (a hypothesis, not a result).

---

## 15. Summary and asks (1 min)
**Title:** What we have and what we need

**On the slide:**
- Built: 8-checkpoint bootrom, six fault models, two detectors in firmware (140 B and 1060 B), validated on 2100 fresh boots and real halting builds
- Found: a statistical detector that looks excellent on clean-ish data fails on realistic timing spikes; a one-sided floor is robust, so the response is tiered
- Honest limits: simulated faults, QEMU timing, calibrated per build
- Asks: (1) priority for Phase 2: breadth of fault models or formal bounds; (2) what false-alarm budget a bootrom can tolerate

Close by repeating the one-sentence story.

---

## Backup slides (do not present unless asked)
- **B1 Fig6:** Mahalanobis with spike trimming (worst-split detection and false alarms vs trim level)
- **B2 Choice of f:** fig5 table, headroom, cross-build alarms
- **B3 Frozen 4-checkpoint result:** 14/1000 false alarms, 1000/1000 detected, spike-free training set caveat
- **B4 Fixed-point details:** Q16.16 error (1.2% of the largest inverse-covariance entry), H computed on fixed-point distances
- **B5 Effort and scope versus the Phase 0 proposal:** table from STATUS.md Sections 4 and 5; 600 hours as an allocation, not a time log
- **B6 Gaussian assumption:** Shapiro-Wilk rejects it; thresholds are empirical

## Likely questions (prep short answers; the long ones are in [QA_BACKUP.md](QA_BACKUP.md))
1. *Your faults are huge; would a plain threshold do?* Yes, that is what the floor is. The statistical detector adds value only if faults are subtler, which QEMU cannot test.
2. *Why keep Mahalanobis at all?* It is the only thing that sees FT-5 (upward faults) and it carries Phase 2.
3. *Is 0.45 just tuned?* Partly. It was chosen after seeing faults; the usable window is 0.30 to 0.50 and the fresh validation checks the calibration.
4. *Why not halt on Mahalanobis?* 5.7% of clean boots would halt.
5. *Where is the PMU?* QEMU does not provide DWT events; SysTick is the stand-in.
6. *What is novel?* The application and embedded port, not the statistics.
7. *Can an attacker avoid detection?* Possibly; an attacker who also pads timing, or a fault that does not change timing, evades it. Out of Phase 1 scope.

## Demo (optional, 2 to 3 minutes, only if time allows)
Prefer a pre-recorded terminal. Show a clean boot completing and a faulted build halting with `ALARM,floor,3`. Old [DEMO_SCRIPT.md](DEMO_SCRIPT.md) describes the 4-checkpoint build and needs updating before use; use `make app_attack.elf` (non-halting, prints the alarm) or build the halting variant as in `scripts/test_halting_build.sh`. About 1 in 18 clean boots prints a Mahalanobis warning, so have a retake ready.

## Rehearsal plan
- Run once with a timer; target 22 to 23 minutes so questions during the talk do not overrun
- If short of time, compress slide 3 and slide 12 first, never slides 8 to 10
- Rehearse the transition slide 6 to 8 (spikes) and slide 8 to 9 (why a floor), the two moments where the story can lose the audience
