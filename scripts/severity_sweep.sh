#!/bin/bash
#
# Partial-severity glitch test on the firmware detector.
# Usage: [N=20] [PCTS="0 25 50 75 90 99 100"] bash scripts/severity_sweep.sh
#
# For each percentage, builds the firmware skipping that share of the sub_b
# loop iterations (-DGLITCH_SKIP_PCT), boots it N times in QEMU and reports
# the detection rate and the measured sub_b (mean and median). COLLECT_MODE
# only stops the halt so the telemetry line is still printed; the alarm
# decision is the same one the halting build makes. PCT=0 is a no-glitch
# reference. Output is also written to results/severity_sweep.log.

N=${N:-20}
PCTS=${PCTS:-"0 25 50 75 90 99 100"}
BASE="-mcpu=cortex-m33 -mthumb -O0 -g -Wall -fno-builtin"
LOG=results/severity_sweep.log

mkdir -p results
exec > >(tee "$LOG") 2>&1

echo "Date: $(date -Iseconds)   N=$N per setting"
echo "QEMU: $(qemu-system-arm --version | head -1)"
clean_sub_b=$(awk -F, '$2==2 {s+=$5; n++} END {print s/n}' data/nominal_boots.csv)
echo "Mean clean sub_b: $clean_sub_b cycles (from data/nominal_boots.csv)"
echo ""
printf "%-7s %-11s %-10s %-9s %-9s %s\n" "Skip %" "Iterations" "Detected" "Mean b" "Median b" "Mean reduction"

for pct in $PCTS; do
    make clean > /dev/null 2>&1
    make CFLAGS="$BASE -DGLITCH_ATTACK -DGLITCH_SKIP_PCT=$pct -DCOLLECT_MODE" app.elf > /dev/null 2>&1 \
        || { echo "build failed for $pct%"; exit 1; }

    detected=0
    vals=()
    for i in $(seq 1 $N); do
        output=$(timeout 0.5 make run 2>&1 </dev/null || true)
        echo "$output" | grep -q "PMU BOOTROM" || { echo "ERROR: boot produced no output; aborting" >&2; exit 2; }
        if echo "$output" | grep -q "ATTACK DETECTED"; then
            detected=$((detected+1))
        fi
        b=$(echo "$output" | awk -F, '/^2,/ {print $4; exit}' | tr -d '\r')
        [ -n "$b" ] && vals+=("$b")
    done

    parsed=${#vals[@]}
    if [ "$parsed" -eq 0 ]; then
        printf "%-7s %-11s %-10s no telemetry parsed\n" "$pct" "-" "$detected/$N"
        continue
    fi
    mean_b=$(printf '%s\n' "${vals[@]}" | awk '{s+=$1} END {printf "%.1f", s/NR}')
    med_b=$(printf '%s\n' "${vals[@]}" | sort -n | awk '{a[NR]=$1} END {print a[int((NR+1)/2)]}')
    red=$(awk -v m="$mean_b" -v c="$clean_sub_b" 'BEGIN {printf "%.1f", 100*(1-m/c)}')
    iters=$((300 * (100 - pct) / 100))
    printf "%-7s %-11s %-10s %-9s %-9s %s%%\n" "$pct" "$iters" "$detected/$N" "$mean_b" "$med_b" "$red"
done

make clean > /dev/null 2>&1
make > /dev/null 2>&1
echo ""
echo "Rebuilt the normal firmware (app.elf)."
