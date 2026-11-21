# Stage 2: Moving the Detector into the Firmware

Study notes in plain language. Numbers come from [STATUS.md](../STATUS.md), [KNOWN_ISSUES.md](../KNOWN_ISSUES.md) and the frozen firmware at git tag `phase1-review-freeze-2`; if a number here differs from STATUS.md, STATUS.md wins.

**Period:** 7 to 10 Nov 2026 (commits 4b019e3 and 0d6aa44). **Code:** [src/cusum_detector.c](../src/cusum_detector.c) and `.h`, [scripts/calibrate_firmware.py](../scripts/calibrate_firmware.py).

---

## Why this stage existed

Stage 1 left a gap. The detector lived in Python and ran after the data was collected. A defence has to run inside the bootrom, during boot, and stop the boot itself (ISSUE-008). So we rewrote the detector in C.

## What was built

| File | Job |
|---|---|
| `src/cusum_detector.c` and `.h` | The detector in C |
| `scripts/calibrate_firmware.py` | Learns the numbers from clean boots and prints them as C code |
| `main.c` | Calls the detector after checkpoint 2 and stops the boot on alarm |

## Problem 1: the chip has no maths library

A bootrom has no floating-point unit, no `printf` and no maths library. We needed decimals using only whole numbers. The answer is **Q16.16 fixed point**.

- Store every number as a whole number counting in 1/65536ths.
- Example: 1.5 is stored as 98,304.
- The smallest step is 0.0000153, so tiny numbers lose a little accuracy. The matrix entry 0.001665 is stored as 109, which reads back as 0.001663.
- The range is about plus or minus 32,768.

## What the C code does for one boot

1. **Difference.** Subtract the average boot from the three timings.
2. **Multiply** by the inverse-covariance matrix (the "how they move together" information).
3. **Combine** into one number, the squared distance.
4. **Square root** to get the distance (MD).
5. **Compare** with the threshold `H`. If MD is higher, alarm.

A real example with the frozen firmware's numbers:

| Boot | Timings | MD | Result |
|---|---|---:|---|
| Clean | 700, 590, 505 | 0.17 | no alarm |
| Attack | 690, 88, 500 | 22.29 | alarm (H = 10.84) |

## Problem 2: the square-root bug, found twice

We could not use the normal square root. A version that needed 64-bit division failed to link, because the chip has no routine for it. So `fixed_sqrt` builds the answer one bit at a time using only compare, subtract and shift.

- **First version:** it always returned 0, so nothing ever alarmed.
- **First fix:** it took the whole-number part before the root, which threw away the decimals.
- **Why that mattered:** the first firmware alarmed only when MD was above 15.37 (`H` 13.84 plus `k` 1.53). Anything just above that was rounded down and missed:

| True MD | After the first fix | Alarm? |
|---|---:|---|
| 15.5 | 15 | missed |
| 15.9 | 15 | missed |

- **Final fix:** do the root in 64-bit so the decimals survive. The host test shows it is within one step (0.0000153) over 2 million values.

## Problem 3: the threshold did not fit how the firmware runs

- The Python detector adds up evidence over a 20-boot window.
- The firmware sees one boot, calls the CUSUM once, and decides. With one boot the running total is just that boot's MD, so the CUSUM adds nothing.
- The first firmware used the Python values (`k` 1.53, `H` 13.84), so it alarmed only above MD 15.37.
- On 10 Nov we switched to a plain one-shot threshold: `k` = 0 and `H` = 1.25 times the largest clean MD, which is 10.84.
- This is why the Stage 1 test, which assumed 10 faulted boots in a row, did not carry over.

## Problem 4: the overflow bug that failed open (ISSUE-014)

- The squared distance is computed in 64 bits, then squeezed into 32.
- At 32,768 or more (MD of 181 or more) the value wrapped around, and the code set negative results to 0. A huge timing value could then look like a tiny distance.
- It was found by reading the code, not by a failing test. We then re-ran the pre-fix code (commit 4b019e3) on single sub-stage values to see what it did:

| Sub-stage value | Old code |
|---|---|
| 3,000 cycles | alarm |
| 16 million | alarm |
| 40,000 | **no alarm** |
| 4,294,967,295 (a wrapped timer) | **no alarm** |

So some huge values passed and others did not, which is the dangerous kind of bug: it looks fine in casual testing.

- **Fix, three layers:**
  - Cap each input at 32,767.
  - Saturate the squared distance at its maximum, so MD tops out at 181.02 and alarms.
  - Alarm outright if any sub-stage exceeds 4,096 cycles.

## Results at the freeze (10 Nov)

| Test | Result |
|---|---|
| 1000 clean boots | 14 false alarms (1.4%) |
| 1000 attack boots | 1000 detected |
| Clean MD, largest | 8.7 |
| Attack MD | 19.1 to 31.9 |
| Detector code size | 1,060 bytes |

Detection was good because the fault is large: the clean and attack distances are far apart.

## Weaknesses we already knew about

- **One fault, one checkpoint.** It watched only signature verification and was tested with one fault.
- **ISSUE-012.** QEMU's timer follows host time, so skipping 99% of a loop looks the same as skipping 0%.
- **ISSUE-013.** Every false alarm we examined (23 across two runs) was a timing spike: one or two sub-stages far too slow, with MD from 11.8 up to 171.5. The likely cause is the host pausing QEMU. The training set probably contained no such spikes, because the halting build drops a boot when it alarms. That fits the data but is not proven.
- **ISSUE-015.** Removing all three loops gave a median MD of 9.1, below `H`. All three timings shrink together, and the model treats that as normal. This was the first sign that Mahalanobis could miss a real fault.

These led to Stage 3: add more checkpoints and more fault types and see whether the detector still holds up. It did not.
