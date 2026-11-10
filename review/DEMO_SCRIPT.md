# Phase 1 Review: Demo Script

Total about 6 minutes. The review is offline, so prepare everything in advance and keep a recording as a backup.

## Preparation (do once, after the 1000-boot validation has finished)

Do not prepare while `test_firmware_detector.sh` is running: it runs `make clean` and rebuilds `app.elf`.

```bash
cd pmu_bootrom
mkdir -p /tmp/demo

make clean && make
cp app.elf /tmp/demo/clean.elf

make clean
make CFLAGS="-mcpu=cortex-m33 -mthumb -O0 -g -Wall -fno-builtin -DGLITCH_ATTACK" app.elf
cp app.elf /tmp/demo/attack.elf

make clean && make        # leave the tree in its normal state
```

Check for stray emulators before starting: `ps aux | grep qemu | grep -v grep` should print nothing. `severity_sweep.sh` and `test_firmware_detector.sh` both start with `make clean` and rebuild the shared `app.elf` (and `make` does too), so never run two of them, or demo preparation, at the same time; run them one at a time. The sweep rebuilds the normal firmware when it finishes, but the validation script ends on the glitched build. If you are unsure which build is on disk, run `make clean && make` before recording; the demo itself uses the copies in `/tmp/demo`.

Pre-run once and record the terminal (for example `script` or a screen recording) as the fallback. About 1% of clean boots false-alarm (one did in a dry run, the first boot after the builds), so do not record straight after building: wait a minute, and have retakes ready.

## Step 1: Clean boot (about 1.5 min)

```bash
timeout 2 qemu-system-arm -machine mps2-an505 -cpu cortex-m33 -nographic -kernel /tmp/demo/clean.elf </dev/null
```

Run it from an interactive terminal at least once before the review; `</dev/null` avoids the capture problem seen there.

Show: banner, the `DATA_START ... DATA_END` block (one row per checkpoint: cp, elapsed, sub_a, sub_b, sub_c) and `=== BOOT COMPLETE ===`.

Say: four checkpoints; checkpoint 2 is signature verification; the detector ran after it and let the boot continue.

## Step 2: Glitched boot (about 1.5 min)

```bash
timeout 2 qemu-system-arm -machine mps2-an505 -cpu cortex-m33 -nographic -kernel /tmp/demo/attack.elf </dev/null
```

Show: `!!! ATTACK DETECTED at CP2 !!!` and no `BOOT COMPLETE`.

Say: the macro skips the sub-stage B loop, which models a glitch that skips verification work; sub_b drops by hundreds of cycles; the Mahalanobis distance jumps above the threshold; the boot halts.

## Step 3: Why it works, with data (about 1.5 min)

Open `results/model_distributions.png` and `results/empirical_attack.png`. Point at how far the attack cluster sits from the clean cloud.

Say: the simulated fault is large, so the separation is wide. The Python simulation shows what happens at lower severity (open `results/cusum_results.png`).

## Step 4: Validation summary (about 1 min)

```bash
tail -8 results/validation_1000.log
```

Show the false-alarm and detection rates. Say where the log comes from and that it runs 1000 clean and 1000 glitched boots through the same QEMU flow.

## Step 5: Honest limits (about 30 s)

State one-shot detection, single fault type and severity, QEMU noise, SysTick not PMU. Then point to Phase 2.

## If something goes wrong
| Symptom | Action |
|---|---|
| QEMU prints nothing | Check `qemu-system-arm --version` is 8.0 or newer (the project was run on 8.2.2). |
| QEMU does not exit | `Ctrl-A` then `X`, or rely on `timeout`. |
| Clean boot shows a false alarm | Run it again and say so: the measured false-alarm rate is in STATUS.md, and one alarm in a live demo is consistent with it. |
| Attack not detected | Run again; if it repeats, switch to the recording. |
| Anything else | Switch to the recording. |
