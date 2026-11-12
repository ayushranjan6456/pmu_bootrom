#!/bin/bash
# End-to-end test of the real (halting) firmware: what happens to a boot when the floor rule fires.
# Usage: N=300 bash scripts/test_halting_build.sh        (writes results/validation_halting.log)
# For each build variant (no -DCOLLECT_MODE) runs N boots and counts how many halt, complete, or
# complete with a Mahalanobis warning. Load average is recorded per boot.
set -euo pipefail

N=${N:-300}
QEMU_FLAGS="-machine mps2-an505 -cpu cortex-m33 -nographic"
LOG=results/validation_halting.log
VARIANTS="clean: attack:-DGLITCH_ATTACK ft1:-DGLITCH_FT1_CP1_MEMCHECK ft2:-DGLITCH_FT2_CP2_COMPARE ft3:-DGLITCH_FT3_CP7_HANDOFF ft4:-DGLITCH_FT4_CP2_DOUBLE ft5:-DGLITCH_FT5_CORRUPT_FLAG"

case "$(qemu-system-arm --version | head -1)" in
    *"version 8."*|*"version 9."*|*"version 1"[0-9]*) ;;
    *) echo "ERROR: need QEMU 8 or newer"; exit 1 ;;
esac

TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT
{
    echo "HALTING-BUILD TEST, $N boots per variant"
    echo "date: $(date -Iseconds)   git: $(git rev-parse --short HEAD)   $(qemu-system-arm --version | head -1)"
    echo "floor table + Mahalanobis constants as compiled from src/ (dirty firmware files: $(git status --porcelain src Makefile | wc -l))"
    printf '%-7s %-8s %7s %9s %10s %9s %8s %8s\n' variant elf_sha halted completed completed+W no_output load_max load_med
} | tee "$LOG"

for v in $VARIANTS; do
    label=${v%%:*}
    flag=${v#*:}
    make clean > /dev/null
    make EXTRA_CFLAGS="$flag" app.elf > /dev/null
    sha=$(sha256sum app.elf | cut -c1-8)
    halted=0; done_=0; done_w=0; none=0; loads=""
    for i in $(seq 1 "$N"); do
        loads="$loads $(cut -d' ' -f1 /proc/loadavg)"
        qemu-system-arm $QEMU_FLAGS -kernel app.elf </dev/null > "$TMP" 2>&1 &
        pid=$!
        sleep 0.8
        kill "$pid" 2>/dev/null || true
        wait "$pid" 2>/dev/null || true
        out=$(tr -d '\r' < "$TMP")
        if ! grep -q "PMU BOOTROM" <<< "$out"; then none=$((none+1)); continue; fi
        if grep -q "HALTING BOOT" <<< "$out"; then halted=$((halted+1))
        elif grep -q "BOOT COMPLETE" <<< "$out"; then
            if grep -q "WARNING ONLY" <<< "$out"; then done_w=$((done_w+1)); else done_=$((done_+1)); fi
        else none=$((none+1)); fi
    done
    lmax=$(tr ' ' '\n' <<< "$loads" | sort -g | tail -1)
    lmed=$(tr ' ' '\n' <<< "$loads" | grep . | sort -g | awk '{a[NR]=$1}END{print a[int((NR+1)/2)]}')
    printf '%-7s %-8s %7d %9d %10d %9d %8s %8s\n' "${label:-clean}" "$sha" "$halted" "$done_" "$done_w" "$none" "$lmax" "$lmed" | tee -a "$LOG"
done
make clean > /dev/null
echo "halted = floor rule stopped the boot; completed+W = reached BOOT COMPLETE after a Mahalanobis warning; no_output = QEMU gave no usable output (not counted as clean or detected)." | tee -a "$LOG"
