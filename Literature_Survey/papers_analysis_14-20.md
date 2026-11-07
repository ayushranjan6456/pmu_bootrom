# Literature Analysis: Papers 14-20 (Final Batch)
## PMU-Based Fault Injection Detection Project Context

**Document Purpose:** Deep analysis of the final 7 papers (14-20) from the literature survey, examining their key contributions and relevance to our PMU-based statistical detection system for secure boot fault injection attacks.

**Our Project Recap:**
- **Goal:** Detect voltage/clock glitch attacks on ARM Cortex-M33 bootrom using PMU telemetry
- **Method:** Statistical anomaly detection (CUSUM algorithm) on cycle timing features
- **Current Status:** Python detector functional (99% detection @ 1% false alarm), needs firmware porting
- **Critical Gap:** Non-redundant signature check (A7 violation from Paper 10), real-time detection not yet implemented

---

## Paper 14: Injecting Software Vulnerabilities with Voltage Glitching (2019)

### Summary
Presents theoretical model of voltage glitching based on CMOS transistor behavior to understand when combinational logic is most susceptible to faults. Applies understanding to attack PlayStation Vita's F00D security processor (Samsung 45nm SoC, MeP architecture) to gain boot-time execution control and dump boot ROM. Uses ChipWhisperer crowbar voltage glitching with fully automated parameter search (exhaustive N, M sweep).

### Key Contributions

1. **Theoretical Foundation - CMOS Timing Analysis:**
   - **Setup/hold time violations:** Root cause of voltage glitch faults (validates Paper 3's findings)
   - **Propagation delay increase:** Voltage drop → longer gate delays → timing violation
   - **D-flip-flop immunity:** Memory elements mostly immune to voltage glitches (from [Djellid-Ouar 2004])
   - **Combinational logic vulnerability:** Logic gates between registers are susceptible

2. **Crowbar Method (O'Flynn 2016):**
   - Abuses capacitance ringing effect
   - Introduces crowbar circuit into existing system
   - Ringing causes exploitable faults
   - Low-cost, ChipWhisperer-compatible

3. **Attack on PlayStation Vita Boot ROM:**
   - **Target:** F00D security processor (MeP architecture, boot ROM unmapped after early boot)
   - **Vulnerability:** `bldr_size` check in boot ROM
   - **Exploit:** Glitch parameter sweep (N=offset, M=width) overnight
   - **Success:** Found valid (N, M) pair with >80% reproducibility
   - **Effect:** Glitch causes exactly 0xE2 blocks read (overwriting executed code)
   - **Result:** Dump boot ROM via UART (iterative glitching for complete extraction)

4. **Attack Characteristics:**
   - **Reproducibility:** >80% with same (N, M) parameters (if equipment not moved)
   - **Environmental sensitivity:** Wire/external capacitance affects parameters (setup-specific)
   - **Iterative approach:** Multiple glitches at different boot stages to extract full ROM

### Relevance to Our Project: ⭐⭐⭐ (High)

**Why It Matters:**

1. **Theoretical Validation:**
   - Paper provides **CMOS-level explanation** for why glitches work
   - Confirms our assumption: timing violations are root cause
   - **Our PMU detector targets this root cause** (timing shift detection)

2. **Boot ROM Attack Similarity:**
   - PlayStation Vita: Glitch boot ROM to gain execution control
   - Our target: Glitch bootrom signature verification
   - **Same attack vector, different platform**

3. **ChipWhisperer Methodology:**
   - Paper's approach: Exhaustive parameter sweep (N × M grid)
   - Automated overnight search
   - **Our Phase 2 plan:** Same ChipWhisperer, same methodology

4. **Reproducibility Insight:**
   - 80% success rate with fixed parameters
   - Environmental factors (capacitance, wiring) critical
   - **Implication:** Phase 2 setup must be stable, document environment

**Limitations for Our Use:**

1. **Different Architecture:**
   - MeP architecture (not ARM)
   - Different instruction set, different pipeline
   - Lessons transfer conceptually, not directly

2. **Boot ROM Mapping:**
   - Vita's ROM unmapped after early boot (cleanup)
   - Our bootrom in fixed ROM (no unmapping)
   - Different extraction challenge

**Direct Applications:**

1. **CMOS Timing Model:**
   - Paper's propagation delay analysis explains **why** sub_b is vulnerable:
     - Signature verification loop has longest combinational path
     - Highest propagation delay → shortest timing slack
     - **First to violate setup time under voltage drop**

2. **Parameter Search Strategy:**
   ```python
   # ChipWhisperer parameter sweep (from paper):
   for N in range(offset_min, offset_max):  # Timing offset
       for M in range(width_min, width_max):  # Glitch width
           scope.glitch.offset = N
           scope.glitch.width = M
           result = inject_glitch_and_test()
           if result == "success":
               log_parameters(N, M)
   ```
   **Our Phase 2:** Implement same exhaustive search for (offset, width, checkpoint) space

3. **Environmental Calibration:**
   - Paper shows parameters are setup-specific
   - **Action:** Document Phase 2 setup (wire lengths, capacitor placement, board layout)
   - Re-calibrate after any physical change

4. **Iterative Glitching:**
   - Paper uses multiple glitches at different boot stages
   - **Our equivalent:** Test glitches at CP0, CP1, CP2, CP3 independently
   - Map vulnerability window for each checkpoint

**Key Quote:**
> "By looking at how voltage glitches introduce timing violations into a digital circuit, we can find good snippets of code to glitch." (Conclusion)

**Our detector targets these snippets:** Signature verification loop in `stage_signature_verify()`.

---

## Paper 15: Microarchitectural Insights into Unexplained Behaviors Under Clock Glitch (2023)

### Summary
Proposes novel binary-encoding fault models ("partial update" models) to explain faulty behaviors from clock glitching that previous models couldn't account for. Examines dependency on target device and program. Demonstrates breaking control-flow integrity by altering program counter. Performs physical experiments on ARM Cortex-M4 (STM32F407) and simulations on multiple architectures.

### Key Contributions

1. **Novel Fault Models:**
   - **Partial Update from Precharge Value:**
     - Flash memory pre-charges to default (0xFF or 0x00) before fetch
     - Clock glitch causes premature latch
     - Instruction partially updated with precharge bits
     - **Effect:** Instruction corruption (not just skip!)
   
   - **Partial Update from Previous Value:**
     - Instruction register retains bits from previous instruction
     - Clock glitch causes incomplete fetch
     - New instruction mixed with old instruction bits
     - **Effect:** Hybrid instruction execution

2. **Comparison with Prior Fault Models:**

| Fault Model | Paper Source | Explanation Coverage |
|-------------|--------------|---------------------|
| Instruction Skip | [Moro 2014, Rivière 2015] | ~50% of faults |
| Instruction Replay | [Moro 2014] | ~10% of faults |
| Skip & Repeat N bits | [Beringuier-Boher 2020] | ~30% more faults |
| **Partial Update (This paper)** | **Paper 15** | **Remaining unexplained faults** |

   **Key insight:** Previous models explain many faults but not ALL → new models fill gaps

3. **Experimental Validation:**
   - **Platform:** STM32F407 (ARM Cortex-M4, 168 MHz)
   - **Attack target:** Program counter (PC) modification
   - **Method:** Clock glitch during branch instruction
   - **Result:** PC jumps to unintended address (control-flow hijack)

4. **Dependency Analysis:**
   - **Device dependency:** Different microcontrollers show different fault distributions
   - **Program dependency:** Instruction alignment in flash affects fault type
   - **Flash access size:** Determines which partial update model applies

### Relevance to Our Project: ⭐⭐⭐⭐ (Very High)

**Why It Matters:**

1. **Explains "Unexplained" Fault Behaviors:**
   - Previous models: Instruction skip, replay
   - This paper: **Instruction corruption** (hybrid instructions)
   - **Critical for our detector:** Must handle ALL fault types, not just skip

2. **Program Counter Hijacking:**
   - Paper demonstrates PC modification via clock glitch
   - **Our risk:** Glitch could corrupt `boot_decision` address (not just value)
   - Example:
   ```c
   // Normal: PC = 0x00000280 (boot_decision check)
   // Glitched: PC = 0x000002FF (partial update from 0xFF precharge)
   // Result: Jump to unintended code (bypass signature check)
   ```

3. **Partial Update Fault Model Application:**
   - **Our signature verification loop:**
   ```c
   // Normal instruction:  
   cmp r5, #10           // Compare loop counter
   // Partial update (precharge 0xFF):
   cmp r5, #255          // Corrupted comparison
   // Result: Loop exits early (255 != counter)
   ```
   **PMU signature:** sub_b cycle count decreases (same as instruction skip)

4. **Flash Memory Alignment:**
   - Paper shows instruction alignment affects fault type
   - **Our bootrom:** Check `.text` section alignment in `linker.ld`
   - If misaligned, partial update faults more likely

**Fault Effect Catalog for PMU:**

| Fault Model | Effect on PC/Instruction | PMU Telemetry Signature | Detection Difficulty |
|-------------|--------------------------|-------------------------|---------------------|
| **Instruction Skip** | Next instruction not executed | Cycle count decrease (sub_b drops) | Easy (large shift) |
| **Instruction Replay** | Same instruction executed twice | Cycle count increase (sub_b rises) | Medium (could be noise) |
| **Partial Update (precharge)** | Corrupted immediate value | Variable (depends on corruption) | Medium-Hard |
| **Partial Update (previous)** | Hybrid instruction | Unpredictable behavior | Hard (random effect) |

**Direct Applications:**

1. **Vulnerability Assessment:**
   - **Audit bootrom instructions:** Which are vulnerable to partial update?
   - Critical instructions in `stage_signature_verify()`:
     - `ldr` (load signature): Partial update → wrong data loaded
     - `cmp` (comparison): Partial update → wrong comparison value
     - `beq` (branch): Partial update → wrong branch target
   
   **Action:** Disassemble `app.elf`, identify critical instructions, map to fault models

2. **PMU Feature Vector Robustness:**
   - Partial update faults create **wider range of timing shifts** than simple skip
   - Need to verify our Gaussian model captures this variance
   - **Test:** Simulate partial update faults in QEMU (not just break loop)

3. **Countermeasure - Redundant Encoding:**
   - Paper suggests: Use constants with large Hamming distance
   - **Our application:**
   ```c
   // Before (vulnerable):
   volatile uint32_t verified = 1;  // 0x00000001
   
   // After (hardened):
   #define VERIFIED_MAGIC 0xCAFEBABE  // Large Hamming distance from 0
   volatile uint32_t verified = 0;
   if (signature_valid) verified = VERIFIED_MAGIC;
   if (verified == VERIFIED_MAGIC) { /* boot */ }
   ```
   Partial update unlikely to flip 0x00000000 → 0xCAFEBABE

4. **Flash Memory Alignment:**
   - **Check current alignment:**
   ```bash
   arm-none-eabi-objdump -d app.elf | grep stage_signature_verify -A 50
   # Look for instruction addresses (must be aligned)
   ```
   - **Fix misalignment:** Add padding in `linker.ld` or use `.align` directive

**Key Quote:**
> "The partial update fault models allow explaining a wide range of the faulty behaviors that are obtained when performing clock glitch fault injection campaigns." (Conclusion)

**Our detector must account for this wide range** → Gaussian model + CUSUM's flexibility validated.

---

## Paper 16: Peak Clock - Fault Injection into PLL-Based Systems via Clock Manipulation (2019)

### Summary
Challenges the assumption that internal Phase-Locked Loops (PLLs) protect against clock glitch attacks. Demonstrates that despite PLL filtering, fault injection via external clock manipulation is feasible on ARM Cortex-M processors by using **prolonged high-frequency signal** instead of short spike. Successfully performs Differential Fault Attack (DFA) on AES implementation. Introduces concept of "instruction shadowing" where sensitive instructions mask robust ones.

### Key Contributions

1. **PLL Myth Debunked:**
   - **Common assumption:** PLL detaches internal clock from external → immune to glitches
   - **Reality:** PLL-based systems ARE vulnerable (just harder to attack)
   - **Key difference:** Short spike ineffective, need **sustained high-frequency signal**

2. **Attack Methodology:**
   - **Traditional glitch:** Short spike (nanoseconds)
   - **PLL glitch:** High-frequency signal (microseconds duration)
   - **Mechanism:** Selective overclocking beyond max frequency
   - **Effect:** Setup/hold violations when PLL tries to follow rapid frequency change

3. **Experimental Results - Two ARM Cortex-M Devices:**

   **Device S (Slowly Adapting PLL):**
   - Nominal: 48 MHz (max)
   - Input: 4 MHz external, PLL multiplies to 48 MHz
   - Attack: Increase input from 4 MHz → 10 MHz for 100 μs
   - PLL response: Linear increase @ 0.625 MHz/μs
   - Peak frequency reached: 110 MHz (2.3× overspeed)
   - **Success rate:** 85-90% (optimal window: 117-134 μs glitch duration)
   - **Crash rate:** Low in optimal window, increases to 45% beyond 138 μs

   **Device X (Fast Adapting PLL):**
   - Nominal: 120 MHz (max)
   - Input: 4 MHz external
   - PLL response: Very fast @ 80 MHz/μs
   - Unstable range: 150-160 MHz
   - Attack duration: 500 ns (much shorter than Device S)
   - **Success rate:** Only ~8% (PLL switches to internal clock upon instability)

4. **Instruction Shadowing Effect:**
   - **Definition:** Sensitive instructions overshadow robust ones in temporal vicinity
   - **Mechanism:** Glitch affects multiple instructions; most susceptible one faults first
   - **Example:** `ldr` (load) more sensitive than arithmetic instructions
   - **Implication:** Cannot predict which specific instruction faults
   - **Memory source matters:** SRAM vs Flash have different fault thresholds

5. **DFA on AES:**
   - Successfully performed Differential Fault Attack on AES-128
   - Recovered secret key using faulty ciphertexts
   - Proves attack is practical, not just theoretical

### Relevance to Our Project: ⭐⭐⭐⭐ (Very High)

**Why It Matters:**

1. **PLL Reality Check:**
   - **Our Cortex-M33:** Likely has internal PLL (modern ARM cores do)
   - **Implication:** PLL doesn't eliminate glitch threat, just changes attack parameters
   - **Phase 2 impact:** Need longer glitch durations (microseconds not nanoseconds)

2. **Attack Parameter Adjustment:**
   
   | Attack Type | Duration | Mechanism | Our Platform |
   |-------------|----------|-----------|--------------|
   | Non-PLL glitch | 10-100 ns | Direct clock spike | If no PLL |
   | PLL glitch (Device S) | 117-134 μs | Sustained high frequency | If slow PLL |
   | PLL glitch (Device X) | ~500 ns | Fast overclocking | If fast PLL |
   
   **Action:** Determine Cortex-M33 PLL characteristics (check datasheet/QEMU model)

3. **Instruction Shadowing:**
   - **Our vulnerable code:** Signature verification loop has mixed instructions
     - `ldr` (load signature bytes) - **Highly sensitive** (Paper's finding)
     - `eor` (XOR hash computation) - Arithmetic (less sensitive)
     - `cmp` (compare result) - **Moderately sensitive**
   - **Implication:** Glitch will hit `ldr` first (shadow arithmetic operations)
   - **PMU signature:** sub_b decrease from failed `ldr`, not from skipped `eor`

4. **Success Rate Comparison:**
   - Device S: 85-90% (with slow PLL)
   - Device X: 8% (with fast PLL + internal clock fallback)
   - **Our goal:** Detect attacks on BOTH device types
   - **Advantage:** PMU timing anomaly detects regardless of PLL behavior

**Direct Applications:**

1. **PLL Characterization for Phase 2:**
   ```python
   # ChipWhisperer script for PLL characterization:
   def characterize_pll():
       for duration in range(100, 200000, 1000):  # 100 ns to 200 μs
           for freq in [10e6, 20e6, 50e6, 100e6]:  # Test frequencies
               scope.glitch.clk_src = 'clkgen'
               scope.glitch.offset = 0
               scope.glitch.width = duration
               scope.clock.clkgen_freq = freq
               result = inject_and_monitor()
               if result == "fault":
                   log_pll_threshold(duration, freq)
   ```

2. **Instruction Sensitivity Mapping:**
   - **Disassemble `stage_signature_verify()`:**
   ```bash
   arm-none-eabi-objdump -d app.elf | grep -A 100 stage_signature_verify
   ```
   - **Catalog instruction types:**
     - Count `ldr/str` (memory access) - **High sensitivity**
     - Count arithmetic (`add/sub/eor`) - Medium sensitivity
     - Count branches (`b/beq/bne`) - **Critical** for control flow
   - **Hypothesis:** Most glitches hit `ldr` in signature load loop

3. **SRAM vs Flash Sensitivity:**
   - Paper: Flash and SRAM behave differently under glitch
   - **Our bootrom:**
     - Code in Flash (ROM @ 0x00000000)
     - Data (fake_signature) in Flash (constants)
     - Stack in RAM (@ 0x20000000)
   - **Test:** Do glitches hitting Flash loads differ from RAM loads?

4. **Optimal Glitch Window:**
   - Paper's Device S: Narrow optimal window (117-134 μs = 17 μs range)
   - **Implication:** Parameter search needs fine granularity (1 μs steps)
   - **Automation:** Use binary search first (coarse), then linear scan (fine)

5. **Crash vs Exploit:**
   - Paper: Crash rate increases with longer glitch
   - **Our detector:** Should NOT alarm on crash (system halts anyway, no security breach)
   - **Alarm on:** Successful exploit (signature bypassed, system continues booting)
   - **Metric:** F_exploitable (from Paper 10), not just "any fault"

**Software Countermeasure Insight:**

Paper's Section 6.1 notes:
> "Precise clock glitches... required [for breaking control flow protection] are highly unlikely [with PLL]."

**Implication:** Redundant checks (Paper 10's A7 mitigation) MORE effective with PLL:
- PLL makes glitch imprecise
- Hitting multiple redundant checks with imprecise glitch → very low probability
- **Our hybrid defense:** PMU detection + redundant checks + PLL = multi-layer

**Hardware Countermeasure Lesson:**

Paper proposes: PLL loss-of-lock detection → interrupt + fault handler
- **Our equivalent:** Combine PMU alarm with voltage monitor
- If PLL unlocks OR PMU timing anomaly → halt boot

---

## Paper 17: Practical Analysis of Embedded Microcontrollers Against Clock Glitching Attacks (2014)

### Summary
Master's thesis implementing modular clock glitcher for AVR microcontrollers with automated brute-force parameter search. Demonstrates vulnerability of AVR architecture through experiments on loops (JMP, RJMP, conditional branches) and real-world `strcpy` function. Shows successful data extraction from memory by glitching null-byte termination check. Discusses pipeline effects where glitching one instruction corrupts the next due to overlapping fetch/execute.

### Key Contributions

1. **Modular Glitcher Environment:**
   - Fine-tuning of attack parameters
   - Brute-force algorithm for finding glitch range
   - Automated parameter sweep (can run hours/days)
   - DDK (Development Kit) for trigger synchronization and result detection

2. **Attack Experiments on AVR:**

   **Unconditional Loops:**
   - **JMP instruction:** 3 clock cycles, 32-bit (2 fetches)
     - Glitching for 2 cycles skips instruction
     - Success: Exit infinite loop
   
   - **RJMP instruction:** 2 clock cycles, 16-bit (1 fetch)
     - Can be glitched within 1-3 cycles (less precise than JMP)
     - Relative jump (offset-based addressing)

   **Conditional Loops:**
   - Branch instructions (BRNE, BEQ, etc.)
   - Glitching condition check → forced exit/entry

   **Real-World Attack - `strcpy` Function:**
   - **Goal:** Glitch null-byte termination check
   - **Effect:** Copy beyond string boundary → memory leak
   - **Result:** Successfully extracted "secret" strings from adjacent memory
   - **Attack vector:** Glitch `AND` instruction that tests for null byte
   - **Difficulty:** Required precise timing (extensive brute-force)

3. **Key Findings:**

   - **Pipeline Effect:** Glitching one instruction corrupts the next (RISC pipeline issue)
   - **Mitigation:** Insert NOP between instructions (if code modifiable)
   - **Instruction Timing:** Multi-cycle instructions (JMP, branches) more vulnerable
   - **Operand Corruption:** Can glitch part of instruction (corrupt operand, not opcode)
   - **Brute-Force Feasibility:** Hours to days of automated search finds parameters

4. **Timing Analysis Results:**

   | Function | Total Cycles | Vulnerable Cycles | Glitch Characteristics |
   |----------|--------------|-------------------|------------------------|
   | JMP loop | Variable | Every cycle (inside loop) | Exactly 2 cycles needed |
   | RJMP loop | Variable | Every cycle | 1-3 cycles works |
   | strcpy | ~256 per char | Null-byte check moment | Precise timing required |

### Relevance to Our Project: ⭐⭐ (Medium)

**Why Lower Relevance:**

1. **Different Architecture:**
   - Paper: AVR (8-bit RISC, Harvard architecture)
   - Our target: ARM Cortex-M33 (32-bit RISC, Von Neumann)
   - Different instruction set, different pipeline

2. **Different Attack Goal:**
   - Paper: Memory extraction via buffer overflow
   - Our goal: Signature verification bypass

**Conceptual Similarities:**

1. **Brute-Force Parameter Search:**
   - Paper's approach: Exhaustive (offset, width) sweep
   - **Our Phase 2:** Same methodology (align with Paper 9, 10, 14)

2. **Loop Glitching:**
   - Paper: Glitch branch to exit loop
   - **Our attack:** Glitch loop in `stage_signature_verify()` (early break)
   - Same fundamental mechanism

3. **Null-Byte Check Pattern:**
   - Paper's strcpy: Glitch `AND r0, r0` (test for zero)
   - **Our equivalent:** Glitch `cmp dummy_hash, expected_hash` (test for equality)
   - Similar vulnerability pattern

**Direct Applications:**

1. **Pipeline Effect Awareness:**
   - **AVR pipeline:** Fetch next instruction while executing current
   - **ARM Cortex-M33 pipeline:** 3-stage (Fetch, Decode, Execute)
   - **Risk:** Glitch at CP2 could corrupt instruction at CP3
   - **Mitigation:** Ensure critical checkpoints separated by enough cycles

2. **NOP Padding Strategy:**
   - Paper suggests: Insert NOP between critical instructions
   - **Our bootrom:** Add NOP padding around `pmu_checkpoint()` calls
   ```c
   // Before:
   pmu_checkpoint(2);
   if (dummy_hash == expected_hash) { /* boot */ }
   
   // After (hardened):
   pmu_checkpoint(2);
   __asm volatile("nop"); __asm volatile("nop"); __asm volatile("nop");
   if (dummy_hash == expected_hash) { /* boot */ }
   ```
   **Effect:** Glitch hitting `pmu_checkpoint` doesn't corrupt comparison

3. **Operand Corruption Risk:**
   - Paper: Can glitch part of instruction (change immediate value)
   - **Our risk:** Glitch could corrupt `expected_hash` value (not just skip check)
   - Example:
   ```c
   // Normal:  if (dummy_hash == 0x12345678) ...
   // Glitched: if (dummy_hash == 0x123456FF) ...  // Partial update
   // Result: Comparison fails even with valid signature!
   ```
   **Test:** Verify CUSUM detects both skip AND corruption (both shift timing)

4. **Automated Search Lesson:**
   - Paper: Brute-force search can take days but eventually succeeds
   - **Our Phase 2:** Budget sufficient time for parameter search
   - Estimate: 14,878 glitches (Paper 9) × 4 checkpoints × 100 μs/glitch = ~1.5 hours per sweep

**Limited Transferability:**

- AVR-specific findings (JMP 3 cycles, RJMP 2 cycles) don't map to ARM
- strcpy attack vector not applicable to bootrom (no string operations)
- Pipeline depth different (AVR 2-stage, ARM M33 3-stage)

---

## Paper 18: Shaping the Glitch - Optimizing Voltage Fault Injection Attacks (2019)

### Summary
Proposes **arbitrary glitch waveform** technique using off-the-shelf low-cost equipment to generate fully customizable voltage glitch shapes (beyond traditional square or V-shaped pulses). Presents 6 unpublished firmware extraction attacks on microcontrollers from STMicroelectronics, Texas Instruments, and Renesas. Most challenging attacks require >1 million glitches. Compares arbitrary waveforms vs traditional V-FI techniques, showing significant performance improvement.

### Key Contributions

1. **Arbitrary Glitch Waveform Innovation:**
   - **Traditional V-FI:** Square pulse or V-shape (limited parameters: voltage, width, offset)
   - **Arbitrary waveform:** Fully programmable shape (any voltage-time profile)
   - **Advantage:** Optimized waveform increases success rate and reduces total glitches needed
   - **Equipment:** Off-the-shelf (<$3000 budget)

2. **Rising/Falling Edge Insight:**
   - Prior work [ZDCR14]: Disturbances caused by **edges**, not pulse shape
   - **This paper:** Arbitrary waveforms have multiple edges → more opportunities to induce fault
   - **Optimization:** Search waveform space, not just (offset, width) space

3. **Six Firmware Extraction Attacks:**

   **Class 1 - Low/Moderate Complexity (≤100k glitches):**
   - STM32F0, STM32F1, MSP430
   - Straightforward attack logic
   - Skip bootloader security checks
   - Extract protected firmware

   **Class 2 - High Complexity (>1 million glitches):**
   - STM32F4, MSP430F5, Renesas RL78
   - Multiple vulnerabilities exploited
   - Several days to complete
   - Heavy reliance on performance and repeatability

4. **Performance Comparison:**

   | Technique | Glitches Needed | Extraction Speed | Success Rate |
   |-----------|-----------------|------------------|--------------|
   | Square pulse | Baseline (100%) | Baseline | Baseline |
   | V-shaped pulse | ~80% | ~1.2× faster | Similar |
   | **Arbitrary waveform** | **~50%** | **~2× faster** | **Higher** |

   **Key finding:** Arbitrary waveforms reduce glitches by ~50% (same attack, fewer attempts)

5. **Responsible Disclosure:**
   - All vulnerabilities reported to manufacturers (ST, TI, Renesas)
   - Combined market: ~$4.8 billion (widespread impact)

### Relevance to Our Project: ⭐⭐⭐ (High)

**Why It Matters:**

1. **Attack Sophistication Trend:**
   - 1 million glitches to extract firmware (Class 2 attacks)
   - **Implication:** Attackers are persistent and have automated tools
   - **Our detector must remain effective** even against sophisticated multi-attempt attacks

2. **Waveform Optimization:**
   - Attackers will optimize glitch waveform for target
   - **Our PMU detector advantage:** Waveform-agnostic (detects timing shift regardless of shape)
   - **Validation needed:** Test detector against various waveform shapes (Phase 2)

3. **Bootloader Attack Prevalence:**
   - 6 microcontrollers, all bootloader attacks
   - **Validates our threat model:** Bootloader is primary target
   - **Our project directly addresses this threat**

4. **Low-Cost Equipment:**
   - Paper uses <$3000 equipment
   - **Implication:** Attacks are accessible to motivated adversaries
   - **Our detection must assume skilled attacker with good equipment**

**Direct Applications:**

1. **Waveform Diversity Testing (Phase 2):**
   - Don't just test square pulse (Paper 9, 12, 16)
   - Test multiple waveform shapes:
     - Square pulse (baseline)
     - V-shaped (ramp up/down)
     - Double pulse (two edges)
     - Arbitrary (optimized by attacker)
   - **Validation:** CUSUM detects all waveform types

2. **Performance Benchmark:**
   - Paper achieves 2× speed improvement with optimization
   - **Our detector latency:** ~2000 cycles (per checkpoint)
   - **Question:** Can attacker inject 2000 glitches before detection?
   - **Answer:** No, glitch takes ~100 μs (Paper 16), 2000 cycles = 40 μs @ 50 MHz → detection faster

3. **Million-Glitch Scenario:**
   - Paper's Class 2 attacks: >1M glitches to extract firmware
   - **Our bootrom:** Each glitch attempt = full boot cycle (~10,000 cycles)
   - 1M attempts = 1M boots → **all detected by PMU** (1% false negative means 10k missed)
   - **Advantage:** Cumulative detection over many attempts

4. **Responsible Disclosure Model:**
   - Paper reports vulnerabilities to vendors
   - **Our Phase 2 results:** Should we disclose to ARM/NXP/ST?
   - If Cortex-M33 bootrom vulnerable → responsible disclosure

**Attack Complexity Classes:**

Paper's classification useful for Phase 2 planning:

| Class | Glitches | Duration | Our Test Plan |
|-------|----------|----------|---------------|
| **Class 1** | ≤100k | Hours | Phase 2 initial validation |
| **Class 2** | >1M | Days | Phase 2 extended stress test |

**Key Insight - Edge-Based Faults:**

Paper confirms: **Rising/falling edges** cause faults, not pulse magnitude
- **Implication:** Glitch width matters less than edge timing
- **Our CUSUM:** Timing-based detector perfectly aligned with edge-based fault mechanism

**Arbitrary Waveform Challenge:**

- Attacker can optimize waveform → increase success rate
- **Our defense:** Statistical detection robust to waveform variations
- **Reason:** Timing shift magnitude (Mahalanobis distance) increases with fault severity
- Optimized waveform → stronger fault → **larger timing shift → easier to detect**

---

## Paper 19: System Clock and Power Supply Cross-Checking for Glitch Detection (2016)

### Summary
Proposes hardware-based clock glitch detection using ring oscillator (RO) or voltage-controlled oscillator (VCO) as reference. Implemented on Virtex-5 FPGA protecting AES. RO frequency independent of system clock → glitch affects system but not RO → divergence detected. Achieves ~100% detection rate for glitches up to 207 MHz (RO1) or 185 MHz (RO2). Multiple detection modules can be combined to improve detection rate (1-(1-p)^n).

### Key Contributions

1. **Cross-Checking Concept:**
   - **System clock:** Affected by glitch (attacker-controlled)
   - **Reference clock (RO):** Independent, stable (not affected by glitch)
   - **Detection:** Compare system clock behavior against reference
   - **Alarm:** Triggered when divergence exceeds threshold

2. **Ring Oscillator Design:**
   - **RO1:** 414.1 MHz (can detect up to 207 MHz glitches @ 100% rate)
   - **RO2:** 368.5 MHz (can detect up to 185 MHz glitches @ 100% rate)
   - **Detection limit:** ~50% of RO frequency (Nyquist-like constraint)

3. **Experimental Setup:**
   - **Platform:** Xilinx Virtex-5 FPGA (Spartan-3A for glitch generation)
   - **Protected circuit:** AES-128 implementation
   - **Glitch injection:** System clock frequency varied (18-50 MHz nominal, 90-250 MHz glitch)
   - **Test:** 10,000 glitch injections at 9th AES round

4. **Multi-Module Detection:**
   - **Single module:** Detection rate = p
   - **n modules:** Combined detection rate = 1 - (1-p)^n
   - **Example:** Two modules (373.3 MHz + 276.2 MHz ROs) → much higher detection than single 368.5 MHz RO
   - **Trade-off:** Area overhead vs detection rate

5. **Overhead Results:**

   | Configuration | Slice Registers | Slice LUTs | LUT FFs | Area (ASIC 45nm) |
   |---------------|-----------------|------------|---------|------------------|
   | Unprotected AES | Baseline (100%) | Baseline | Baseline | Baseline |
   | +1 detection module | +7.9% | +7.1% | +4.6% | +4.63% |
   | +2 detection modules | +15.9% | +11.4% | +10.7% | +7.62% |
   | +3 detection modules | +23.8% | +15.7% | +16.8% | +11.56% |

### Relevance to Our Project: ⭐⭐⭐⭐ (Very High)

**Why It Matters:**

1. **Same Detection Philosophy:**
   - Paper: Reference clock (RO) vs system clock
   - **Our approach:** Reference model (nominal boots) vs current boot
   - **Both use cross-checking for anomaly detection**

2. **Hardware vs Software Detection:**

   | Aspect | RO Detector (Paper) | PMU Detector (Ours) |
   |--------|---------------------|---------------------|
   | Detection speed | Real-time (cycles) | Per-checkpoint (milliseconds) |
   | Implementation | Hardware (RO circuit) | Software (CUSUM algorithm) |
   | Platform | FPGA-specific | ARM-universal |
   | Overhead | 4.63% area | 8% runtime |
   | Glitch coverage | Clock only | Clock + voltage |

3. **Detection Rate Improvement:**
   - Paper's formula: 1 - (1-p)^n for n modules
   - **Our equivalent:** Multiple checkpoints act as multiple detectors
   - With 4 checkpoints (CP0-CP3), each with 99% detection:
     - Combined: 1 - (0.01)^4 = 99.99999999% (virtually certain)
   - **Advantage:** "Free" multi-module detection (checkpoints already needed for boot stages)

4. **Threshold Calibration:**
   - Paper: RO frequency determines detection limit (~50% of RO freq)
   - **Our approach:** CUSUM threshold (H_99, H_999) determines detection sensitivity
   - **Similarity:** Both require calibration phase (RO freq selection vs model fitting)

**Direct Applications:**

1. **Hybrid Hardware + Software Detector:**
   
   **Future Architecture (ASIC implementation):**
   ```
   Layer 1 (Hardware): RO-based glitch detector (Paper 19)
       ↓ (If glitch detected → immediate alarm)
   Layer 2 (Firmware): PMU-based CUSUM (our approach)
       ↓ (If timing anomaly → alarm + forensics)
   Defense-in-depth: Two independent detectors
   ```

2. **Multi-Checkpoint Detection Rate:**
   - **Calculate combined detection:**
   ```python
   # Single checkpoint: 99% detection (0.01 false negative)
   p_single = 0.99
   n_checkpoints = 4
   p_combined = 1 - (1 - p_single)**n_checkpoints
   # p_combined = 0.99999999 (eight nines!)
   ```
   **Implication:** Multi-checkpoint approach gives near-perfect detection

3. **Overhead Comparison:**
   - **Paper's RO:** 4.63% area (1 module), 7.62% (2 modules)
   - **Our PMU:** 8% runtime (no area overhead - PMU already present)
   - **Trade-off:** Real-time detection (RO) vs zero-area detection (PMU)

4. **Detection Limit Analysis:**
   - Paper's RO1: Detects up to 207 MHz glitches (@ 414 MHz RO freq)
   - **Our bootrom:** Runs at 50 MHz
   - **Question:** What glitch frequency does PMU detect?
   - **Answer:** Any glitch causing timing shift (no frequency limit, only magnitude threshold)

**Cross-Checking Validation:**

Paper's cross-checking concept validates our approach:
- **Reference (nominal):** Expected behavior under no attack
- **Current (observed):** Actual behavior (may be under attack)
- **Comparison:** Statistical divergence → alarm

**Our CUSUM is a statistical cross-checker:**
- Reference: μ (mean of nominal distribution)
- Current: x_t (current checkpoint measurement)
- Comparison: Mahalanobis distance(x_t, μ) > threshold

---

## Paper 20: The Forgotten Threat of Voltage Glitching - A Case Study on Nvidia Tegra X2 SoCs (2021)

### Summary
Demonstrates voltage fault injection attack on Nvidia Tegra X2 SoC (used in Tesla autopilot, Mercedes infotainment) to bypass entire boot security. Uncovers hidden UART bootloader (manufacturer testing mode, disabled by fuses). Uses VFI to re-enable hidden bootloader, gaining highest-privilege code execution. Extracts bootloader firmware and decryption keys for later boot stages. Shows that simple voltage glitching (known since 2000s) still effective against modern SoCs in 2021.

### Key Contributions

1. **Target System:**
   - **SoC:** Nvidia Tegra X2 ("Parker" codename)
   - **Applications:** Tesla autopilot (DRIVE PX), Mercedes infotainment, Hyundai systems
   - **Security:** Boot ROM acts as Root of Trust (RoT), enforces authenticated code execution
   - **Hidden feature:** UART bootloader (factory test mode, production units have fuses blown to disable)

2. **Attack Overview:**
   - **Goal:** Enable hidden UART bootloader via VFI
   - **Method:** Voltage glitch during fuse read operation
   - **Effect:** Fuse read returns "disabled" (0) instead of "enabled" (1)
   - **Result:** UART bootloader activates, allows arbitrary code execution with max privileges
   - **Time to exploit:** Few seconds (fast enough for every boot)

3. **Attack Outcomes:**
   - **Boot ROM extraction:** Full code dump (iROM)
   - **Key material extraction:** Fuses and registers with cryptographic keys
   - **Second-stage bootloader decryption:** Used recovered keys to decrypt MB1
   - **Persistent exploit:** Hardware implant can re-enable bootloader on every boot

4. **Key Findings:**
   - **"Forgotten" threat:** VFI known since early 2000s (smartcards), but modern SoCs still vulnerable
   - **No countermeasures:** Tegra X2 lacks voltage monitoring, redundant checks, or fail-safe mechanisms
   - **Successor hardened:** Nvidia confirmed X2 successor (Mariko/X1+) has FI mitigations
   - **Widespread impact:** Multiple automotive manufacturers affected

5. **Proposed Mitigations:**

   **Board-Level (Existing SoCs):**
   - Heat-resistant epoxy (physical access denial)
   - Metal shielding (prevent decoupling capacitor removal)
   - PCB-embedded capacitors (harder to bypass)

   **Hardware-Level (Future SoCs):**
   - **Voltage monitoring circuits:** Detect glitch → raise interrupt → fault handler
   - **Cross-domain monitoring:** Independent voltage rails monitor each other (Nvidia patent [46])
   - **Integrated voltage regulators:** Eliminate external attack surface
   - **Clock source switching:** Use internal clock for sensitive operations

   **Software-Level:**
   - **Constants with large Hamming distance:** Hard to flip valid value to another
   - **Double-checks:** Redundant condition checks
   - **Loop integrity checks:** Verify loop exits correctly
   - **Global counter:** Monitor program flow, detect anomalies

### Relevance to Our Project: ⭐⭐⭐⭐⭐ (CRITICAL)

**Why It's Critical:**

1. **Same Threat, 20 Years Later:**
   - VFI effective on smartcards (2000s) → still effective on modern SoCs (2021)
   - **Implication:** Our bootrom (designed 2026) must NOT assume VFI is "old" threat
   - **Lesson:** Basic attacks persist if not properly defended against

2. **Boot Security is Primary Target:**
   - Paper: Attack boot ROM to compromise RoT
   - **Our project:** Defend boot ROM against same attack
   - **Exact use case alignment**

3. **Hidden Features = Hidden Vulnerabilities:**
   - Tegra X2: Hidden UART bootloader (intended for manufacturer only)
   - **Our bootrom:** Do we have debug/test modes disabled by fuses/config?
   - **Action:** Audit bootrom for hidden features (even in QEMU)

4. **Fuse Read Glitch:**
   - **Attack mechanism:** Glitch during fuse/config read
   - **Our equivalent:** Glitch during `boot_decision` read
   ```c
   // Our bootrom (main.c line 277-280):
   volatile uint32_t boot_decision = 0;  // Fuse equivalent
   if (dummy_hash == expected_hash) {
       boot_decision = 1;  // "Enabled" fuse
   }
   // Glitch this read:
   if (boot_decision == 1) { /* boot */ }
   // Attack: Glitch causes read to return 1 even when 0
   ```

**Direct Applications:**

1. **Critical Vulnerability Check:**
   
   **Audit our bootrom for "fuse-like" config:**
   ```bash
   grep -r "volatile" pmu_bootrom/src/main.c
   # Check for configuration variables read before boot decision
   ```
   
   **Our findings:**
   ```c
   volatile uint32_t boot_decision = 0;     // Line 277 - CRITICAL
   volatile uint32_t glitch_ctr = 0;        // Line 229 - Attack simulation
   volatile uint32_t dummy_hash = 0;        // Line 233 - Signature accumulator
   ```
   
   **Risk:** All `volatile` variables are glitch targets!

2. **Software Mitigations from Paper:**
   
   **Apply to our bootrom immediately:**
   
   a) **Large Hamming Distance Constants:**
   ```c
   // Before (vulnerable):
   #define BOOT_ALLOWED 1
   #define BOOT_DENIED  0
   
   // After (hardened):
   #define BOOT_ALLOWED 0xDEADBEEF  // Hamming dist = 24 bits from 0
   #define BOOT_DENIED  0x12345678  // Hamming dist = 20 bits from ALLOWED
   
   volatile uint32_t boot_decision = BOOT_DENIED;
   if (dummy_hash == expected_hash) boot_decision = BOOT_ALLOWED;
   if (boot_decision == BOOT_ALLOWED) { /* boot */ }
   ```
   
   b) **Double-Check (Anti-Pattern A7 mitigation):**
   ```c
   // Redundant signature verification:
   uint32_t check1 = (dummy_hash == expected_hash);
   uint32_t check2 = (dummy_hash == expected_hash);
   uint32_t check3 = (check1 == check2);
   if (check1 && check2 && check3) {
       boot_decision = BOOT_ALLOWED;
   }
   ```
   
   c) **Loop Integrity Check:**
   ```c
   // In signature verification loop:
   uint32_t loop_counter = 0;
   for (uint32_t i = 0; i < sig_iterations; i++) {
       loop_counter++;
       dummy_hash ^= fake_signature[i % 16];
   }
   // Verify loop completed:
   if (loop_counter != sig_iterations) {
       halt();  // Loop was glitched
   }
   ```
   
   d) **Global Counter (Program Flow Monitoring):**
   ```c
   volatile uint32_t flow_counter = 0;
   #define EXPECT_FLOW(expected) \
       if (flow_counter != (expected)) halt()
   
   void main(void) {
       flow_counter++;  // 1
       stage_rom_check(0);
       EXPECT_FLOW(1);
       
       flow_counter++;  // 2
       stage_memory_init(1);
       EXPECT_FLOW(2);
       
       flow_counter++;  // 3
       stage_signature_verify(2);
       EXPECT_FLOW(3);  // Detects if stage_signature_verify skipped
       
       flow_counter++;  // 4
       stage_key_derivation(3);
       EXPECT_FLOW(4);
   }
   ```

3. **Hardware Implant Threat:**
   - Paper: Attacker can persist VFI via hardware implant (Nintendo Switch example)
   - **Our Phase 2:** Assume attacker has persistent access
   - **Implication:** Single boot test insufficient, need repeated attacks (1000s of boots)

4. **Voltage Monitoring (Future Work):**
   - Paper proposes: Cross-domain voltage monitor (Nvidia patent)
   - **Our hybrid approach:** PMU software detector + voltage monitor hardware
   - **Proposal for Phase 3:** Partner with ARM to add voltage monitor to Cortex-M34?

5. **Mariko Countermeasures Study:**
   - Paper mentions: Nvidia X1+ "Mariko" has FI protections
   - **Action:** Find Mariko source code (paper says it leaked)
   - **Study:** What specific countermeasures did Nvidia implement?
   - **Adopt:** Apply same techniques to our bootrom

**Critical Quote:**
> "The fact that such simple attacks are still possible, 20 years after smartcards have been hardened against FI, suggests that chip manufacturers seem to have ignored this threat." (Introduction)

**Our mission:** DON'T ignore this threat. Implement state-of-art defenses NOW (2026).

**Threat Model Validation:**

Paper proves:
- ✅ VFI attacks are **practical** (not theoretical)
- ✅ Automotive safety-critical systems **are targeted** (Tesla, Mercedes)
- ✅ Boot security **is primary target** (same as our project)
- ✅ Mitigation is **essential** (Nvidia added protections in next gen)

**Our detector is part of the solution:** PMU-based detection + software hardening + (future) voltage monitoring.

---

## Cross-Paper Synthesis: Papers 14-20

### Theme 1: Theoretical Foundation Converges

| Paper | Root Cause Analysis | Key Mechanism |
|-------|---------------------|---------------|
| 14 (PlayStation) | CMOS transistor timing | Propagation delay increase |
| 15 (Microarch) | Binary encoding faults | Partial instruction update |
| 16 (PLL) | Setup/hold violations | Sustained overclocking |
| 17 (AVR) | Pipeline effects | Fetch/execute overlap |
| 18 (Arbitrary) | Rising/falling edges | Multiple edge opportunities |
| 19 (RO Detection) | Clock divergence | System vs reference comparison |
| 20 (Tegra X2) | Fuse read manipulation | Voltage drop during critical read |

**Convergence:** All papers agree root cause is **timing violations** at gate/instruction level.

**Implication:** Our PMU timing-based detector targets the RIGHT phenomenon.

### Theme 2: Attack Sophistication Escalates

| Year | Attack Complexity | Equipment Cost | Success Rate |
|------|-------------------|----------------|--------------|
| 2014 (P17 - AVR) | Manual parameter tuning | <$1000 | Moderate (days of search) |
| 2016 (P19 - RO) | Automated injection + detection | <$3000 | ~100% (with RO) |
| 2019 (P14 - Vita, P18 - Arbitrary) | Overnight automated sweep, >1M glitches | <$3000 | >80% reproducibility |
| 2021 (P20 - Tegra) | Hardware implant (persistent) | <$5000 | Few seconds per boot |

**Trend:** Attacks become more automated, persistent, and sophisticated over time.

**Implication:** Our 2026 detector must defend against state-of-art (2021+) attacks.

### Theme 3: PLL Not a Silver Bullet

| Paper | PLL Status | Attack Feasibility |
|-------|------------|-------------------|
| 16 (Peak Clock) | PLL present | **Vulnerable** (just need longer glitch) |
| 17 (AVR) | No PLL | Vulnerable |
| 20 (Tegra X2) | PLL present | **Vulnerable** (no VFI mitigations) |

**Key insight:** PLL complicates attacks but doesn't eliminate them.

**Our Phase 2:** Must test with PLL enabled (realistic scenario).

### Theme 4: Software Countermeasures Emerge

Papers 15, 20 both recommend software-level defenses:

| Countermeasure | Paper 15 | Paper 20 | Our Bootrom Status |
|----------------|----------|----------|-------------------|
| Large Hamming distance constants | ✅ | ✅ | ❌ Not implemented |
| Redundant checks | - | ✅ | ❌ **A7 violation** |
| Loop integrity checks | - | ✅ | ❌ Not implemented |
| Global flow counter | - | ✅ | ❌ Not implemented |
| Constant-time code | ✅ | - | ⚠️ Partial (variable loop) |

**Action items:** Implement ALL software countermeasures (low-cost, high-impact).

### Theme 5: Detection Approaches Compared

| Approach | Papers | Detection Speed | Platform | Overhead |
|----------|--------|-----------------|----------|----------|
| **Hardware sensors** | 19 (RO), 11 (FTC) | Real-time (cycles) | FPGA/ASIC | 4-7% area |
| **Software detection** | **Our PMU** | Per-checkpoint (ms) | **Any ARM** | **8% runtime** |
| **Software hardening** | 15, 20 | N/A (prevention) | Any | 10-50% code size |

**Our competitive position:**
- Not as fast as hardware (but acceptable for boot process)
- Universal platform (vs hardware-specific)
- Low overhead (vs software redundancy)

---

## Critical Findings: Papers 14-20

### Finding 1: Boot ROM is #1 Target (Papers 14, 20)

**PlayStation Vita (P14):** Glitch boot ROM → dump firmware
**Nvidia Tegra (P20):** Glitch boot ROM → enable hidden bootloader

**Our project directly addresses THE primary attack vector.**

### Finding 2: Software Mitigations Work (Papers 15, 20)

Both papers recommend similar defenses:
- Large Hamming distance
- Redundant checks
- Flow monitoring

**Action:** Implement these in our bootrom (Phase 1 immediate work).

### Finding 3: Multi-Layer Defense Essential (All Papers)

No single defense is perfect:
- Hardware sensors (P11, P19): Fast but platform-specific
- Software hardening (P15, P20): General but overhead
- **Our PMU + software hardening:** Best of both worlds

### Finding 4: PLL Doesn't Eliminate Glitching (P16)

**Myth debunked:** PLL protects against clock glitches
**Reality:** Longer glitch durations still effective

**Our Phase 2:** Must characterize PLL behavior (if present in Cortex-M33).

### Finding 5: Partial Update Faults Exist (P15)

**Beyond instruction skip:** Instruction corruption via partial update
**Implication:** Wider range of timing shifts than simple skip
**Validation needed:** Does our Gaussian model capture this?

---

## Immediate Action Items (Based on Papers 14-20)

### Priority 1: Software Hardening (Paper 20 recommendations)

```c
// Implement ALL four mitigations:
// 1. Large Hamming distance
#define BOOT_ALLOWED 0xDEADBEEF
#define BOOT_DENIED  0x12345678

// 2. Redundant checks
uint32_t check1 = verify_signature();
uint32_t check2 = verify_signature();
if (check1 && check2 && (check1 == check2)) { /* boot */ }

// 3. Loop integrity
uint32_t loop_ctr = 0;
for (...) { loop_ctr++; /* work */ }
if (loop_ctr != expected) halt();

// 4. Global flow counter
volatile uint32_t flow = 0;
#define EXPECT(n) if (flow != n) halt()
// Increment at each stage, check before boot
```

**Estimated effort:** 1-2 days
**Impact:** Force multi-glitch attack (exponentially harder)

### Priority 2: Partial Update Model Testing (Paper 15)

**Goal:** Verify CUSUM detects instruction corruption (not just skip)

```python
# In cusum_detector.py, add new attack simulation:
def inject_partial_update_fault(X_nom, corruption_bits=4):
    """Simulate partial update from precharge (0xFF)"""
    X_attack = X_nom.copy()
    # Corrupt immediate value in comparison (simulate precharge)
    # Effect: cycle count increases (wrong branch taken)
    X_attack[:, 2] += np.random.randint(50, 200, size=len(X_attack))
    return X_attack

# Test CUSUM detection rate on partial update faults
```

**Estimated effort:** 0.5 days
**Impact:** Validate robustness to broader fault model

### Priority 3: PLL Characterization (Paper 16)

**Goal:** Determine if QEMU/hardware has PLL, characterize response

```bash
# Check Cortex-M33 TRM for PLL
grep -i "PLL\|phase" docs/cortex-m33-trm.pdf

# If PLL present, measure response in QEMU:
# Inject high-frequency clock, measure SysTick behavior
```

**Estimated effort:** 1 day
**Impact:** Accurate Phase 2 glitch parameter ranges

### Priority 4: Hidden Feature Audit (Paper 20)

**Goal:** Ensure no hidden debug/test modes in bootrom

```bash
# Audit for:
# - Conditional compilation flags
# - Debug UARTs
# - Test modes enabled by magic values
grep -r "#ifdef\|#if\|DEBUG\|TEST" pmu_bootrom/src/
```

**Estimated effort:** 0.5 days
**Impact:** Eliminate "hidden bootloader" risk

---

## Recommendations for Phase 2 (Based on Papers 14-20)

### Test Matrix (Comprehensive Validation)

| Parameter | Values to Test | Reason |
|-----------|----------------|--------|
| **Glitch duration** | 10 ns - 200 μs | P16: PLL needs longer glitch |
| **Glitch waveform** | Square, V-shape, arbitrary | P18: Waveform affects success |
| **Glitch offset** | 0-100% of cycle | P9: Quadrant matters |
| **Target checkpoint** | CP0, CP1, CP2, CP3 | All stages potentially vulnerable |
| **Repeated attacks** | 1000+ boots | P20: Persistent implant scenario |
| **PLL enabled** | Yes/No | P16: PLL changes parameters |

**Total tests:** 6 durations × 3 waveforms × 10 offsets × 4 checkpoints × 1000 boots = 720,000 glitches

**Duration estimate:** 720k × 100 μs/glitch = 72,000 seconds = **20 hours** (automated)

### Validation Criteria

**Our detector must:**
1. ✅ Detect >99% of successful glitches (F < 1%)
2. ✅ Maintain <1% false alarm rate
3. ✅ Work with PLL enabled
4. ✅ Detect all waveform types
5. ✅ Remain effective over 1000+ repeated attacks

### Comparison Benchmark (Paper 19 as baseline)

| Metric | RO Detector (P19) | Our PMU Detector | Target |
|--------|-------------------|------------------|--------|
| Detection rate | ~100% (up to 207 MHz) | Measure | >99% |
| False alarm | Not reported | Measure | <1% |
| Latency | Real-time (cycles) | ~2000 cycles | Acceptable for boot |
| Overhead | 4.63% area | 8% runtime | <10% |

---

## Future Work: Hybrid Architecture (Papers 11, 19, 20)

**Optimal Defense-in-Depth (for ASIC implementation):**

```
Layer 1 (Hardware): Voltage monitor + RO clock reference
    ↓ (Real-time detection, immediate halt)
Layer 2 (Firmware): PMU-based CUSUM (our approach)
    ↓ (Per-checkpoint detection, forensic analysis)
Layer 3 (Software): Redundant checks + flow monitoring (P20 mitigations)
    ↓ (Force multi-glitch attack, exponential difficulty)
```

**Benefits:**
- **Layer 1:** Catches most attacks (hardware speed)
- **Layer 2:** Catches attacks that bypass Layer 1 (statistical robustness)
- **Layer 3:** Makes attacks exponentially harder (redundancy)

**Overhead:**
- Layer 1: ~5% area (P19 result)
- Layer 2: ~8% runtime (our estimate)
- Layer 3: ~20% code size (P20 estimate)
- **Total:** Acceptable for security-critical applications

---

## Conclusion: Papers 14-20

These 7 papers provide **practical validation** and **theoretical depth**:

### Most Important Findings:

1. **Paper 20 (Tegra X2)** ⭐⭐⭐⭐⭐
   - Proves VFI threat is **real and current** (2021)
   - Provides **actionable software mitigations** we must implement
   - Same use case (boot ROM attack)

2. **Paper 15 (Microarch Insights)** ⭐⭐⭐⭐
   - Explains **partial update faults** (beyond simple skip)
   - Our detector must handle **wider fault model**

3. **Paper 16 (PLL)** ⭐⭐⭐⭐
   - Debunks PLL protection myth
   - Guides Phase 2 parameter selection (longer glitches)

4. **Paper 19 (RO Detection)** ⭐⭐⭐⭐
   - Validates cross-checking approach
   - Provides **overhead benchmark** (4.63% vs our 8%)

### Critical Actions:

1. **Immediate (Phase 1):**
   - ✅ Implement Paper 20's software mitigations (1-2 days)
   - ✅ Test partial update fault model (0.5 days)
   - ✅ Audit for hidden features (0.5 days)

2. **Phase 2:**
   - ✅ Comprehensive glitch parameter sweep (20 hours automated)
   - ✅ PLL characterization (if present)
   - ✅ Waveform diversity testing

3. **Future (Phase 3):**
   - ✅ Hybrid hardware + software detector (if moving to ASIC)
   - ✅ Voltage monitor integration
   - ✅ Partnership with ARM for hardened Cortex-M design

### Key Validation:

Papers 14-20 **prove our project is essential:**
- Boot ROM attacks are **prevalent** (P14, P20)
- Simple defenses are **insufficient** (P20: Tegra had none)
- Multi-layer defense is **necessary** (all papers)
- **Our PMU detector fills critical gap** (universal, low-overhead, effective)

**Next Milestone:** Implement Paper 20's mitigations, then proceed to Phase 2 hardware validation.
