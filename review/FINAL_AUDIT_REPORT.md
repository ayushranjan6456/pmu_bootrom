# Phase 1 Final Audit Report

**Target:** tag `phase1-review-freeze-2` (commit 02fedee). The working tree equals the tag plus the survey file you moved into `Literature_Survey/` (untracked). Line numbers below refer to the tag.
**Date:** 2026-11-10
**Method:** six independent reviewers (code, statistics, documentation, reproducibility and demo, panel red-team, chronology), each in a scratch copy; the real repository was not modified. I re-ran the load-bearing findings myself.
**Evidence tags:** **[V]** I reproduced it myself. **[A]** A reviewer reported it and I did not re-run it.
**Numbers in this report are audit measurements.** [STATUS.md](../STATUS.md) stays the source of truth for results.

This report is candid. It is for you, not for the panel; decide whether it belongs in the repository you hand in.

---

## 1. Verdict

**Ready with fixes.** All six reviewers returned "Ready with fixes" and none found a blocker in code, data or reported numbers. Everything in STATUS.md that was recomputed reproduces.

The risk is in how three results are worded, plus one item only you can settle:

1. The shipped detector does not catch a fault that skips all of signature verification (F-01).
2. The Python detection table describes 10 consecutive faulted boots, not one boot (F-02).
3. The firmware threshold is set by a single clean boot (F-03).
4. The effort figures in different documents disagree (F-04).

Fix F-01 to F-07 before you build slides. None of them needs a change to `src/`, `scripts/`, `data/` or the Makefile. F-04 needs your decision.

## 2. What holds up

| Area | Result |
|---|---|
| Build | 0 compiler warnings; text 3152, bss 64, detector object 1060 bytes [A] |
| Boots (QEMU 8.2.2) | 300 clean boots: 298 complete, 2 alarm [V]; 10 of 10 attack boots alarm [A] |
| Model | `model.npz` regenerates (k 1.6854, H99 10.1414); calibration script prints the same 14 constants as `src/cusum_detector.c` [A] |
| Python detector | Detection table and AUC 0.9933 reproduce exactly at seed 0 and stay within noise over 8 other seeds [A] |
| Baseline table | All 18 cells reproduce exactly [A] |
| False alarms | 23 boots: MD 11.8 to 171.5, z +5.2 to +68.9, pooled 23/2000, Wilson 0.77 to 1.72%, Fisher p = 0.40 [A] |
| Real glitch | MD 19.08 to 31.89; H = 1.25 x 8.669 = 10.8367 [V] |
| Shipped sensitivity | 0.2 / 1.4 / 49 / 79 / 97% at 20 / 30 / 40 / 45 / 50%; shifts by at most 3 points with rounding [A] |
| Fixed point | `fixed_sqrt` exact over all 2^31 inputs; no disagreement with a double-precision reference away from the threshold across 20M random points and a 1.33e9-point lattice; same decisions at -O0 to -O3 with sanitizers; no libgcc, FPU or divide instructions [A]. Host test passes [V] |
| Docs | 97 links, 0 broken; 6 of 6 archive files carry a SUPERSEDED banner; effort table sums to 600 [A] |
| Platform | Whole demo takes about 4 s, so 6 minutes is all narration [A] |

## 3. Fix before building the slides

### F-01 A fault that skips all of signature verification is not detected [V]

- Calling the firmware's own `cusum_update` with all three sub-stages at the empty-loop cost gives no alarm: {87, 87, 87} gives MD 10.35 against H 10.84. {60, 60, 60} gives 10.78. The first alarm is near {55, 55, 55}.
- A scratch firmware with all three loops of `stage_signature_verify` removed, 30 boots on QEMU 8.2.2 (non-halting build): median sub-stages 143 / 90 / 81, median MD 9.11, and 1 of 30 boots above H (a 333-cycle `sub_b` spike).
- Removing any one loop or any two does alarm (MD 20.9 to 26.0).
- The 87 comes from `attack_boots.csv`, where an empty `sub_b` takes 62 to 96 cycles.
- Why: the three sub-stages move together, so shrinking all of them is the direction the model treats as normal.
- `STATUS.md:61` says the shipped detector "catches large faults reliably". `STATUS.md:28` (1000/1000) and the Q&A leave the same impression.

**Fix (docs only):** `STATUS.md:61` becomes: "The shipped detector catches the simulated fault (sub-stage B loop removed) reliably. It misses a milder `sub_b` reduction (under roughly 40%) and, by direct test, a fault that removes all three loops of signature verification (median MD 9.1 against H 10.84)." Add it to Section 6 and ISSUE-011, to slide 13, and to the Q&A as a question ("what if the whole check is skipped?"). Label the validation row "boots of the loop-removed build detected".

### F-02 The Python detection table is for 10 consecutive faulted boots [V]

- `scripts/cusum_detector.py:108` sets `N_GLITCH = 10`. Each stream is 10 clean boots followed by 10 faulted ones, resampled from the same 496 boots used to fit the model.
- With the same k and H, one faulted boot at 20% severity is detected 2.3% of the time, three boots 83%, ten boots 100%. At 10% severity: 0.4%, 4.4%, 86%.
- STATUS.md calls it "20-boot windows" (`STATUS.md:140`); `PPT_OUTLINE.md:54` says "strong from 10% and above".

**Fix:** state the stream design and that it is in-sample on slide 9 and in STATUS. Never show the 99.7% at 20% next to the firmware result as if it were per boot.

### F-03 The firmware threshold is set by one clean boot [V]

- Boot 78 (`sub_a` = 934) has MD 8.669. The next largest clean MD is 6.091. H = 1.25 x the largest, so without boot 78 and with the same model H would be 7.6 (a refit gives about 8.2 [A]).
- `STATUS.md:286` (limitation 3) says the one-shot baselines miss glitches "below about 10% severity". The baseline table shows 71.6% and 48.3% at 20%, and the shipped firmware needs about 40%.

**Fix:** quote the three thresholds separately in limitation 3 and add one sentence that H depends on a single boot.

### F-04 Effort figures disagree across documents [V, partly A] (needs your decision)

- `STATUS.md` Section 4 gives 600 hours as "an allocation... not a time log", equal to the guideline figure.
- Commit 4b019e3's message and `archive/PHASE1_COMPLETION.md:8` and `archive/PHASE1_DELIVERABLES.md:383` say about 205 hours. A 2026-07-24 note in the parent `archive/` says about 195 hours [A].
- ISSUE-001 is 25 hours in `archive/PHASE1_TIME_INVESTMENT.md:139` and 20 in STATUS. `KNOWN_ISSUES.md:332` gives 15 minutes for the recollection.
- Git has 5 commits and none between 2026-07-21 and 2026-11-07.
- The archive banners cover only the detection and false-alarm claims, and the panel can open `archive/`.

I cannot tell what the true hours are. **Options:** state the hours as your own estimate from your records and have the mentor confirm; extend the archive banners to say the hour figures are superseded. Do not leave 205 and 600 unexplained next to each other.

### F-05 Stale or over-claiming phrases [V unless marked]

| Where | Problem | Replace with |
|---|---|---|
| `FIRMWARE_DETECTOR.md:4` | Date November 7 | 2026-11-10 |
| `FIRMWARE_DETECTOR.md:9` | "Real-time ... sequential change detection" | "runs once per boot after checkpoint 2; one CUSUM update, so a one-shot threshold on Mahalanobis distance" |
| `FIRMWARE_DETECTOR.md:54` | "Fixed-point is 10x faster" (never measured) | delete, or "no FPU needed" |
| `FIRMWARE_DETECTOR.md:17-23` [A] | box says "PMU Checkpoint" | "Timing checkpoint (SysTick)" |
| `KNOWN_ISSUES.md:294` | "Perfect discrimination" beside AUC 0.9933 | "Near-perfect discrimination (AUC 0.993)" |
| `KNOWN_ISSUES.md:428, 446` | "real-time" | "alarm that halts the boot" |
| `docs/GAUSSIAN_ASSUMPTION_ANALYSIS.md:97` | "50-500 cycle shifts (>> noise)" while sigma is about 60 | "large against the 60-cycle spread" |
| `docs/GAUSSIAN_ASSUMPTION_ANALYSIS.md:92, 228` [A] | "Robust Performance" | "detection of the large simulated fault works despite non-Gaussianity" |
| `review/QA_BACKUP.md` Q4 [A] | "controlled false-alarm rate" | "measured false-alarm rate" |

### F-06 The survey move left stale paths and an untracked file [V]

- `STATUS.md:319` and `../README.md:21` still place the survey one level up, and `review/LITERATURE_SLIDES.md:11` names it without a path. The tag does not contain it.
- Survey lines 769, 770, 878, 1052 and 1055 still carry the pre-implementation claims ("99% detection @ 1% FA", "~8% overhead", "catches all fault types") that your slide notes say to drop.

**Fix:** update the three paths; commit the survey, or leave it out of what you hand in; put a banner on top: "pre-implementation; reference list names wrong". `archive/PROJECT_OVERVIEW.md:324` also has the old link; leave it.

### F-07 The wrong QEMU silently alarms every boot [V]

- This machine has QEMU 6.2.0 at `/usr/bin` and 8.2.2 at `/usr/local/bin`. Your shell finds 8.2.2 first. A tool that resets `PATH` finds 6.2.
- Three boots under 6.2 each printed "Timer with period zero, disabling" then `ALARM_FEATURES,0,0,0`.
- `README.md:256` says older QEMU "lacks the machine or has a UART bug". In fact 6.2 has the machine and alarms on every clean boot.

**Fix:** say that in README. Put `qemu-system-arm --version` (must say 8.2.2) at the top of the demo checklist, and call `/usr/local/bin/qemu-system-arm` by full path when recording.

## 4. Fix before the review (accuracy)

### F-08 The median scatter is understated [V]
`STATUS.md:166` uses 17 cycles (3%) from the Gaussian formula. The clean `sub_b` is flat, and resampling gives 29 cycles (4.9%). P(two medians of 20 differ by 27 or more) = 0.27. The conclusion stands. The six sweep medians fall monotonically (627 to 600; Spearman about -0.94 [A]), so write "no usable dependence", not "none". Fix the same figure at `PPT_OUTLINE.md:77`.

### F-09 Stale numbers in KNOWN_ISSUES.md
- Line 109 says CV 11%; data give 8.8 to 10.4%. [V]
- Line 365 says condition number 27; line 328 and the data say 33.5. [V]
- Lines 348-350 show correlations 0.913 / 0.761 / 0.780; data give 0.902 / 0.886 / 0.908. [V]
- The statistics block lists ISSUE-009 under Medium; its own severity (line 475) is Low. [V]
- ISSUE-003 uses 555 and 63 where data give 582.7 and 60.6, and "+36%" yield is 36 points. [A]
- "185 of 500 boots (37%)" (line 22) has no stored dataset: the first commit's nominal CSV has 4 corrupt boots of 500 [V]; the pre-fix backup has 17 of 499 [A]. Reword it as "an early collection had a large share of corrupt boots", or find the source. Do not quote 37% to the panel.

### F-10 Footprint labels, quantisation and the word "verified"
- `STATUS.md:180` and `FIRMWARE_DETECTOR.md:171` call the 64 bytes of bss "detector state". It is `boot_log` at 0x38000000 [V]; the detector state is a stack object [A]. All sizes are for `-O0 -g`; at `-Os` the detector would be about 396 bytes and the firmware about 1,800 [A].
- The `cov_inv` entries are about 7-bit integers in Q16.16 (109, -61, -50, 135, -82, 170), so MD runs up to 2.5% off exact floating point [A]. The host test's "within 0.0008" compares with float using the same quantised parameters, so it does not show this. Decisions are unaffected (largest clean MD 8.662 against 8.669) [A].
- Say "arithmetic checked against floating point on the host", not "fixed-point verified".

### F-11 Scope table and the Phase 2 change
- Three rows in `STATUS.md` Section 5 are generous. "CUSUM log-likelihood detector, Done with a note" should be Partial (Mahalanobis is not a log-likelihood ratio; the firmware is one-shot). "5-D PMU at 10 checkpoints, Partial" should say no PMU events are used. "Cycle overhead and latency benchmark, Partial" should be Not done (footprint only).
- Proposal items with no row: PMU events (cache misses, branch mispredictions), "optimise detection versus false-alarm tradeoff" (H = 1.25 x max is not an optimisation), "prove the CUSUM mathematics", "highly optimised, deterministic" (the build is -O0), applicability to TI parts. [V against the proposal text]
- `Phase_0_Proposal.txt` never mentions STM32 or DWT; its Phase 2 is "Production Implementation". The hardware port is therefore a scope change, and two approved Phase 2 items are already done. Ask the panel to approve the revised Phase 2.
- The proposal says the PMU is "present on all standard Cortex cores". The reviewers believe the Cortex-M33 has the DWT counters but no architectural PMU (that arrives with Armv8.1-M). **Unverified:** web search was unavailable and `svd/Cortex-M33.svd` has no DWT or PMU block. Check the Cortex-M33 Technical Reference Manual; "PMU/DWT" is safe wording either way.
- Phase 2 at about 400 hours is optimistic; KNOWN_ISSUES estimates for the first five open items alone sum to about 270 hours [A]. Order the plan by risk: board bring-up and variance first, then fault models, latency, the redundancy comparison, and fusion, TrustZone-M and Stein last.

### F-12 "Does Mahalanobis help?" needs a second baseline [V]
Single boot, 1% calibration, held-out half, synthetic `sub_b` cuts of 5 / 10 / 20 / 30%:

| Statistic | 5% | 10% | 20% | 30% |
|---|---|---|---|---|
| Mahalanobis (two-sided) | 2.0 | 5.0 | 68.9 | 99.4 |
| Direction-aware (matched to a `sub_b` drop) | 20.2 | 58.1 | 99.4 | 100 |
| Plain one-sided `sub_b` threshold | 7.6 | 16.3 | 48.6 | 71.5 |

On the 23 recorded false-alarm boots: the direction-aware statistic still alarms on 13 of 23 (high `sub_a` spikes make the model expect a higher `sub_b`); a plain "`sub_b` too low" rule alarms on 0 of 23. By arithmetic (threshold `sub_b` < 459 against an observed 90) that rule would also catch the whole-stage skip of F-01.

- Q&A 7 says "a signed rule would not have alarmed on any of them". That is true only for a rule on `sub_b` alone. Reword it.
- Title slide 12 "Partly", not "Why Mahalanobis?".
- A one-sided `sub_b` rule is worth testing in Phase 2. It needs an implementation change, so leave the frozen firmware alone. (Ad hoc analysis, not in the repo.)

### F-13 Smaller errors

| Where | Problem |
|---|---|
| `PROJECT_GUIDE.md:81` [V] | "not an in-repo test"; the test is `tests/test_firmware_detector.c` |
| `PROJECT_GUIDE.md:113` [V] | "untracked until committed"; the files are tracked |
| `README.md:336-338` [V] | tests listed as "20 boots"; 20 is the default, the reported run is `N=1000` |
| `../CLAUDE.md:51` [V] | `make run` "exits after 0.8s"; it never exits (`main.c:289`, `while (1);`) |
| `../CLAUDE.md:25` [A] | lists a "ROM verification" stage that does not exist in `main.c` |
| `PPT_OUTLINE.md:3-5` [V] | header says 25 min + 6 min demo (31); the section lines add to 23 + 6 (29) |
| `PPT_OUTLINE.md:96` [V] | says `empirical_attack.png` predates the recollected data; it was regenerated in 02fedee |
| `DEMO_SCRIPT.md:51` [V] | narration mentions an "attack cluster"; `model_distributions.png` shows only clean data |
| `DEMO_SCRIPT.md` step 5 [A] | the limits step is 30 s; too short for the points the panel will probe |
| STATUS and Q&A [A] | 0.3% chance of no CP2 spike becomes "about 0.3% (up to about 3% using the training set's own spike rate)"; the Fisher test "shows no difference", it does not "support pooling"; "one or two sub-stages" is not true of boot 932 (all three above +3 sigma); "same 1% calibration" held-out false-alarm rates are 1.4 to 1.7% |

### F-14 One unreproduced observation
The reproducibility reviewer saw `ALARM_FEATURES,0,0,0` once in an isolated control batch on 8.2.2 and 9 alarms in 450 clean boots (2.0%). I saw none in 300 boots and none in the saved false-alarm evidence. All-zero features are exactly what QEMU 6.2 prints, so a wrong binary in that batch is possible [inference]. Do not add it to STATUS until it reproduces. If you ever see it, check the QEMU version first.

## 5. Hygiene before you commit or submit

| ID | Item |
|---|---|
| F-15 [A] | `.git` is about 148 MB because commits fe93578, 051046f and 4b019e3 track a `.venv` (visible in `git show --stat fe93578` [V]) and `svd/STM32U545.svd`. Do not rewrite history after the tag. Hand in `git archive phase1-review-freeze-2` (34 MB) or state the size. |
| F-16 [A] | Setup friction: the pins in `requirements.txt` need Python 3.12 or newer (Ubuntu 22.04's stock 3.10 fails); scripts use relative paths and fail outside `pmu_bootrom/`; the README flow overwrites tracked CSVs, `model.npz`, PNGs and the false-alarm evidence, so tell reproducers to work on a copy or run `git checkout -- data results`. |
| F-17 [A] | Implementation-owned items, best documented and left for Phase 2: `test_firmware_detector.sh` counts a boot as clean once the banner prints, without checking it finished (`BOOT COMPLETE` or `ALARM_FEATURES`); the Makefile has no header dependencies, so plain `make` after a glitch build says "Nothing to be done"; stale source comments (`cusum_detector.c:15` "not yet measured", `cusum_detector.h:133,142` "binary search" and "Error < 0.001", `main.c:220` CP0 "~400-1000 cycles", `collect.sh:15` "0.2 seconds"); the model is calibrated at -O0 only; latency is unmeasured. |
| F-18 [A] | Prose for the panel: define MD, CV, z and "95% interval" on first use; slide 11 carries about 15 numbers (put the false-alarm table on a backup slide); slide 14 merges the scope and effort tables; slide 8 sentences run over 40 words. |

## 6. Expected panel outcome

The red-team reviewer's reading, which I share but cannot verify against the panel's actual standard: **satisfactory with conditions**. The likely condition is hardware evidence that a partial fault moves a counter.

**Strongest evidence:** a working fixed-point detector in the boot flow; a 1000 + 1000 harness; a measured platform finding (SysTick in QEMU does not follow executed work); a limitations section that already names most of what a faculty member would raise.
**Weakest:** nothing shows timing moves under a partial fault, so "1000/1000" means loop absent against loop present.
**What would worry a faculty member most:** the title says "PMU" and the sensitivity claim both rest on hardware you have not touched yet.

Three messages to leave with the panel:
1. An in-boot detector works end to end on a large simulated fault.
2. QEMU timing cannot show partial faults, which is the case for hardware.
3. Scope is mapped honestly against the proposal, with a gated Phase 2.

Cuts for a 30-minute slot: one literature slide instead of two, fold slide 8 into 9, move slide 12 to backup, drop slide 16, shorten the demo to 3 or 4 minutes. Slides missing from the outline: architecture or data-flow figure, threat model, "built versus reused, and AI use", risks.

## 7. Questions to rehearse (not yet in QA_BACKUP.md)

| # | Question | Answer outline (source) |
|---|---|---|
| 1 | What is the threat model? | One large skipped block; timing-preserving and adaptive attackers are out (STATUS Section 6) |
| 2 | A glitch that does not change timing? | One loop iteration is about 0.3% of `sub_b`, far below the 40% needed; out of scope until hardware shows which faults move a counter |
| 3 | A glitch on the alarm branch itself? | Single non-redundant branch (`main.c:241`, the same weakness slide L1 describes); Phase 2 hardening |
| 4 | What does a false alarm cost, and what is the budget? | About 1% is unusable (ISSUE-013); a product budget is far lower; hardware plus a retry policy |
| 5 | Per-chip, temperature and voltage thresholds? | Constants fixed in ROM; drift untested; hardware sweep in Phase 2 |
| 6 | Why Gaussian and Mahalanobis? | Cheap, fits a ROM; one-sided and box baselines are next (F-12) |
| 7 | Is a constant-time stub a fair test? | Loops are constant by design; real verification time is data-dependent; hardware needs such a workload |
| 8 | Why 4 checkpoints, only CP2 monitored? | Design choice; fusion is Phase 2 (ISSUE-009) |
| 9 | Why QEMU rather than a board? | The proposal said emulation; the sweep result is the case for hardware |
| 10 | Is the 496-boot model valid? | Probably excludes spikes (halting firmware), multi-peaked, stationarity unchecked; recollect with a non-halting build |
| 11 | Comparison with existing countermeasures? | Not measured; same campaign on both in Phase 2 |
| 12 | Generalising to TI parts? | Depends on which counters the target exposes; hardware first |
| 13 | What is novel? | Only within the 20 surveyed papers, no systematic search; the contribution is the application and the port |
| 14 | Is it reproducible? | Tag and commands exist; timing follows host time and host load was not recorded |
| 15 | IP, clearance, AI policy? | Confirm TI clearance and the AI-tool policy with your mentor |

Weakest existing answers in `QA_BACKUP.md` [A]: Q4 ("controlled"), Q7 (too long to say aloud; see F-12), Q8 (say "arithmetic only"), Q9 (add the DWT point), Q10 and Q23 ("effort went into the pipeline" is an excuse; give the technical reason that severity cannot be expressed in QEMU), Q14 and Q16 (see F-04), Q15 ("be ready to explain" is not an answer: write what the tool did, what you decided, and what you checked).

## 8. Before you record

1. `qemu-system-arm --version` must print 8.2.2 (F-07).
2. `pkill -f qemu-system-arm`; close other work; wait until `uptime` load is under 1.
3. `make clean && make`, then copy `app.elf` and the attack build to a demo folder, as `DEMO_SCRIPT.md` does. Never run `severity_sweep.sh` or `test_firmware_detector.sh` just before: they rebuild the shared `app.elf` (the validation script leaves the glitched build).
4. Dry-run once from an interactive terminal. About 1 to 2% of clean boots alarm; keep a retake.
5. Do not mention a clean-boot count you have not just seen.

## 9. Decisions for you

1. Effort figures (F-04): your records, mentor confirmation, and the archive banners.
2. Whether to document F-01 only, or also test a one-sided `sub_b` rule in Phase 2 (F-12).
3. Whether the survey goes into a commit, and whether this report goes into the repository you hand in.
4. Whether to ask the panel to approve the revised Phase 2 scope (F-11).

## 10. Limits of this audit

- No GDB or `debug-server` flow, no full 500-boot `make collect`, and no QEMU runs by the code and statistics reviewers.
- The DWT and PMU facts and the paper numbers are unverified.
- Actual time logs, mentor and TI sign-off, and the AI-tool policy are outside the repository.
- The deck does not exist yet, so slide content was judged from `PPT_OUTLINE.md` only.
- Three reviewers' findings (marked [A]) rest on their own runs; the host-load conditions of the recorded validation runs are unknown.
