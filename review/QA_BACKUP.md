# Phase 1 Review: Q&A Backup

Short answers first, evidence second. Numbers come from [STATUS.md](../STATUS.md); do not quote others.

## Results and method

**1. Your simulated faults are huge (80-90% reductions). Is a statistical detector even needed?**
You're right that a simple floor threshold catches them. That's why the shipped firmware uses one: check if any sub-stage < 0.45× its clean median, halt if so. 140 bytes, integer compares, 0% false alarms on 300 clean boots, 298-300 of 300 detected on five skip-loop faults. The Mahalanobis rule (1060 bytes, Q16.16 fixed-point) has 5.7% false alarms because timing spikes in the clean data make it two-sided, so it only warns at CP3. The floor is one-sided (downward only) and robust. The detector design is tiered: fail-stop for high-confidence (floor), warning for lower-confidence (Mahalanobis). See [FIRMWARE_DETECTOR.md](../FIRMWARE_DETECTOR.md) and [docs/MAHALANOBIS_ANALYSIS.md](../docs/MAHALANOBIS_ANALYSIS.md).

**2. You call it CUSUM, but the firmware calls it once per boot.**
Correct. The Mahalanobis detector in firmware (CP3 only) does S starts at 0 and gets one update, so it is a calibrated one-shot threshold on Mahalanobis distance (k = 0, H = 1.25× max clean MD). The primary detector is the floor rule, which runs at every checkpoint CP1-CP7. Sequential CUSUM and multi-checkpoint fusion are Phase 2.

**3. What does your false-alarm rate mean in practice? Halting a boot is costly.**
The floor rule: 0 of 300 clean boots halted (95% CI 0 to 1.3%). The Mahalanobis rule: 17 of 300 clean boots warned (5.7%, CI 3.6 to 8.9%), mostly timing spikes, so it does not halt. This is why we use a tiered response: the floor is fail-stop with high confidence, Mahalanobis warns with lower confidence. Real hardware should have lower timing noise (DWT counters measure executed work, not wall time), and Phase 2 will add retry-then-lockout policy.

**4. Why a Gaussian model when Shapiro-Wilk rejects Gaussianity?**
Measured and documented ([GAUSSIAN_ASSUMPTION_ANALYSIS.md](../docs/GAUSSIAN_ASSUMPTION_ANALYSIS.md)). Thresholds are set empirically from observed distances, not from Gaussian quantiles, so the test still has a measured false-alarm rate on this data. The non-Gaussianity is attributed to QEMU host jitter; whether hardware removes it is a hypothesis for Phase 2.

**5. Why two detectors, and why does Mahalanobis only warn?**
Mahalanobis failed when applied across all checkpoints: about 14% of clean boots have timing spikes (some sub-stage >1.5× median), and the two-sided score treats spikes like faults. The max-based threshold (H = 1.25× largest clean MD) is set by the most extreme training boot. At CP3 it false-alarms on 5.7% of clean boots — too high to halt. The floor rule is one-sided (downward only), so spikes don't trigger it, and it has 0% false alarms. We run both: floor halts with high confidence, Mahalanobis warns with lower confidence. FT-5 (extra loop, timing goes up) is only caught by the warning. Details in [FIRMWARE_DETECTOR.md](../FIRMWARE_DETECTOR.md) and [docs/MAHALANOBIS_ANALYSIS.md](../docs/MAHALANOBIS_ANALYSIS.md).

**6. Why was an earlier threshold calibration wrong?**
Using the single-observation 99th percentile as the CUSUM threshold ignores accumulation and gives roughly 13% false alarms over 20-boot windows (ad hoc simulation in [PROJECT_GUIDE.md](../PROJECT_GUIDE.md)). Sequence-level calibration fixes that for the Python detector.

**7. Why does Mahalanobis work on the frozen 4-checkpoint firmware but fail on the 8-checkpoint firmware?**
The frozen firmware's training set (496 boots, halting-build collection) had 0 CP2 spikes above 1.5× median (earlier data had 5). The 8-checkpoint training set (300 boots, non-halting) has 24 boots with spikes somewhere at CP1-CP7, 4 at CP3. Those spikes set the max-based threshold high (H = 1.25× max clean MD is two-sided), and about 14% of future clean boots trigger it. At CP3 only, the rate is 5.7% (17 of 300 validation boots), which matches the frozen 1.4% roughly — the frozen result was likely a selection effect (halting build dropped spiked boots), not proven. The current detector uses Mahalanobis at CP3 only with a warning, not a halt. Full analysis in [docs/MAHALANOBIS_ANALYSIS.md](../docs/MAHALANOBIS_ANALYSIS.md).

**8. How do you know the fixed-point code is correct?**
Host test in `tests/test_firmware_detector.c` verifies the firmware's own C code: the square root stays within 1 LSB over 2 million values, the distance stays within 0.0008 of floating point on 3 million random inputs (except where the true distance exceeds 180 and the fixed-point value saturates at 181.02 by design), and extreme inputs alarm. The sqrt history (ISSUE-008) and the overflow flaw (ISSUE-014: a squared distance of 32768 or more wrapped and read as zero, so a huge timing value would not alarm; fixed by clamping and saturating) show why the tests matter. There are no automated unit tests for the bootrom integration; the project is a research prototype.

## Scope and proposal

**9. The title says PMU. You only use SysTick.**
Correct. QEMU's Cortex-M33 model does not provide DWT event counters, so SysTick is the cycle counter. DWT/PMU counters (cycle, CPI, LSU, fold) are the Phase 2 STM32L552 work.

**10. The proposal promised 10,000 glitched boots, a QEMU NOP plugin, 5-D vectors at 10 checkpoints, Stein bounds.**
Show the scope table ([STATUS.md](../STATUS.md#5-scope-versus-the-phase-0-proposal)). Delivered: 496 clean boots (500 collection runs), firmware detector, validation at one severity. Deferred: the plugin, large glitched datasets, higher dimension and checkpoint count, formal bounds. Reasons: effort went into the pipeline, the fixed-point port and the debugging it needed. Ask which of these the panel wants prioritised for Phase 2.

**11. Why does the fixed-point port and bootrom integration come before hardware?**
Both were scheduled for Phase 2 in the proposal, and doing them early validated that the detector fits a no-FPU, no-libgcc environment. It did not replace the missing Phase 1 items.

**12. Latency, RAM and flash cost?**
Footprint measured at `-O0`: floor detector 140 B text, Mahalanobis 1060 B text, whole firmware 4692 B text. RAM negligible (boot_log array, detector state). Latency not yet measured; will time with SysTick in Phase 2.

**13. What fault models can you actually represent?**
Six: five skipped loops (one sub-stage removed, 80-90% reduction) at CP1, CP3 (three variants) and CP7, plus one extra loop (CP3 sub_c +84%). See [FAULT_MODELS.md](../FAULT_MODELS.md). No instruction skip, repeat, register corruption or voltage glitch. Phase 2 adds debugger-based injection and hardware fault injection.

## Effort and process

**14. How is the 600 hours distributed?**
Table in [STATUS.md](../STATUS.md#4-effort). It is an allocation across the work visible in the repository, not a time log. Research and learning 22.5%, statistical pipeline 20%, firmware detector 14%, debugging 10%.

**15. What did AI tooling do?**
Claude Code assisted with implementation, debugging and documentation; stated in the README and STATUS.md. Be ready to explain any part of the code or statistics yourself.

**16. Why are there so few commits?**
Be honest about it; the history in the repository does not reflect the full effort. Offer the issue log ([KNOWN_ISSUES.md](../KNOWN_ISSUES.md)) as the record of the work.

## Phase 2

**17. What is the single biggest risk in Phase 2?**
That hardware timing is not clean enough, or that real glitches do not show up as cycle-count shifts at the chosen checkpoints. Mitigation: start with debugger-based injection, measure the hardware CV first, and fuse several checkpoints.

**18. How will you compare with redundant execution?**
Same fault campaign on both, comparing detection rate, cycle overhead and code size. Proposed in Phase 0; not started.

## Platform findings

**19. Why is there no severity sweep on the firmware?**
We built it: `-DGLITCH_SKIP_PCT=<n>` skips n% of the sub-stage B loop and `scripts/severity_sweep.sh` runs each setting. It showed no dependence on the skip percentage: median `sub_b` is 600 to 627 cycles from 0% to 99% skip (627 at 0%, 600 at 99%) and drops to 93 when the loop is removed entirely (about 84% reduction against the clean mean; N=20 each; table in STATUS.md, raw output in `results/severity_sweep.log`, 2026-11-10T13:15). The 4% spread across 0 to 99% skip is about the scatter of a 20-boot median (roughly 17 cycles at this noise level), so it is not a trend. SysTick in QEMU follows host time, not executed instructions, so `sub_b` is dominated by a roughly fixed cost. The likely explanation (first-time translation of the loop block) is not confirmed. With `-icount` the numbers are exact (78, 39, 1, 0 at 0, 50, 99, 100% skip) but clean boots then have zero variance and the Mahalanobis covariance is singular. The severity curve is therefore Python-only, and DWT counters on hardware are the way to repeat it.

**20. Does that undermine the 1000-boot result?**
It limits what the result means. The full-loop fault changes `sub_b` by far more than any noise, so detection is reliable, but the platform cannot tell us how the detector behaves for faults that remove a fraction of the work. It also supports the statement that most of the QEMU timing noise is host-driven.

## Method questions

**21. What does Mahalanobis buy you over a plain `sub_b` threshold?**
Measured, with a mixed result ([STATUS.md](../STATUS.md#baseline-comparison-one-shot-detectors)). At the same 1% calibration both catch the real glitch 100%. Mahalanobis is better from about 20% severity (71.6% vs 48.3%) because the three sub-stages are correlated (about 0.9), so a change in one stands out against the other two; a `sub_b` threshold is better at 5 to 10%. Say that the shipped firmware threshold is higher still, so for milder faults neither result carries over.

**22. One-shot against sequential: which one is the real detector?**
The firmware is one-shot: S starts at 0 and gets one update with k = 0, so it is a threshold on Mahalanobis distance (H = 1.25 x the largest clean MD). The Python simulation is sequential over 20-boot windows (k = 1.685, H = 10.14). Their false-alarm and detection numbers answer different questions and should not be merged. Sequential accumulation across checkpoints is Phase 2.

**23. Why 1,000 glitched boots and not the 10,000 you proposed?**
Scope and time: effort went into the pipeline, the fixed-point port and the debugging it needed. Also, 10,000 boots of one deterministic fault would add little information: the full-loop fault is far from the clean cloud (MD 19 to 32 against at most 8.7), and 1000 of 1000 detected already puts the detection rate at 99.7% or better (one-sided 95% bound) for this fault. More boots only help with a range of fault severities and fault types, which QEMU cannot produce (question 19). The 10,000-boot campaign belongs on hardware.

**24. Stein's Lemma: where are your formal bounds?**
Not done in Phase 1; the threshold is calibrated empirically. Stein's Lemma needs a model of the clean and the attacked distribution, and the clean distribution here is not Gaussian and not stable under host timing spikes, so a bound computed now would not be trustworthy. The plan is to revisit it with hardware data, where the timing noise should be lower (hypothesis).

**25. "A 1% false-alarm rate is unusable in a bootrom."**
Agree. Present it as a Phase 1 result on an emulator whose timing follows host time, not as a product figure. The false alarms are timing spikes (question 7), the training data probably excludes them, and hardware counters measure executed work so they should not appear there (to be measured). A product would also need a response better than halting, such as retry then lock out, which is Phase 2 work.
