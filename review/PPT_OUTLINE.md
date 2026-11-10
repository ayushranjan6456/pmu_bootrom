# Phase 1 Review: PPT Outline

16 slides, about 25 minutes of talking plus a 6-minute demo, which fits the 30 to 45 minute slot with Q&A. Every number comes from [STATUS.md](../STATUS.md); do not type numbers into slides from memory, and re-check them against STATUS.md before building the deck.

Time budget: slides 1 to 5 about 6 min, slides 6 to 11 about 9 min, slides 12 to 16 about 8 min, demo 6 min, Q&A the remainder.

Deliverables for the review: this deck, a live or recorded demo (see the recording plan at the end), the repository at the freeze tag, and [STATUS.md](../STATUS.md) as the written summary.

---

## 1. Title
- PMU-Based Statistical Detection of Fault Injection Attacks in Secure Boot
- Ayush Ranjan (EE24M504), M.Tech, IIT Madras. Mentor organisation: Texas Instruments
- Phase 1 review

## 2. Problem
- The BOOTROM is the root of trust; a voltage or clock glitch can make it skip a signature check.
- Existing defences: hardware sensors, redundant execution (area, power, latency cost).
- Question: can a software-only statistical detector, using timing telemetry already available on-chip, flag a glitch while the bootrom is still running?

## 3. Literature 1: the boot ROM is a real target
- Source: slide L1 in [LITERATURE_SLIDES.md](LITERATURE_SLIDES.md). Real attacks on deployed devices (console boot ROM, automotive secure boot, industrial bootloaders, million-glitch campaigns).
- Our Phase 1 stub has a single, non-redundant signature check, so it has the same weakness.

## 4. Literature 2: defences and the gap
- Source: slides L2 and L3. Hardware sensors, software redundancy, algorithm-level checks, with their limits. About 60 hours of the effort went into the survey (20 papers), so state what was read.
- Gap, within the surveyed papers only: statistical detection from on-chip timing telemetry inside the boot ROM, small enough for a ROM. A systematic prior-art search is not done.
- Novel versus reused: Mahalanobis distance and CUSUM are standard; the application and the embedded port are the contribution.
- Do not put our detection rates next to the papers' numbers; the platforms and faults differ.

## 5. Approach and journey
- Clean boots have repeatable timing; a glitch changes the timing of the stage it hits. Model clean timing as a multivariate Gaussian, score a boot by Mahalanobis distance (MD), decide with a threshold.
- Diagram: boot stage, 3-D feature [sub_a, sub_b, sub_c], MD, CUSUM, alarm or continue.
- Journey in four steps: ideation and literature; a basic bootrom stub with timing checkpoints in QEMU; the Python statistical detector (model fit, synthetic attacks); the C port into the firmware (fixed point, halts the boot). Each step is where the main bugs were found (SysTick init, ROC calculation, square root, overflow).

## 6. Phase 1 setup
- Cortex-M33 bootrom stub in QEMU (`mps2-an505`), SysTick as cycle counter.
- 4 checkpoints: boot start, memory init, signature verify (monitored), key derivation. Each stage is split into sub-stages A, B, C.
- Fault simulation: a compile-time macro removes the signature-verification loop (sub-stage B). It models a skipped check, not an electrical glitch.
- Be upfront: SysTick stands in for the PMU/DWT counters, which arrive on hardware in Phase 2.

## 7. Statistical model
- 500 collection runs, 496 boots recorded; the 2.5 x IQR outlier filter removed none. The four missing boots are probably runs where the halting firmware alarmed, so the training set probably excludes timing spikes (STATUS.md, Section 3; consistent with the data, not proven).
- Measured QEMU noise: CV about 9 to 10%. Shapiro-Wilk rejects Gaussianity ([GAUSSIAN_ASSUMPTION_ANALYSIS.md](../docs/GAUSSIAN_ASSUMPTION_ANALYSIS.md)); the distributions are flat and multi-peaked.
- Consequence: thresholds are set empirically from observed data, not from Gaussian quantiles.
- Figure: `results/model_distributions.png`.

## 8. Detector design and calibration (Python)
- Sequential CUSUM over 20-boot windows; k = 70th percentile of clean MD; H from the 99th percentile of the window maximum.
- Why naive calibration fails: using the single-observation 99th percentile as H gives about 13% false alarms over 20-boot windows (a quick resampling simulation, see [PROJECT_GUIDE.md](../PROJECT_GUIDE.md)).
- Figure: `results/threshold_calibration.png`.

## 9. Results: detection versus severity (Python simulation)
- Table from [STATUS.md](../STATUS.md#python-simulation-synthetic-attacks): weak at 5%, strong from 10% and above at the sequential operating point (k = 1.685, H = 10.14). Noise is the limit at 5% (signal 28 cycles against noise 63).
- Say in one sentence that this is a different operating point from the shipped firmware (next slides): the firmware threshold is higher and needs a much larger fault.
- Figure: `results/cusum_results.png`.

## 10. Firmware detector
- Fixed-point Q16.16, division-free integer square root, no FPU. Footprint measured: detector 1,060 bytes, whole firmware 3,152 bytes, 64 bytes of bss. Design: [FIRMWARE_DETECTOR.md](../FIRMWARE_DETECTOR.md).
- Runs after checkpoint 2, halts the boot on alarm.
- State clearly: called once per boot, so it is a calibrated one-shot threshold on MD (k = 0, H = 1.25 x largest clean MD). Sequential accumulation is Phase 2.
- Bugs found and fixed: SysTick init (ISSUE-001), ROC mixing (ISSUE-004), sqrt truncation found twice (ISSUE-008), and a fail-open overflow in the squared distance (ISSUE-014): a huge timing value wrapped to zero and was not flagged. Present the overflow as a real security flaw found and fixed, verified by host test in `tests/test_firmware_detector.c`.

## 11. Results: firmware validation
- 1000 clean and 1000 glitched boots (final run, 2026-11-10): false alarms 14 / 1000 (1.4%), detected 1000 / 1000. Pooled with the earlier run at the same threshold: 23 / 2000, about 1% (Wilson 95%: 0.77% to 1.72%). Source: [STATUS.md](../STATUS.md#2-results).
- Honest framing: the simulated fault is large (clean MD at most 8.7, glitched 19.1 to 31.9), so separation is wide. The run shows the pipeline works end to end, not that subtle faults are caught.
- Do not show a trend across earlier runs; only the final run is comparable. The earlier 9 / 1000 run was built before the overflow fix and with a weaker glitch (3 misses, probably that glitch; not proven).
- False alarms: each of the 23 is a large one-sided slowdown of one or two sub-stages (z up to +68.9, MD 11.8 to 171.5 against H = 10.84), probably host pauses of the emulator (unconfirmed). The real glitch is the opposite direction. Show the table in [STATUS.md](../STATUS.md#false-alarms-in-the-1000-boot-validation).
- Say: the shipped threshold catches large faults and misses mild ones. Offline, with the firmware arithmetic, detection is about 1% at a 30% `sub_b` reduction, about half at 40%, and about 97% at 50% ([STATUS.md](../STATUS.md#sensitivity-of-the-shipped-firmware-threshold)).

## 12. Why Mahalanobis? Baseline comparison
- Table from [STATUS.md](../STATUS.md#baseline-comparison-one-shot-detectors): Mahalanobis against `sub_b` thresholds, all at a 1% calibration (threshold 4.88 for Mahalanobis, not the firmware's 10.84).
- State exactly: every detector catches the real (large) glitch; Mahalanobis wins from about 20% severity (71.6% vs 48.3%); a plain `sub_b` threshold wins at 5 to 10%. The result is mixed; do not claim Mahalanobis is better everywhere.

## 13. Limitations
- One macro-based fault at one severity in firmware; no skip, repeat or register-corruption faults.
- QEMU SysTick follows host time, not executed instructions: skipping 99% of the sub-stage B loop changes the median `sub_b` by about 4%, which is within the scatter of 20-boot medians, while skipping all of it reduces it by about 84% (against the clean mean). So there is no firmware severity sweep. Show the table from [STATUS.md](../STATUS.md#firmware-partial-severity-sweep-not-possible-with-qemu-timing) as a finding about the platform and as the motivation for DWT counters.
- One monitored checkpoint; QEMU noise; mild faults missed; SysTick not PMU; about 1% false alarms from timing spikes; the Python results are sequential while the firmware is one-shot.
- Link: [STATUS.md](../STATUS.md#6-limitations).

## 14. Scope versus the Phase 0 proposal and effort
- Reuse the table from [STATUS.md](../STATUS.md#5-scope-versus-the-phase-0-proposal): done, partial, not done. Pulled forward: fixed-point port, bootrom integration. Deferred: NOP plugin, 10,000 glitched boots, 5-D at 10 checkpoints, Stein bounds.
- 600 hours by category, from [STATUS.md](../STATUS.md#4-effort); an allocation across the work done, with Claude Code assisting development.

## 15. Phase 2 plan
- STM32L552, DWT counters (executed work, which should also remove the host-pause spikes; to be measured), debugger-based fault injection, multi-checkpoint fusion, redundant-execution comparison, TrustZone-M lockout; about 400 hours.
- Open items to carry over: collect training data with a non-halting build, save missed attacks in the harness, latency measurement.

## 16. Ask of the panel
- Priority between breadth of fault models and formal bounds.
- Guidance on the false-alarm budget for a bootrom (a 1% rate would be unusable in a product; Phase 2 targets hardware timing).

---

## Figures to use (all in `results/`)
`model_distributions.png`, `threshold_calibration.png`, `cusum_results.png`, `empirical_attack.png`, `cycle_stability.png`. Regenerate them from the final data first; `empirical_attack.png` predates the recollected attack data.

## Recording plan
- Record the demo ([DEMO_SCRIPT.md](DEMO_SCRIPT.md)) as a fallback and have retakes ready: about 1% of clean boots false-alarm, and one did in a dry run.
- Do not build immediately before recording; let the machine settle, and close other work.
- Deliverables to hand in: slides, the recording, the repository and STATUS.md.
