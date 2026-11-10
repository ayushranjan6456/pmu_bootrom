# Literature Review Slides

**Audience:** IIT Madras Phase 1 panel (faculty reviewers)  
**Duration:** 5–6 minutes for three literature slides plus one backup  
**Date:** 2026-11-10

---

## Author notes (do not share or present)

Before using these slides, be aware of issues in `COMPREHENSIVE_LITERATURE_SURVEY.md`:

- **Reference list (Section 8):** Author names are wrong for most of the 20 papers. The correct names (from `papers_list.csv`) are used in these slides.
- **Missing papers:**
  - Paper 19 (Luo, Luo, Fei 2016) is a ring-oscillator clock-glitch detector, directly relevant prior work. The survey says "details incomplete".
  - Paper 4 (Kaur et al. 2020) is a general review with no detection numbers (background only).
- **Numbers to verify before presenting:**
  - Paper 9: use cycles 5–12 (text supports 5–12, not 5–20)
  - Paper 18: "50% fewer glitches" was not found in summaries
  - Paper 15: the 50/10/30/10% fault split isn't in it (comes from other work)
  - The "10 anti-patterns" belong to Paper 10, not Paper 6
- **Pre-implementation estimates to drop:** "99% detection at 1% false alarm", "about 8% overhead", "about 2000 cycles"

**Recommendation:** Spot-check numbers against PDFs before final deck. The citation-check agent verified against your own summary files, not the PDF text.

---

## Slide L1 — Why the boot ROM is the target

**Title:** Boot ROM Under Attack: Real-World Evidence

**Content:**

Boot-time security checks are successfully attacked on commercial devices:

- **PlayStation Vita** boot ROM: voltage glitching, >80% reproducible success (Lu 2019)
- **Automotive systems**: Nvidia Tegra X2 secure boot bypassed in Tesla, Mercedes-Benz, and Hyundai vehicles (Bittner et al., FDTC 2021)
- **Industrial microcontrollers**: NXP LPC, STM8, and Renesas 78K0 bootloaders (Van den Herrewegen et al., TCHES 2021)
- **Scale of attacks**: campaigns of over one million glitches on six microcontrollers from three manufacturers (Bozzato et al., TCHES 2019)

**The vulnerability:** A non-redundant check (what Van den Herrewegen et al. call **anti-pattern A7**) is a single point of failure — one glitch can bypass it.

**Honest note for panel:** Our Phase 1 stub has exactly one signature check, so it has this weakness too. Redundant checks are complementary and planned for Phase 2.

**Speaker notes (≈1.5 min):**
- Emphasize that these are real attacks on deployed systems, not lab demonstrations
- The cost of an attack here is low, and the damage is code execution at the root of trust
- Set up the need for detection mechanisms

---

## Slide L2 — How the literature defends, and the trade-offs

**Title:** Defence Landscape: Hardware vs Software Trade-offs

**Content:**

| Approach | Example | Reported Result | Limit |
|----------|---------|-----------------|-------|
| **Hardware sensors** | Ring-oscillator/PLL sensor (He et al., ASP-DAC 2017) | 92.82% detection, Virtex-5 FPGA | Needs FPGA/ASIC primitives |
| | Fault-to-time converter (Muttaki et al., HOST 2022) | 64-stage delay line; 0.4% LUTs on Zynq; covers glitch, laser, optical, EM | Silicon area; per-platform calibration |
| | Clock-glitch detector (Luo et al., 2016) | 7.9% registers / 7.1% LUTs on FPGA; 4.63% area on ASIC | Hardware only, clock only |
| **Software redundancy** | CompaSeC (Geier et al., ICCAD 2023) | No remaining successful attacks; 0.21% (selective) to 484% (full) overhead | Prevents rather than detects; RISC-V compiler |
| **Algorithm-level checks** | Loop and inverse-function checks (Lee et al., Sensors 2025) | 92.56% detection on STM32F303 | Per function |
| **This project** | Statistical timing detector in boot ROM | See slide L3 | Platform and fault limits on L3 |

**Key pattern:** Hardware sensors are fast but need silicon; software methods are portable but narrow or costly.

**Important:** Do not put our detection rates in this table. The papers' numbers come from FPGA and real chips with different faults; ours come from QEMU with one simulated fault. They aren't comparable, and the panel will notice.

**Note:** Check whether He et al.'s 0.94% is false alarms or failure rate before quoting it.

**Speaker notes (≈2 min):**
- Point at the trade-off, not the absolute numbers
- Each approach solves a different slice of the problem
- Hardware sensors: excellent detection but require chip-level integration
- Software redundancy: portable but can be expensive or narrowly scoped
- Our approach aims for firmware-only deployment with statistical detection

---

## Slide L3 — The gap and our position

**Title:** Gap Analysis and Project Scope

**Gap identified (within the 20 papers surveyed; the firmware itself is a one-shot threshold, sequential accumulation is Phase 2):**
- No prior work uses **statistical detection** (CUSUM-style, sequential in the Python simulation, one-shot in the firmware) on **on-chip timing telemetry** inside a boot ROM, with an implementation small enough for ROM deployment

**Honesty note:**
- This novelty claim holds within the surveyed papers
- A systematic prior-art search (CUSUM, performance counters, glitch detection) has not been completed
- Web search was unavailable for this verification

**What is reused:**
- Mahalanobis distance and CUSUM are standard statistical techniques
- **Our contribution:** the application, calibration on real timing data, and fixed-point firmware port

**Delivered in Phase 1:**
- Python design → C firmware port
- Embedded detector: 3,152 bytes total firmware, 1,060 bytes detector code (measured via `arm-none-eabi-size`)
- Validation: 1,000 + 1,000 boots
  - 14/1,000 false alarms in the final run (1.4%); about 1% pooled over two runs (23/2,000)
  - 100% detection of large simulated fault (1,000/1,000)
  - Details in `STATUS.md`

**Not delivered (Phase 2 scope):**
- Performance-counter hardware (currently using SysTick)
- Multi-checkpoint fusion
- Formal statistical bounds
- Real fault injection (voltage/clock glitch)
- Firmware-based severity curve

**Speaker notes (≈1.5 min):**
- Be upfront about the honest scope — this leads naturally into Phase 2 planning
- Emphasize that the contribution is the application and implementation, not inventing new statistical methods
- Acknowledge the limitation: we haven't searched the wider literature systematically

---

## Backup Slide — Fault models in the literature vs ours

**Title:** Fault Model Coverage (Not Yet Tested)

**Beyond instruction skip:**
- **Partial-update faults**: Alshaer et al. (2023) on STM32F407 — register corruption without full skip
- **Silent corruption**: Malik et al. (CRAFT, arXiv 2025) — no exception raised, data silently wrong

**What we tested:**
- One skip-like fault (sub_b loop removal/reduction in signature verification)

**Honest assessment:**
- The survey's claim that timing detection "catches all fault types" is **not tested** in Phase 1
- Say "**not yet tested**", not "covered"
- This is future work for Phase 2

**Use for:** When the panel asks "What kinds of faults does this detect?"

---

## Likely Panel Questions on Literature

### Q1: "Is this novel?"
**A:** Within the 20 papers surveyed, yes — no prior work combines statistical detection (CUSUM-style) with on-chip timing telemetry in a boot ROM; our firmware is a one-shot threshold and sequential accumulation is Phase 2. However, the wider prior-art search (across CUSUM applications, PMU-based detection, formal bounds) is still to be done.

### Q2: "Why not use a hardware sensor?"
**A:** Silicon cost and platform-specific calibration. Hardware sensors (like ring oscillators) need FPGA/ASIC primitives and per-chip tuning. Our approach needs only a firmware update, trading off detection latency and generality for deployment flexibility.

### Q3: "How does it compare with CompaSeC?"
**A:** Different goal — CompaSeC (Geier et al.) prevents attacks via redundancy; we detect them via timing anomalies. Detection rates aren't comparable across platforms: they use RISC-V simulation with synthesized faults; we use ARM Cortex-M33 QEMU with one simulated fault.

### Q4: "Does QEMU predict hardware behavior?"
**A:** The survey's evidence for simulation validity is RTL, gate-level, and ARMORY simulation — not QEMU. Our own severity sweep found that QEMU's SysTick doesn't follow executed work (it tracks wall-clock time). That's why hardware counters (DWT) are deferred to Phase 2.

### Q5: "What about the 1% false alarms?"
**A:** The false alarms (14/1,000 in the final run, 1.4%; 23/2,000 pooled, about 1%) are attributed to probable QEMU host timing stalls — single or double sub-stage spikes inconsistent with the fault model. Phase 2 will use DWT cycle counters on STM32L552 hardware, which count executed instructions rather than wall-clock time. See `KNOWN_ISSUES.md` ISSUE-013.

---

## Citation Corrections for Slides

Use these correct author names (from `papers_list.csv`) when citing papers:

- **P1:** Kazemi et al., Electronics 2020
- **P2:** He, Breier, Bhasin, Miura, Nagata, ASP-DAC 2017
- **P3:** Dadjou thesis 2013
- **P5:** Lee, Kim, Hong, Ha, Sensors 2025
- **P6:** Geier, Auer, Mueller-Gritschneder, Sharif, Schlichtmann, ICCAD 2023
- **P7:** Malik, Mihir, Aysu (CRAFT), arXiv 2025
- **P10:** Van den Herrewegen, Oswald, Garcia, Temeiza, TCHES 2021
- **P11:** Muttaki, Zhang, Tehranipoor, Farahmandi, HOST 2022
- **P14:** Yifan Lu 2019
- **P15:** Alshaer, Colombier, Deleuze, Beroulle, Maistri 2023
- **P18:** Bozzato, Focardi, Palmarini, TCHES 2019
- **P19:** Luo, Luo, Fei 2016
- **P20:** Bittner, Krachenfels, Galauner, Seifert, FDTC 2021

---

## Next Steps

1. **Verify numbers against PDFs** before finalizing slides
2. **Integrate into `PPT_OUTLINE.md`** as slide 3 (or split into slides 3, 4, 5)
3. **Prepare speaker notes** with timing (≈5–6 min total)
4. **Add to Q&A backup** (`QA_BACKUP.md`) with expanded answers
5. **Consider adding figures:**
   - Table from L2 as a visual
   - Attack evidence timeline (Vita → Tesla → this work)
   - Gap positioning diagram (hardware ← our approach → software)
