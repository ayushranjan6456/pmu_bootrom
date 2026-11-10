# Phase 1 Review: PPT Outline

14 slides, about 20 minutes plus Q&A. Numbers marked `{{...}}` are filled from [STATUS.md](../STATUS.md) Section 2 after the final 1000-boot validation. Do not type numbers into slides from memory.

---

## 1. Title
- PMU-Based Statistical Detection of Fault Injection Attacks in Secure Boot
- Ayush Ranjan (EE24M504), M.Tech, IIT Madras. Mentor organisation: Texas Instruments
- Phase 1 review

## 2. Problem
- The BOOTROM is the root of trust; a voltage or clock glitch can make it skip a signature check.
- Existing defences: hardware sensors, redundant execution (area, power, latency cost).
- Question: can a software-only statistical detector, using timing telemetry already available on-chip, flag a glitch while the bootrom is still running?

## 3. Literature and gap
- 20 papers surveyed ([COMPREHENSIVE_LITERATURE_SURVEY.md](../../COMPREHENSIVE_LITERATURE_SURVEY.md)).
- Gap to state: statistical, sequential detection from performance counters inside the bootrom, with a fixed-point implementation that fits a ROM.
- One sentence on what is novel versus what is reused (CUSUM and Mahalanobis distance are standard; the application and the embedded port are the contribution).

## 4. Approach
- Clean boots have repeatable timing. A glitch changes the timing of the stage it hits.
- Model clean timing as a multivariate Gaussian; score a boot by Mahalanobis distance (MD); decide with a CUSUM threshold.
- Diagram: boot stage, then 3-D feature [sub_a, sub_b, sub_c], then MD, then CUSUM, then alarm or continue.

## 5. Phase 1 setup
- Cortex-M33 bootrom stub in QEMU (`mps2-an505`), SysTick as cycle counter.
- 4 stages / checkpoints: UART init, memory init, signature verify (primary target), key derivation. Each stage split into sub-stages A, B, C.
- Fault simulation: a compile-time macro skips the signature-verification loop (sub-stage B).
- Be upfront: SysTick stands in for the PMU/DWT counters, which arrive on hardware in Phase 2.

## 6. Statistical model
- 500 collection runs, 496 boots recorded; the 2.5 x IQR outlier filter removed none.
- Measured QEMU noise: CV about 9 to 11%. Shapiro-Wilk rejects Gaussianity ([GAUSSIAN_ASSUMPTION_ANALYSIS.md](../docs/GAUSSIAN_ASSUMPTION_ANALYSIS.md)).
- Consequence: thresholds are set empirically from observed data, not from Gaussian quantiles.
- Figure: `results/model_distributions.png`.

## 7. Detector design and calibration (Python)
- Sequential CUSUM over 20-boot windows; k = 70th percentile of clean MD; H from the 99th percentile of the window maximum.
- Why naive calibration fails: using the single-observation 99th percentile as H gives about 13% false alarms over 20-boot windows (ad hoc simulation, see [PROJECT_GUIDE.md](../PROJECT_GUIDE.md)).
- Figure: `results/threshold_calibration.png`.

## 8. Results: detection versus severity (Python simulation)
- Table from [STATUS.md](../STATUS.md#2-results): 5%, 10%, 20% severity.
- Message: strong above about 15% severity, weak below 10%. Noise is the limit (signal 28 cycles vs noise 63 at 5%).
- Figure: `results/cusum_results.png`.

## 9. Firmware detector
- Fixed-point Q16.16, integer square root, no FPU, no 64-bit division. Design: [FIRMWARE_DETECTOR.md](../FIRMWARE_DETECTOR.md).
- Runs after checkpoint 2, halts boot on alarm.
- State clearly: called once per boot, so it is a calibrated one-shot threshold on MD (k = 0, H = 1.25 x largest clean MD). Sequential accumulation is Phase 2.
- Bugs found and fixed on the way: SysTick init (ISSUE-001), ROC mixing (ISSUE-004), sqrt truncation, found twice (ISSUE-008). Shows engineering rigour.

## 10. Results: firmware validation
- 1000 clean boots, 1000 glitched boots (final run, 2026-11-10): false alarms 14 / 1000 (1.4%), detected 1000 / 1000 (100%), missed 0. Source: [STATUS.md](../STATUS.md#2-results).
- Pooled false-alarm rate across two comparable runs (same firmware, same harness): 23 / 2000, about 1% (Wilson 95%: 0.77% to 1.72%).
- In the datasets, clean MD never exceeds 8.7 (496 boots) and glitched MD never falls below 19.1 (50 boots). Live clean boots do show rare spikes far above that (next bullet).
- Honest framing: the simulated fault is large, so separation is wide. The numbers show the pipeline works end to end, not that subtle faults are caught.
- Do not present a trend across earlier runs: they used earlier firmware and earlier versions of the test harness, so only the final run is comparable.
- False alarms: each of the 23 (14 + 9 from two runs) is a large one-sided slowdown of a single sub-stage (z-scores +5.2 to +49.6; MD 11.8 to 120.7 against H = 10.84), probably host pauses of the emulator (unconfirmed). The real glitch is the opposite direction. Show the table in [STATUS.md](../STATUS.md#false-alarms-in-the-1000-boot-validation).

## 10b. Why Mahalanobis? Baseline comparison
- Table from [STATUS.md](../STATUS.md#baseline-comparison-one-shot-detectors): Mahalanobis against `sub_b` thresholds at the same 1% calibration.
- Message to state exactly: every detector catches the real (large) glitch; Mahalanobis wins from about 20% severity (71.6% vs 48.3%); a plain `sub_b` threshold wins at 5 to 10% severity. Do not claim Mahalanobis is better everywhere.

## 11. Limitations
- One macro-based fault at one severity in firmware; no skip, repeat or register-corruption faults.
- QEMU SysTick follows host time, not executed instructions: skipping 99% of the sub-stage B loop changes `sub_b` by under 15%, while skipping all of it halves it. So there is no firmware severity sweep; the severity curve is Python-only. Show the iterations-versus-median table from [STATUS.md](../STATUS.md#firmware-partial-severity-sweep-not-possible-with-qemu-timing). Present it as a finding about the platform, and as the motivation for DWT counters on hardware.
- One monitored checkpoint; QEMU noise; weak at low severity; SysTick not PMU; false alarms from timing spikes (9 / 1000); 3 uninvestigated misses.
- Link: [STATUS.md](../STATUS.md#6-limitations).

## 12. Scope versus the Phase 0 proposal
- Reuse the table from [STATUS.md](../STATUS.md#5-scope-versus-the-phase-0-proposal): done, partial, not done.
- Say which items were pulled forward (fixed-point port, bootrom integration) and which are deferred (NOP plugin, 10,000 glitched boots, 5-D at 10 checkpoints, Stein bounds).

## 13. Effort
- 600 hours by category, from [STATUS.md](../STATUS.md#4-effort). Mention it is an allocation across the work done and that Claude Code assisted development.

## 14. Phase 2 plan and ask
- STM32L552, DWT counters, debugger-based fault injection, multi-checkpoint fusion, redundant-execution comparison, TrustZone-M lockout; about 400 hours.
- Ask the panel: priority between breadth of fault models and formal bounds; guidance on the false-alarm budget for a bootrom.

---

## Figures to use (all in `results/`)
`model_distributions.png`, `threshold_calibration.png`, `cusum_results.png`, `empirical_attack.png`, `cycle_stability.png`.

## Before building the deck
- Wait for the final `validation_1000.log`, then fill the `{{...}}` markers and update STATUS.md.
- Regenerate the figures from the final data so slide numbers match.
