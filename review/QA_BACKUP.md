# Phase 1 Review: Q&A Backup

Short answers first, evidence second. Numbers come from [STATUS.md](../STATUS.md); do not quote others.

## Results and method

**1. Your simulated fault is huge. Would a plain threshold on sub_b catch it too?**
Yes, and we measured it ([STATUS.md](../STATUS.md#baseline-comparison-one-shot-detectors)): all three one-shot detectors catch the real glitch 100%. In the datasets, clean Mahalanobis distance never exceeds 8.7 (496 boots) and glitched never falls below 19.1 (50 boots); the live validation does show rare clean spikes far above 8.7, see answer 7. The differences appear on synthetic reductions at the same 1% calibration: Mahalanobis is better from about 20% severity (71.6% vs 48.3% at 20%, 99.4% vs 73.3% at 30%), but a `sub_b` threshold is better at 5 to 10% (16.2% vs 5.5% at 10%). So the multivariate model helps for medium faults and not for the weakest. Do not claim the firmware result proves sensitivity to subtle faults.

**2. You call it CUSUM, but the firmware calls it once per boot.**
Correct. In firmware, S starts at 0 and gets one update, so it is a calibrated one-shot threshold on Mahalanobis distance (k = 0). The sequential version runs in the Python simulation over 20-boot windows. Sequential accumulation across checkpoints is Phase 2.

**3. What does your false-alarm rate mean in practice? Halting a boot is costly.**
The measured rate is in STATUS.md. Any non-zero rate means some legitimate boots halt, which is unacceptable for a product. Phase 1 shows the pipeline; the Phase 2 goals are hardware with lower timing noise and a response policy better than halt (retry, then lock out).

**4. Why a Gaussian model when Shapiro-Wilk rejects Gaussianity?**
Measured and documented ([GAUSSIAN_ASSUMPTION_ANALYSIS.md](../docs/GAUSSIAN_ASSUMPTION_ANALYSIS.md)). Thresholds are set empirically from observed distances, not from Gaussian quantiles, so the test still has a controlled false-alarm rate on this data. The non-Gaussianity is attributed to QEMU host jitter; whether hardware removes it is a hypothesis for Phase 2.

**5. Why does the Python threshold differ from the firmware threshold?**
Different problems. Python is sequential over 20-boot windows (k from the 70th percentile of clean MD, H from the 99th percentile of the window maximum). Firmware is one observation, so it uses k = 0 and H = 1.25 x the largest clean MD. Details in [FIRMWARE_DETECTOR.md](../FIRMWARE_DETECTOR.md).

**6. Why was an earlier threshold calibration wrong?**
Using the single-observation 99th percentile as the CUSUM threshold ignores accumulation and gives roughly 13% false alarms over 20-boot windows (ad hoc simulation in [PROJECT_GUIDE.md](../PROJECT_GUIDE.md)). Sequence-level calibration fixes that for the Python detector.

**7. Were the validation false alarms real?**
The final run had 14 false alarms in 1000 clean boots (1.4%); an earlier run with the same firmware and harness had 9 (pooled: 23 / 2000, about 1%). The saved telemetry shows each false alarm is a large one-sided slowdown of a single sub-stage (z-scores +5.2 to +49.6, MD 11.8 to 120.7 against a threshold of 10.84), so they are timing spikes and not borderline calibration cases. The hypothesis is the host pausing the emulator, which SysTick follows; that is not confirmed. The real glitch is the opposite direction (`sub_b` drops), so a signed rule would not have alarmed on any of them, but that is untested. The final run detected all 1000 attacks (100%); an earlier run missed 3 (not investigated). Do not guess beyond this in the room.

**8. How do you know the fixed-point code is correct?**
Manual arithmetic checks and the sqrt bug history (ISSUE-008: the integer square root first returned 0, then truncated the fractional part so distances just above the threshold slipped under it; both fixed and re-validated, see the log history in STATUS.md). No automated unit tests; stated in [CLAUDE.md](../../CLAUDE.md) as a research prototype.

## Scope and proposal

**9. The title says PMU. You only use SysTick.**
Correct. QEMU's Cortex-M33 model does not provide DWT event counters, so SysTick is the cycle counter. DWT/PMU counters (cycle, CPI, LSU, fold) are the Phase 2 STM32L552 work.

**10. The proposal promised 10,000 glitched boots, a QEMU NOP plugin, 5-D vectors at 10 checkpoints, Stein bounds.**
Show the scope table ([STATUS.md](../STATUS.md#5-scope-versus-the-phase-0-proposal)). Delivered: 496 clean boots (500 collection runs), firmware detector, validation at one severity. Deferred: the plugin, large glitched datasets, higher dimension and checkpoint count, formal bounds. Reasons: effort went into the pipeline, the fixed-point port and the debugging it needed. Ask which of these the panel wants prioritised for Phase 2.

**11. Why does the fixed-point port and bootrom integration come before hardware?**
Both were scheduled for Phase 2 in the proposal, and doing them early validated that the detector fits a no-FPU, no-libgcc environment. It did not replace the missing Phase 1 items.

**12. Latency, RAM and flash cost?**
Not measured yet. The numbers in older notes are estimates. Say you will measure them (`arm-none-eabi-size` and SysTick around `cusum_update`).

**13. What fault models can you actually represent?**
One: skipping the sub-stage B loop. No instruction skip, repeat, register or flash-read corruption. Phase 2 uses debugger-based injection and possibly voltage glitching.

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
We built it: `-DGLITCH_SKIP_PCT=<n>` skips n% of the sub-stage B loop and `scripts/severity_sweep.sh` runs each setting. It showed no dependence on the skip percentage: median `sub_b` is 618 cycles clean, 620 at 50% skip, 602 at 90%, 610 at 99%, and 278 only when the loop is removed entirely (N=20 each; table in STATUS.md, raw output in `results/severity_sweep.log`). SysTick in QEMU follows host time, not executed instructions, so `sub_b` is dominated by a roughly fixed cost. The likely explanation (first-time translation of the loop block) is not confirmed. With `-icount` the numbers are exact (78, 39, 1, 0 at 0, 50, 99, 100% skip) but clean boots then have zero variance and the Mahalanobis covariance is singular. The severity curve is therefore Python-only, and DWT counters on hardware are the way to repeat it.

**20. Does that undermine the 1000-boot result?**
It limits what the result means. The full-loop fault changes `sub_b` by far more than any noise, so detection is reliable, but the platform cannot tell us how the detector behaves for faults that remove a fraction of the work. It also supports the statement that most of the QEMU timing noise is host-driven.
