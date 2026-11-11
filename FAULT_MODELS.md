# Fault Injection Models

This document describes the 6 fault types implemented for detector robustness testing in Phase 1. Each fault simulates a control-flow or data-corruption attack via compile-time macros.

**Target:** 8-checkpoint bootrom with signature verification at CP3.

---

## Fault Type Summary

| ID | Label | Target | Attack Vector | Macro | Expected MD |
|----|-------|--------|---------------|-------|-------------|
| Original | ATTACK | CP3 sub_b | Loop skip (signature verify key load) | `GLITCH_ATTACK` | 19-32 |
| FT-1 | CP1_MEMCHECK | CP1 sub_b | Loop skip (memory init check) | `GLITCH_FT1_CP1_MEMCHECK` | 15-25 |
| FT-2 | CP3_COMPARE | CP3 sub_c | Loop skip (signature comparison) | `GLITCH_FT2_CP2_COMPARE` | 12-20 |
| FT-3 | CP7_HANDOFF | CP7 sub_a | Loop skip (stack setup) | `GLITCH_FT3_CP7_HANDOFF` | 10-18 |
| FT-4 | CP3_DOUBLE | CP3 sub_a+b | Double loop skip (hash + verify) | `GLITCH_FT4_CP2_DOUBLE` | >30 |
| FT-5 | CORRUPT_FLAG | CP3 | Variable corruption (adds work) | `GLITCH_FT5_CORRUPT_FLAG` | 8-15 |

---

## Original: GLITCH_ATTACK (CP3 sub_b)

**Checkpoint:** CP3 (Signature Verification)  
**Sub-stage:** B (public key load + modular reduction)  
**Attack:** Removes 300-iteration loop entirely (100% skip)

### Code
```c
#ifndef GLITCH_ATTACK
    #define SUB_B_ITERS 300
    for (int i = 0; i < SUB_B_ITERS; i++) x ^= (x * 31337U) >> 8;
#else
    #define SUB_B_ITERS 0  // Loop removed
#endif
```

### Effect
- **Clean `sub_b`:** ~799 cycles (varies 750-850)
- **Glitched `sub_b`:** ~87 cycles (empty loop overhead)
- **Reduction:** 89% (713 cycles)
- **Mahalanobis distance:** 19.08 to 31.89 (median ~23, clean max 8.67)

### Rationale
Primary attack target. Models voltage glitch during signature verification that skips the key loading step, causing the verification to pass with an invalid signature.

---

## FT-1: GLITCH_FT1_CP1_MEMCHECK (CP1 sub_b)

**Checkpoint:** CP1 (Hardware Initialization)  
**Sub-stage:** B (peripheral base address probing)  
**Attack:** Removes 200-iteration loop

### Code
```c
#ifdef GLITCH_FT1_CP1_MEMCHECK
    t2 = systick_elapsed();  // Skip loop
#else
    for (int i = 0; i < 200; i++) x ^= (i * 7);
    t2 = systick_elapsed();
#endif
```

### Effect
- **Clean `sub_b`:** ~644 cycles
- **Glitched `sub_b`:** ~96 cycles
- **Reduction:** 85% (548 cycles)
- **Expected MD:** 15-25

### Rationale
Tests detector sensitivity to faults outside the primary target (CP3). A glitch during memory initialization could allow boot from corrupted RAM regions.

---

## FT-2: GLITCH_FT2_CP2_COMPARE (CP3 sub_c)

**Checkpoint:** CP3 (Signature Verification)  
**Sub-stage:** C (signature comparison, the critical branch)  
**Attack:** Removes 200-iteration comparison loop

### Code
```c
#ifdef GLITCH_FT2_CP2_COMPARE
    t3 = systick_elapsed();  // Skip comparison
#else
    for (int i = 0; i < 200; i++) x = x ^ (uint32_t)(i * i);
    t3 = systick_elapsed();
#endif
```

### Effect
- **Clean `sub_c`:** ~548 cycles
- **Glitched `sub_c`:** ~85 cycles
- **Reduction:** 84% (463 cycles)
- **Expected MD:** 12-20

### Rationale
Targets the final comparison step in signature verification. Even if hash and key load succeed, skipping the comparison corrupts the "signature valid" decision.

---

## FT-3: GLITCH_FT3_CP7_HANDOFF (CP7 sub_a)

**Checkpoint:** CP7 (Handoff Preparation)  
**Sub-stage:** A (stack pointer and frame setup)  
**Attack:** Removes 120-iteration stack setup loop

### Code
```c
#ifdef GLITCH_FT3_CP7_HANDOFF
    t1 = systick_elapsed();  // Skip stack setup
#else
    for (int i = 0; i < 120; i++) sp += (i * 4);
    t1 = systick_elapsed();
#endif
```

### Effect
- **Clean `sub_a`:** ~585 cycles
- **Glitched `sub_a`:** ~85 cycles
- **Reduction:** 85% (500 cycles)
- **Expected MD:** 10-18

### Rationale
Late-stage attack after all security checks pass. A glitch during handoff setup could corrupt the application entry point or stack, causing the bootrom to jump to attacker-controlled code.

---

## FT-4: GLITCH_FT4_CP2_DOUBLE (CP3 sub_a + sub_b)

**Checkpoint:** CP3 (Signature Verification)  
**Sub-stages:** A (hash computation) + B (key load)  
**Attack:** Removes both 500-iteration and 300-iteration loops

### Code
```c
// Sub-stage A
#ifdef GLITCH_FT4_CP2_DOUBLE
    t1 = systick_elapsed();  // Skip hash
#else
    for (int i = 0; i < 500; i++) x = (x << 3) ^ (x >> 5) ^ (uint32_t)i;
    t1 = systick_elapsed();
#endif

// Sub-stage B
#if defined(GLITCH_FT4_CP2_DOUBLE)
    t2 = systick_elapsed();  // Skip key load
#elif ...
```

### Effect
- **Clean `sub_a`:** ~768 cycles, **Clean `sub_b`:** ~614 cycles
- **Glitched `sub_a`:** ~87 cycles, **Glitched `sub_b`:** ~87 cycles
- **Reduction:** 88% (1208 cycles total)
- **Expected MD:** >30 (likely >35)

### Rationale
**Tests the blind spot identified in audit finding F-01.** Skipping all verification loops together moves along the correlated direction of normal variance (all three sub-stages slow/fast together is normal host jitter). The shipped firmware threshold (H = 10.84) may not catch this if MD < 10.84. This fault type validates whether the detector's sensitivity is adequate.

---

## FT-5: GLITCH_FT5_CORRUPT_FLAG (CP3)

**Checkpoint:** CP3 (Signature Verification)  
**Sub-stage:** After sub_c (post-comparison)  
**Attack:** Data corruption (flips verification result flag)

### Code
```c
#ifdef GLITCH_FT5_CORRUPT_FLAG
    volatile uint32_t verify_flag = 1; /* normally set by comparison */
    for (int i = 0; i < 50; i++) {
        verify_flag ^= (x & 0x1); /* corrupt with hash bits */
    }
    (void)verify_flag;
#endif
```

### Effect
- **Adds ~50-60 cycles** rather than removing cycles
- **All sub-stages slightly inflated** (different direction from loop skips)
- **Expected MD:** 8-15 (less extreme than loop removal)

### Rationale
Different attack vector: **register fault** rather than control-flow fault. Models a glitch that corrupts the verification outcome boolean after the check completes. Tests whether the detector flags timing increases (not just decreases).

---

## QEMU Limitations

**Partial loop skips are invisible** in QEMU because SysTick measures wall-clock time, not executed instructions. Only 0% or 100% loop iteration changes are distinguishable. See [STATUS.md](STATUS.md) Section 6, Limitation 2 (ISSUE-012).

Phase 2 on STM32L552 with DWT CYCCNT will measure instruction-count-based timing, enabling partial-fault severity sweeps.

---

## Build and Collection

### Build Targets
```bash
make app.elf          # Clean baseline (no faults)
make app_attack.elf   # Original CP3 sub_b removal
make app_ft1.elf      # CP1 memory check skip
make app_ft2.elf      # CP3 comparison skip
make app_ft3.elf      # CP7 handoff skip
make app_ft4.elf      # CP3 double loop skip (blind spot test)
make app_ft5.elf      # Variable corruption
```

All attack builds include `-DCOLLECT_MODE` so the detector does not halt and telemetry is printed.

### Data Collection
```bash
# Collect 300 boots per fault type
bash scripts/collect_fault_types.sh 300 ds1

# Output: data/ds1_clean.csv, data/ds1_ft1.csv, ..., data/ds1_attack.csv
```

---

## Analysis

Detection rates per fault type are computed by:
1. Loading the fitted model (`data/model.npz`, trained on clean CP3 features)
2. Computing Mahalanobis distance for each boot's CP3 feature vector `[sub_a, sub_b, sub_c]`
3. Flagging as detected if `MD > H = 10.84`
4. Reporting detection rate with Wilson 95% confidence intervals

**Script:** `python scripts/fault_type_analysis.py`

**Expected results:**
- Original attack, FT-1, FT-2: >95% detection (large `sub_b` or `sub_c` reductions)
- FT-3: 80-95% detection (smaller loop, end-of-boot stage)
- FT-4: 50-80% detection (tests blind spot, may fail if MD < H)
- FT-5: 30-60% detection (adds cycles, less extreme than removal)

---

## Phase 2 Extensions

- **Hardware fault injection:** Debugger-based instruction skip, register corruption, clock glitches
- **Partial faults:** 10%, 30%, 50% loop reductions (requires DWT CYCCNT)
- **Multi-checkpoint attacks:** Spread fault across CP1 + CP3
- **Timing-channel attacks:** Side-channel leaks during crypto operations

See [STATUS.md](STATUS.md) Section 7 for Phase 2 plan.
