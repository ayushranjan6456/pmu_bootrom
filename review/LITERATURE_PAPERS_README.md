# The 20 papers behind the literature survey

A short note on each paper, in the same order (P1 to P20) as the backup slide `figures/backupB8_literature_references.png`. Authors, years and venues come from each paper's PDF in `Literature_Survey/papers/`. Numbers were checked against the PDFs; a few survey claims could not be confirmed and are left out (see the last section). The four papers on the literature slide (slide 3) are marked **[slide 3]**.

**Groups:** hardware sensors (P2, P11, P19) | software and algorithm defences (P5, P6) | how faults behave (P3, P7, P9, P15, P16, P17) | attacks on real boot code (P10, P14, P18, P20) | attack tooling (P12, P13) | background and reviews (P1, P4, P8).

---

**P1. Kazemi et al. (2020), Electronics.** A review of the equipment used to inject faults (clock and voltage glitchers, laser, EM) and how to configure it when testing microcontroller-based IoT devices. Background reading: it gives the vocabulary and the landscape, with no detection numbers.

**P2. He et al. (2017), ASP-DAC. [slide 3]** A hardware sensor built from a phase-locked loop (PLL) that watches for the disturbance a laser or EM fault causes, tested on FPGAs. The paper reports about 92.82% detection and a 0.94% "failure rate" for laser injection (quoted from the group's earlier 2016 paper), and the sensor triggers at 64% laser power while faults need 91%. It needs extra circuitry on the chip, so it cannot be added by a firmware update.

**P3. Dadjou (2013), M.A.Sc. thesis, University of Waterloo.** Builds an FPGA test bench with an on-chip clock-glitch generator to study which glitches cause exploitable faults, using AES as the example. Explains how a shortened clock cycle produces wrong values, which is the physical idea behind our simulated skip.

**P4. Kaur, Singh, Kaur (2020), Indo-Taiwan ICAN.** A review of side-channel attacks, glitch attacks and fault injection, with their countermeasures. Background only; no new method or measurements to quote.

**P5. Lee et al. (2025), Sensors. [slide 3]** Shows that clock glitches on a neural network running on an STM32F303 (Cortex-M4) cause wrong classifications, then adds algorithm-level checks to the Softmax and Sigmoid functions. The checks detect faults with a probability of up to 92.56%. They protect one function at a time, which is the limit shown on slide 3.

**P6. Geier et al. (2023), ASP-DAC. [slide 3]** CompaSeC: a compiler adds control-flow signature checks and runs critical operations twice, for RISC-V secure boot. The paper reports that it closes the instruction-skip attack for single to quadruple skips in the studied boot program. Runtime overhead is 0.21% if only the vulnerable functions are hardened, and 484% for full coverage; code size (ROM) still grows by 145% (selective) or 466% (full). It prevents attacks rather than detecting them.

**P7. Malik, Mihir, Aysu (2025), arXiv.** CRAFT: injects faults into a RISC-V core (CV32E40X) at the gate level, before silicon, and traces why they happen. Some glitches silently corrupt data without any exception flag, so exception handlers would miss them. Our testbed is QEMU, not a gate-level model, so this paper supports the idea of pre-silicon testing, not our setup.

**P8. Abbaspour et al. (2016), Procedia Computer Science.** Detects fault-data injection into a drone's sensors with an adaptive neural network tuned by a Kalman filter, shown in simulation. It is a different domain (sensor data, not instructions), cited only as an example of learning normal behaviour and flagging deviations.

**P9. Esmaeilian, Beitollahi (2024), Microprocessors and Microsystems.** A platform for testing how C functions behave under clock glitches on a RISC-V processor; it generates and injects 14,878 different faults. Useful for how to sweep glitch parameters systematically.

**P10. Van den Herrewegen et al. (2021), IACR TCHES.** Attacks the bootloaders of three real microcontrollers (NXP LPC, STM8, Renesas 78K0) by combining binary analysis with voltage glitching using inexpensive, open-design equipment. Includes the first fully documented multi-glitch attack on the STM8, and a list of bootloader anti-patterns, including A7 (a non-redundant check). Our stub has exactly one signature check, so it has A7.

**P11. Muttaki et al. (2022), IEEE HOST. [slide 3]** FTC: one on-chip sensor, a 64-stage delay line, designed to turn any kind of fault (clock, voltage, laser, optical, EM) into a timing change it can measure. The paper tested only EM, voltage and clock glitches; laser and optical are listed as future work. About 0.4% of the FPGA. It shares our idea that faults show up as timing, but it is hardware.

**P12. Obermaier, Specht, Sigl (2017), Applied Electronics.** "Fuzzy glitch": mixes two ring oscillators to make a random, high-frequency clock glitch instead of one precise pulse. On an STM32F030 (Cortex-M0) it succeeds in about 75% of attacks with glitch widths of 180 to 310 ns. Shows that an attacker does not need precise timing.

**P13. Hsiao et al. (2026), arXiv.** Voltage-glitches the fail-safe logic of a drone flight controller, using the ARMORY simulator and a ChipWhisperer. Out of 26,976 simulated faults, 1,363 gave exploitable outcomes. Shows that simulation can point to the vulnerable cycles before hardware testing.

**P14. Lu (2019), arXiv.** Explains how a voltage glitch causes timing violations in CMOS, then uses it on the PlayStation Vita to get code execution and dump the secure boot ROM. With the board untouched, the same glitch settings reproduce the fault more than 80% of the time. A real attack on a boot ROM, which is the case we defend.

**P15. Alshaer et al. (2023), CARDIS.** Proposes "partial update" fault models: a clock glitch can leave an instruction half-fetched, so it executes with wrong bits instead of being skipped. Used on an Arm Cortex-M4 to change the program counter and break control flow. Faults are wider than "skip one instruction", which our testbed does not cover.

**P16. Selmke, Hauschild, Obermaier (2019), ASHES.** Shows that a PLL does not protect against clock glitches: manipulating the external clock still reaches the internal one. Tested on two Arm Cortex-M microcontrollers and used to mount a differential fault attack on AES.

**P17. Gomes da Silva (2014), B.Sc. thesis, TU Berlin.** Builds a glitching setup for AVR microcontrollers and finds that clock glitches can skip or corrupt instructions and make code exit loops. Exiting a loop early is the effect our simulated fault copies.

**P18. Bozzato, Focardi, Palmarini (2019), IACR TCHES.** Voltage glitching with arbitrary waveforms from low-cost equipment, used for firmware-extraction attacks on six microcontrollers from ST, TI and Renesas. The hardest attacks inject over one million glitches. Shows that attackers will run long, automated campaigns.

**P19. Luo, Luo, Fei (2016), preprint (venue not stated in the PDF).** A hardware detector that cross-checks the system clock against the power supply to spot clock glitches, built on a Virtex-5 FPGA. For AES with one detection module it costs 7.9% more registers and 7.1% more LUTs, or 4.63% more area on an ASIC. Hardware-only and clock-only.

**P20. Bittner et al. (2021), FDTC.** Shows that voltage glitching defeats the entire boot security of the Nvidia Tegra X2 SoC, a chip used in Tesla's autopilot and Mercedes-Benz's infotainment. Evidence that this attack matters on commercial products, not only on lab boards.

---

## Careful when quoting

- **Survey author names are wrong.** `COMPREHENSIVE_LITERATURE_SURVEY.md` Section 8 lists the wrong authors for most papers (for example P5 as Kiyomoto, P6 as Kiaei, P9 as Ghalaty, P20 as Yuce) and "Conference/Journal TBD" almost everywhere. The names above are from the PDFs.
- **P2, 0.94%:** the paper calls it a "failure rate". The survey calls it a "false alarm" rate. Say "failure rate".
- **P6:** the "10 anti-patterns" in the survey belong to P10, not P6 (the CompaSeC PDF never uses the word). The "zero attacks" result is for single to quadruple skips in the studied boot program, not all faults.
- **P7:** the survey says QEMU results matched FPGA results. The PDF never mentions QEMU; it uses a gate-level netlist and an FPGA.
- **P15:** the PDF says "a 32-bit microcontroller with an Arm Cortex-M4"; it never names an STM32F407. `LITERATURE_SLIDES.md` (backup slide) says STM32F407 and "register corruption"; the paper's model is partial update of the instruction encoding. Fix the wording or check the PDF.
- **P18:** the survey's "about 50% fewer glitches" was not found in the PDF, so it is not used.
- **P20:** the paper shows the SoC's boot security can be bypassed. The cars (Tesla, Mercedes-Benz, Hyundai) are named as users of this chip family, not as attacked vehicles.
- **Left out because unconfirmed:** the survey's glitch-cycle ranges for P9 and P13, the PLL success rates for P16, the instruction-sensitivity ranking attributed to P16, and the ISO 26262 and countermeasure list attributed to P20.
