# Phase 1 Complete - Summary

**Date:** 2026-11-12  
**Tag:** `phase1-complete` (commit ec11b5b)  
**Student:** Ayush Ranjan (EE24M504), M.Tech IIT Madras

---

## Deliverables

### 1. Firmware Implementation ✅
- **8-checkpoint bootrom** (CP0-CP7, 3 sub-stages each, 24 features)
- **Two-detector design:**
  - Floor detector: 140 B, halts if sub-stage < 0.45× clean median
  - Mahalanobis detector: 1060 B Q16.16, warns at CP3 only
- **Six fault types:** 5 skipped loops + 1 extra loop
- **Timer guard:** Validates SysTick consistency, fail-open if invalid

### 2. Validation Results ✅

**Fresh boots (N=300 per variant, non-halting build):**
- Floor: 0 / 300 false alarms, 298-300 / 300 detection on skipped loops
- Mahalanobis: 17 / 300 warnings (5.7%), 300 / 300 on CP3 faults
- Python mirror: 100% agreement with firmware (2100 / 2100 boots)

**Real halting build (N=300 per variant):**
- Clean: 0 halted, 293 completed, 7 completed with warning
- Attack + FT-1,2,4: 300 / 300 halted
- FT-3: 299 / 300 halted (1 escape)
- FT-5: 0 halted (caught by warning only, as designed)

### 3. Data Collection ✅
- Calibration: 300 clean boots
- Validation: 7 variants × 300 boots = 2100 boots
- Halting test: 7 variants × 300 boots = 2100 boots
- All with provenance metadata (git hash, load, timestamps)

### 4. Analysis ✅
- **Held-out evaluation:** 4 data splits with Wilson 95% confidence intervals
- **Why Mahalanobis failed:** Timing spikes in training data destroy sensitivity across all checkpoints (14% of boots), works only at CP3 with 5.7% FA
- **Floor detector validation:** 0% FA held-out, catches 55%+ reductions reliably
- **Comparison:** Mahalanobis vs floor, sensitivity curves, synthetic severity sweep

### 5. Documentation ✅

**Core:**
- [STATUS.md](STATUS.md): Complete results, effort, scope, limitations
- [FIRMWARE_DETECTOR.md](FIRMWARE_DETECTOR.md): Two-detector design rationale
- [FAULT_MODELS.md](FAULT_MODELS.md): Six fault types with measured effects
- [KNOWN_ISSUES.md](KNOWN_ISSUES.md): ISSUE-012 to ISSUE-019

**Analysis:**
- [docs/MAHALANOBIS_ANALYSIS.md](docs/MAHALANOBIS_ANALYSIS.md): When it worked, why it failed, floor alternative
- [docs/GAUSSIAN_ASSUMPTION_ANALYSIS.md](docs/GAUSSIAN_ASSUMPTION_ANALYSIS.md): Shapiro-Wilk rejection analysis

**Review preparation:**
- [review/QA_BACKUP.md](review/QA_BACKUP.md): Q&A with short answers + evidence
- [review/PPT_OUTLINE.md](review/PPT_OUTLINE.md): Slide structure

**Figures (results/):**
- fig1: Clean vs faulted timing (8 checkpoints)
- fig2: Mahalanobis vs floor at CP3
- fig3: Detection rate by fault type
- fig4: Synthetic severity sweep
- fig5: Floor fraction sweep (3 panels)
- fig6: Mahalanobis with spike trimming

### 6. Git State ✅
- 6 commits ahead of origin/main (all local, unpushed per instructions)
- Tags: `phase1-complete` (final), `phase1-review-freeze-2` (frozen 4-CP firmware), `phase1-docs-final` (old)
- Clean working tree, no uncommitted changes

---

## Key Findings

1. **Mahalanobis worked on frozen data** (1000/1000, 1.4% FA) because training set had no timing spikes. Selection effect likely (halting build dropped 4 boots).

2. **Mahalanobis fails on 8-checkpoint data** because 14% of clean boots have timing spikes (>1.5× median), and the two-sided max-based threshold treats them like faults.

3. **Floor detector is robust:** One-sided (downward only), so spikes don't trigger it. 0% FA held-out, 298-300/300 detection on tested faults.

4. **Tiered response is embedded best practice:** Floor halts with high confidence (fail-stop), Mahalanobis warns with lower confidence (visibility into upward anomalies).

5. **FT-5 coverage gap:** Extra loop (+84%) only caught by Mahalanobis warning. Floor cannot see longer sub-stages.

6. **Build-to-build timing variation** (up to 28% across binaries, ISSUE-016): cause unknown. Calibrate on the same binary being validated.

7. **QEMU limitation (ISSUE-012):** SysTick follows host time, so partial skips are invisible. Severity sweep must wait for hardware.

---

## Scope vs Proposal

**Achieved:**
- QEMU-based fault injection ✅
- PMU timing telemetry (SysTick) ✅
- Statistical detection ✅
- Multiple fault types (6 vs planned 1) ✅✅
- Firmware-embedded detector ✅
- Held-out validation ✅
- 8 checkpoints (vs planned 4) ✅✅

**Deferred to Phase 2:**
- Real hardware validation (STM32L552)
- DWT counters (CYCCNT, CPICNT, LSUCNT, FOLDCNT)
- Debugger-based fault injection
- Electrical fault characterization
- Sequential CUSUM fusion across checkpoints
- 10,000-boot campaigns

---

## Phase 2 Readiness

**Immediate next steps:**
1. Port firmware to STM32L552
2. Replace SysTick with DWT counters
3. Collect hardware baseline (timing variance, spike rate)
4. Implement debugger-based fault injection
5. Test floor detector on hardware partial skips
6. Add retry-then-lockout response policy

**Open questions for hardware:**
- Are timing spikes still present with DWT counters?
- What is the build-to-build variation cause?
- Can the timer guard be tested/validated?
- Does the floor headroom (0.51 min vs 0.45 threshold) improve?

---

## Review-Ready Status

✅ **Core technical work complete:** Firmware detector validated on 4200 boots  
✅ **Documentation complete:** 9 markdown files, all cross-referenced  
✅ **Figures ready:** 6 slide plots generated  
✅ **Q&A prepared:** 25 common questions with evidence pointers  
✅ **Reproducible:** All scripts, data, and validation logs committed  

**Files to present:**
- Top-level: [../README.md](../README.md), [STATUS.md](STATUS.md)
- Technical: [FIRMWARE_DETECTOR.md](FIRMWARE_DETECTOR.md), [FAULT_MODELS.md](FAULT_MODELS.md)
- Analysis: [docs/MAHALANOBIS_ANALYSIS.md](docs/MAHALANOBIS_ANALYSIS.md)
- Review: [review/QA_BACKUP.md](review/QA_BACKUP.md)

**No further work required before review presentation.**

---

## Acknowledgments

Claude Code (claude.ai/code) assisted with implementation, debugging, and documentation throughout Phase 1.
