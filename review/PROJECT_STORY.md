# Project Story: Phase by Phase

One page per chapter of how the project went, so you can tell it in order. Results, hours and limitations stay in [STATUS.md](../STATUS.md); this file links there instead of repeating numbers. Every fact has a source (commit, dated line, or file). Anything the files do not show is in "Not documented" at the end.

**The arc in one line:** we promised a statistical detector on PMU telemetry; we built it on an emulator with a timer standing in for the PMU, made it run inside the boot flow, found along the way where the emulator's timing cannot be trusted, and now know exactly what hardware has to prove.

## Tracker

| Chapter | What | Status | Main evidence |
|---|---|---|---|
| 0 | Proposal | Submitted | [Phase_0_Proposal.txt](../Phase_0_Proposal.txt) |
| 1 | Literature and approach | Done | `Literature_Survey/`, [LITERATURE_SLIDES.md](LITERATURE_SLIDES.md) |
| 2 | Bootrom stub and clean data | Done | commit fe93578 (2026-07-21), `src/main.c`, `data/` |
| 3 | Python detector | Done, one weakness open | `scripts/`, ISSUE-002, ISSUE-003 |
| 4 | C port into the boot flow | Done | commit 4b019e3 (2026-11-07), `src/cusum_detector.c` |
| 5 | Validation, audits, corrections | Done, findings open | `results/`, [FINAL_AUDIT_REPORT.md](FINAL_AUDIT_REPORT.md) |
| 6 | Phase 2 | Planned | [STATUS.md](../STATUS.md#7-phase-2-plan) |

---

## Chapter 0: The promise (Phase 0)

- **Goal, in the proposal's words:** model clean BOOTROM execution as a multivariate Gaussian and detect glitches with a CUSUM chart, using the ARM PMU as a sensor array. Phase 1 is "building the statistical model and proving the CUSUM mathematics using emulated ARM execution with scripted fault injection". Phase 2 is the fixed-point, BOOTROM-embedded implementation.
- **Promised for Phase 1:** a fault-injection plugin that substitutes NOPs, 500 clean and 10,000 glitched boots at 5 severity levels, 5-dimensional PMU vectors at 10 checkpoints, a detector tuned for detection versus false alarm, and Stein's Lemma bounds.
- **Promised for Phase 2:** fixed-point C, TrustZone-M lockout, benchmarks, comparison against redundant execution.
- **Note:** the proposal never names a board. The STM32L552 port in the Phase 2 plan is a later decision.

## Chapter 1: Literature and approach

- **Goal:** know what exists and where the gap is.
- **What happened:** 20 papers read and summarised; a survey document and corrected citations. The effort table allocates the largest single block of research time here (see [STATUS.md](../STATUS.md#4-effort)).
- **Surprise:** the survey's reference list had wrong author names and some pre-implementation claims (99% detection at 1% false alarm, about 8% overhead). The slides use corrected names and drop those claims.
- **Lesson:** novelty holds only within the 20 papers surveyed; no systematic search was done.
- **Status:** done. Numbers in the slides still need checking against the PDFs.

## Chapter 2: A boot that can be timed (Phase 1, stage 1)

- **Goal:** a bootrom stub with checkpoints whose timing is repeatable.
- **What happened:** the first commit (2026-07-21) already holds `src/main.c`, the linker script, the data-collection script, six Python scripts, a 500-boot clean dataset and a 50-boot attack dataset. Four stages, each split into sub-stages A, B, C, give a 3-dimensional feature vector per checkpoint.
- **Surprise:** QEMU has no DWT cycle counter (CYCCNT stays 0), so SysTick became the cycle counter. This is why "PMU" in the title is, in Phase 1, a timer.
- **Bug:** SysTick initialisation corrupted a share of the boots (ISSUE-001). It is logged on 2026-11-07 and fixed in 051046f.
- **Lesson (KNOWN_ISSUES):** the order of counter enable and clear matters.
- **Status:** done. The stub is a model of a boot flow with constant-length loops, not a real one.

## Chapter 3: The statistical detector (Phase 1, stage 2)

- **Goal:** fit a Gaussian to clean timing and detect shifts with a CUSUM on Mahalanobis distance.
- **What happened:** `build_model.py` fits the model, `cusum_detector.py` simulates attacks at five severities, and later `baseline_comparison.py` (added 2026-11-10) compares Mahalanobis against plain `sub_b` thresholds.
- **Bugs:** the ROC calculation mixed clean and attack streams (AUC about 0.5; ISSUE-004, fixed in 051046f). Naive threshold calibration false-alarmed far too often over 20-boot windows, so the threshold is calibrated on the window maximum.
- **Surprise:** the clean data are not Gaussian (Shapiro-Wilk rejects), so thresholds are set from observed distances ([GAUSSIAN_ASSUMPTION_ANALYSIS.md](../docs/GAUSSIAN_ASSUMPTION_ANALYSIS.md)).
- **Open weakness:** weak detection of small faults (ISSUE-003). The simulation scores 10 consecutive faulted boots, which is not what the firmware sees (audit F-02).
- **Status:** done, with that caveat.

## Chapter 4: Into the boot flow (Phase 1, stage 3)

- **Goal:** run the detector inside the firmware, with no FPU and no library.
- **What happened:** on 2026-11-07 (commit 4b019e3) the Q16.16 Mahalanobis and CUSUM code, the calibration script and the test script were added. The detector runs after checkpoint 2 and halts the boot on alarm. This was a Phase 2 item in the proposal, pulled forward.
- **Surprise:** the firmware calls the update once per boot, so it is a one-shot threshold, not a sequential chart. The Python and firmware detectors are different operating points ([STATUS.md](../STATUS.md#2-results)).
- **Bugs:** the integer square root truncated and let borderline attacks through (ISSUE-008, fixed twice). On 2026-11-10 a review of extreme inputs found that a large squared distance wrapped to zero and was not flagged (ISSUE-014, a fail-open flaw), fixed by clamping and saturating. The glitch model also changed over time: the first commit breaks out of the loop at iteration 100, the frozen firmware removes the loop.
- **Status:** done.

## Chapter 5: Validation, audits and corrections (2026-11-09 to 2026-11-10)

- **Goal:** measure the detector honestly and freeze Phase 1.
- **What happened:** a 1000 + 1000 boot validation; a partial-severity sweep; false-alarm telemetry saved and analysed; documents consolidated into STATUS.md; freeze tags `phase1-review-freeze` (0d6aa44) and `phase1-review-freeze-2` (02fedee).
- **Surprises, in the order they appeared:**
  1. About 1% of clean boots false-alarm, as single-sided timing spikes (ISSUE-013).
  2. The sweep showed QEMU's timer does not follow executed work, so partial loop skips are invisible (ISSUE-012). This became the main platform finding.
  3. The shipped threshold needs roughly a 40 to 50% reduction in `sub_b` before it alarms.
  4. The final audit ([FINAL_AUDIT_REPORT.md](FINAL_AUDIT_REPORT.md)): a fault that skips all of signature verification is not detected, and the firmware threshold is set by one clean boot.
- **Lesson:** the large simulated fault is easy; what the detector does for realistic faults is what hardware has to answer.
- **Status:** done; the audit's fixes are listed there.

## Chapter 6: Phase 2 (planned)

- **Plan:** STM32L552 with DWT counters, debugger-based fault injection, several fault models, multi-checkpoint fusion, redundant-execution comparison, TrustZone-M lockout ([STATUS.md](../STATUS.md#7-phase-2-plan)).
- **Suggested order by risk** (audit suggestion, not a commitment): board bring-up and timing variance first; then fault models and a detection curve against the number of skipped instructions; then latency; then the redundancy comparison; fusion, TrustZone-M and formal bounds last.
- **Suggested gate for the next review:** the same stub running on the board with DWT, a non-halting 1000-boot clean run (spike rate, spread, normality), and a detection curve for at least three fault types.
- **Carry-over items:** collect training data with a non-halting build, measure the latency of `cusum_update`, test a one-sided `sub_b` rule.

---

## Not documented (do not state these as fact)

- Dates or hours of the literature work (only file modification times exist).
- Proposal approval date, review date, mentor meetings.
- Any time log. The hours in STATUS.md are an allocation; older documents in `archive/` give other totals (see audit F-04).
- When the first data collection really happened: KNOWN_ISSUES says 2026-11-07, but corrupt boots already appear in the 2026-07-21 commit.
- The origin of the "185 of 500 boots (37% corrupt)" figure in ISSUE-001; no stored dataset reproduces it.
- Why there are no commits between 2026-07-21 and 2026-11-07, and what the parent `archive/backup/` folder is a snapshot of.
- Why the first commit carries an STM32U545 SVD file when the plan names the STM32L552.
