# Phase 1 Enhancement Plan

**Goal:** Strengthen Phase 1 deliverables with high-value additions before final review freeze.

**Timeline:** Estimated 40-60 hours of work over 1-2 weeks.

**Freeze point 1:** After F-01 through F-07 fixes (commit: `phase1-docs-final`)  
**Freeze point 2:** After all enhancements (commit: `phase1-complete`)

---

## 1. Multiple Fault Types (Priority: HIGH)

### 1.1 Current State
- Single fault model: CP2 sub_b loop removed (`-DGLITCH_ATTACK`)
- Only tests signature verification stage
- Demonstrates pipeline but not robustness

### 1.2 Proposed Fault Types

| Fault ID | Target | Description | Expected MD | Implementation |
|----------|--------|-------------|-------------|----------------|
| **FT-1** | CP1 sub_b | Skip memory init verification loop | ~15-25 | `#ifdef GLITCH_CP1_MEMCHECK` |
| **FT-2** | CP2 sub_c | Skip signature comparison loop | ~12-20 | `#ifdef GLITCH_CP2_COMPARE` |
| **FT-3** | CP3 sub_a | Skip key derivation hash loop | ~18-28 | `#ifdef GLITCH_CP3_KEYHASH` |
| **FT-4** | CP2 sub_a+b | Skip both hash and verify loops | >30 | `#ifdef GLITCH_CP2_DOUBLE` |
| **FT-5** | Variable corruption | Corrupt verification result flag | Varies | `#ifdef GLITCH_CORRUPT_FLAG` |

### 1.3 Rationale
- **FT-1, FT-2, FT-3:** Show detector works across different boot stages
- **FT-4:** Test multi-sub-stage fault (currently blind spot per F-01)
- **FT-5:** Different attack vector (data corruption vs control flow)

### 1.4 Effort
- Firmware modifications: 3 hours
- Data collection (5 types × 100 boots each): 7 hours
- Analysis scripts update: 2 hours
- **Total: 12 hours**

---

## 2. Multi-Checkpoint Fusion (Priority: HIGH)

### 2.1 Current State
- 4 checkpoints instrumented (CP0, CP1, CP2, CP3)
- Only CP2 is monitored by detector
- CUSUM state is per-boot, not accumulated across checkpoints

### 2.2 Proposed Enhancement

**A. Independent per-checkpoint models:**
- Fit 4 separate Gaussian models (one per checkpoint)
- Each checkpoint has its own `(μ, Σ⁻¹, k, H)`
- Alarm if ANY checkpoint triggers

**B. Fusion strategies to test:**
1. **OR-fusion:** Alarm if any CP exceeds its threshold (current + CP1, CP3)
2. **Sequential CUSUM:** Accumulate S across all checkpoints in one boot
3. **Weighted voting:** Each CP contributes to a combined score

### 2.3 Implementation
```c
// In main.c after each checkpoint:
for (int cp = 0; cp < NUM_CHECKPOINTS; cp++) {
    uint32_t features[3] = { boot_log[cp].sub_a, 
                             boot_log[cp].sub_b, 
                             boot_log[cp].sub_c };
    if (cusum_update(&detector_array[cp], features, cp)) {
        // Alarm at first violation (OR-fusion)
        uart_println("\r\n!!! ATTACK DETECTED at CP%d !!!", cp);
        alarm_handler(cp);
    }
}
```

### 2.4 Expected Results
- Reduced false alarm rate (fewer single-CP noise spikes alarm)
- Detection of attacks that spread across stages (e.g., timing side-channel)
- Better coverage of CP1, CP3 attacks

### 2.5 Effort
- Extend calibration script for 4 models: 2 hours
- Firmware detector array + loop: 3 hours
- Data collection (300 clean + 300 mixed faults): 8 hours
- Analysis and comparison: 3 hours
- **Total: 16 hours**

---

## 3. Expanded Boot Stages (Priority: MEDIUM)

### 3.1 Rationale
Real bootrom has multiple entry paths:
- UART boot (serial download)
- SPI boot (flash)
- CAN boot (automotive)
- USB boot (DFU mode)
- Secure vs non-secure boot

More checkpoints = more realistic model of production bootrom complexity.

### 3.2 Proposed Structure

Expand from 4 to **8 checkpoints:**

| CP | Stage | Sub-stages | Purpose |
|----|-------|------------|---------|
| 0 | Boot start | Init, UART, Clock config | Entry point |
| 1 | HW init | RAM test, Periph setup, Watchdog | Hardware |
| 2 | Boot mode detect | Pin sampling, Config read, Mode decode | Path selection |
| 3 | Signature verify (critical) | Hash, Load key, Verify | Security |
| 4 | Decrypt stage | Key derivation, IV setup, Decrypt | Confidentiality |
| 5 | Integrity check | CRC, Auth tag, Rollback | Tamper detection |
| 6 | Memory setup | MMU, MPU, TrustZone config | Isolation |
| 7 | Handoff | Stack setup, Jump to app | Transfer |

Each stage has 3 sub-stages (A/B/C) → 24-dimensional feature space total (8 × 3).

### 3.3 Implementation Strategy
- Each stage = busy loop with distinct instruction mix
- CP3 (signature verify) remains the primary attack target
- CP2, CP4, CP5 are also security-critical

### 3.4 Effort
- Firmware expansion: 6 hours
- Linker script / memory layout: 1 hour
- Testing new stages run correctly: 2 hours
- **Total: 9 hours**

---

## 4. 300-Boot Dataset Collection (Priority: HIGH)

### 4.1 Current State
- 496 clean boots (with 4 missing due to halting detector)
- 50 glitched boots (single fault type)

### 4.2 Proposed Datasets

| Dataset | Boots | Build | Purpose |
|---------|-------|-------|---------|
| **DS-1: Clean baseline** | 300 | Normal, non-halting | Model training |
| **DS-2: Fault type sweep** | 500 | 5 fault types × 100 boots | Detector coverage |
| **DS-3: Multi-CP fusion** | 300 | Faults at CP1/CP2/CP3 mixed | Fusion validation |
| **DS-4: 8-CP clean** | 300 | Expanded firmware | 8-checkpoint model |
| **DS-5: 8-CP attacks** | 400 | 8 checkpoints × 50 attacks | Full validation |

**Total boots to collect: 1,800**

### 4.3 Collection Strategy
- Use `-DCOLLECT_MODE` (non-halting) for all
- Batch collection via updated `scripts/collect.sh`
- Estimate: 0.8s per boot × 1,800 = 24 minutes per full sweep
- With build/setup overhead: ~3 hours per dataset

### 4.4 Data Quality
- Check for SysTick wraps (should be none with expanded stages)
- Outlier filtering: same 2.5 × IQR rule
- Missing boot detection and investigation

### 4.5 Effort
- Script updates: 2 hours
- Collection runtime: 15 hours (mostly unattended)
- Quality checks: 3 hours
- **Total: 20 hours**

---

## 5. Visualization and Analysis (Priority: HIGH)

### 5.1 Required Plots for Slides

#### 5.1.1 Architecture Diagram
- 8-stage bootrom flow with checkpoints marked
- Attack injection points highlighted
- Tool: draw.io or matplotlib with arrows

#### 5.1.2 Timing Stability
- Update existing `cycle_stability.png` for 8 checkpoints
- Violin plots showing clean distribution per CP
- Error bars on median

#### 5.1.3 Fault Type Coverage
- Bar chart: detection rate per fault type
- Grouped by checkpoint (CP1/CP2/CP3)
- Include confidence intervals

#### 5.1.4 Multi-Checkpoint Fusion
- ROC curves: single-CP vs OR-fusion vs sequential CUSUM
- False alarm rate vs detection rate trade-off
- Side-by-side confusion matrices

#### 5.1.5 Feature Space Visualization
- 3D scatter (sub_a, sub_b, sub_c) for CP2
- Clean cluster vs fault types in different colors
- Mahalanobis distance contours

#### 5.1.6 CUSUM Trace
- Time series of S statistic across 50 boots
- Show alarm threshold H, slack k
- Annotate where attack occurs

#### 5.1.7 Sensitivity Analysis
- Heatmap: checkpoint × fault severity → detection %
- X-axis: skip % (for QEMU, only 0% and 100% differ)
- Y-axis: checkpoint index

#### 5.1.8 Computational Cost
- Latency of `cusum_update()` per checkpoint
- Memory footprint breakdown (model params, boot_log, detector state)
- Comparison: 4-CP vs 8-CP overhead

### 5.2 New Analysis Scripts

Create these in `scripts/`:
- `fault_type_analysis.py`: Process DS-2, generate coverage plots
- `fusion_comparison.py`: Compare single-CP vs fusion strategies
- `sensitivity_heatmap.py`: Checkpoint × fault → detection rate
- `feature_space_3d.py`: 3D scatter with clusters
- `cusum_trace.py`: S statistic time series
- `latency_benchmark.py`: Process timing instrumentation

### 5.3 Effort
- Script development: 12 hours
- Figure generation and refinement: 6 hours
- **Total: 18 hours**

---

## 6. Updated Documentation

### 6.1 Files to Update
- **STATUS.md:** New results section with 8-CP, fusion, fault types
- **FIRMWARE_DETECTOR.md:** Multi-CP fusion design
- **PROJECT_GUIDE.md:** New data collection workflow
- **README.md:** Updated build targets for fault types

### 6.2 New Documents
- **FAULT_MODELS.md:** Describe each fault type and rationale
- **FUSION_ANALYSIS.md:** Comparison of fusion strategies

### 6.3 Effort
- Updates: 3 hours
- New docs: 2 hours
- **Total: 5 hours**

---

## 7. Implementation Timeline

### Week 1 (25 hours)
| Day | Task | Hours | Deliverable |
|-----|------|-------|-------------|
| 1 | Fix F-01 to F-07, commit freeze-1 | 3 | `phase1-docs-final` |
| 2 | Implement 5 fault types in firmware | 6 | `app_ft*.elf` builds |
| 3 | Expand to 8 checkpoints | 9 | Updated `main.c`, linker.ld |
| 4 | Update collection scripts | 4 | `collect_fault_types.sh` |
| 5 | Collect DS-1 and DS-4 (clean baselines) | 3 | `data/clean_300.csv`, `data/clean_8cp_300.csv` |

### Week 2 (35 hours)
| Day | Task | Hours | Deliverable |
|-----|------|-------|-------------|
| 6-7 | Collect DS-2, DS-3, DS-5 (fault datasets) | 12 | All fault type data |
| 8 | Implement multi-CP fusion in firmware | 5 | `cusum_detector.c` with array |
| 9 | Calibrate 8-CP models | 3 | `data/model_8cp.npz` |
| 10-11 | Write 6 new analysis scripts | 12 | Fusion, fault type, sensitivity scripts |
| 12 | Generate all plots for slides | 6 | 8 publication-ready figures |
| 13 | Update documentation | 5 | STATUS.md, new .md files |
| 14 | Final validation run (300+300 boots) | 4 | `results/validation_final.log` |

**Total: 60 hours over 2 weeks**

---

## 8. Risk Mitigation

### 8.1 QEMU Limitations (Known)
- **Risk:** 8 checkpoints may expose more SysTick wraps
- **Mitigation:** Keep total boot time < 100k cycles; measure after expansion
- **Fallback:** Drop to 6 checkpoints if wraps appear

### 8.2 Data Collection Time
- **Risk:** 1,800 boots × 0.8s = 24 min, but script overhead may double it
- **Mitigation:** Parallelize collection (4 QEMU instances)
- **Fallback:** Reduce to 200 boots per dataset (1,200 total)

### 8.3 Model Retraining
- **Risk:** 8-CP models may not converge or have singular covariance
- **Mitigation:** Check condition number; apply regularization if needed
- **Fallback:** Use PCA to reduce dimensions before Mahalanobis

### 8.4 False Alarm Rate with 8 Checkpoints
- **Risk:** More checkpoints → more opportunities to false-alarm
- **Mitigation:** Use Bonferroni correction (H × √8) or fusion strategies
- **Fallback:** Report per-checkpoint false alarm rates separately

---

## 9. Success Criteria

**Must achieve:**
1. ✅ All F-01 to F-07 fixed and committed
2. ✅ At least 3 fault types implemented and tested
3. ✅ Multi-CP fusion working in firmware (OR-fusion minimum)
4. ✅ 300 clean boots collected for baseline
5. ✅ 6+ publication-quality plots generated

**Stretch goals:**
6. ⭐ 8 checkpoints fully validated
7. ⭐ 1,800-boot full dataset
8. ⭐ Sequential CUSUM fusion implemented
9. ⭐ Latency benchmarking complete

---

## 10. Deliverables for Slides

After completion, you will have data to present:

1. **Architecture slide:** 8-stage bootrom with attack surface
2. **Threat model slide:** 5 fault types with examples
3. **Detection results table:** 
   - Per fault type: detection rate, false alarm rate
   - Per checkpoint: coverage
   - Fusion vs single-CP comparison
4. **ROC curves:** Showing improved performance with fusion
5. **Sensitivity analysis:** Which faults are hardest to detect
6. **Computational cost:** Overhead of 4-CP vs 8-CP detector
7. **Dataset summary:** 1,800+ boots across 5 datasets

---

## 11. Git Commit Strategy

| Commit | Tag | Content |
|--------|-----|---------|
| After F-01 to F-07 | `phase1-docs-final` | Clean documentation |
| After fault types + 4-CP fusion | `phase1-enhanced-v1` | Multi-fault validation |
| After 8-CP expansion | `phase1-enhanced-v2` | Full bootrom model |
| After all plots + docs | `phase1-complete` | Final freeze for review |

---

## 12. Phase 2 Handoff

This work directly feeds Phase 2:
- **8-CP model** → maps to STM32L552 real boot flow
- **Fault type library** → guides debugger-based fault injection
- **Fusion strategies** → test on hardware with DWT counters
- **300-boot datasets** → establish variance baseline for hardware comparison

---

**Next steps:** 
1. Review this plan
2. Approve or adjust scope
3. Wait for F-01 to F-07 agent to complete
4. Commit freeze-1
5. Begin Week 1 implementation
