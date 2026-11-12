#!/bin/bash
# Collect N non-halting boots for the clean build and each fault build.
# Usage: bash scripts/collect_fault_types.sh [N_BOOTS] [PREFIX]
# Output: data/<PREFIX>_<label>.csv (boot_id,cp,elapsed,sub_a,sub_b,sub_c)
#         data/<PREFIX>_meta.txt (QEMU version, git commit, ELF hashes, host load)
set -euo pipefail

N_BOOTS=${1:-100}
PREFIX=${2:-ds1}
QEMU=qemu-system-arm
QEMU_FLAGS="-machine mps2-an505 -cpu cortex-m33 -nographic"
BOOT_SECONDS=0.8
EXPECTED_CPS=8
DATA_DIR=data

# label:make-target
VARIANTS="clean:app_collect.elf ft1:app_ft1.elf ft2:app_ft2.elf ft3:app_ft3.elf ft4:app_ft4.elf ft5:app_ft5.elf attack:app_attack.elf"

QEMU_VERSION=$($QEMU --version | head -1)
case "$QEMU_VERSION" in
    *"version 8."*|*"version 9."*|*"version 1"[0-9]*) ;;
    *) echo "ERROR: need QEMU 8 or newer (6.x alarms on every boot). Found: $QEMU_VERSION"; exit 1 ;;
esac

# Always rebuild: a stale ELF built from older sources silently corrupts the dataset.
for v in $VARIANTS; do rm -f "${v#*:}"; done
for v in $VARIANTS; do make "${v#*:}" > /dev/null; done

META="$DATA_DIR/${PREFIX}_meta.txt"
{
    echo "date: $(date -Iseconds)"
    echo "qemu: $QEMU_VERSION"
    echo "git_head: $(git rev-parse --short HEAD)"
    echo "git_dirty_firmware: $(git status --porcelain src Makefile | wc -l) files"
    echo "boots_per_variant: $N_BOOTS"
    for v in $VARIANTS; do echo "elf: $(sha256sum "${v#*:}" | cut -c1-12) ${v#*:}"; done
} > "$META"
cat "$META"
echo

TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT
FAILED=0

for v in $VARIANTS; do
    label=${v%%:*}
    elf=${v#*:}
    out="$DATA_DIR/${PREFIX}_${label}.csv"
    echo "boot_id,cp,elapsed,sub_a,sub_b,sub_c" > "$out"
    # What the firmware itself decided on each boot (COLLECT_MODE prints the alarm and carries on).
    # alarms is a ';'-separated list of detector@cp, timer_invalid the checkpoints whose timer readings were rejected.
    bootlog="$DATA_DIR/${PREFIX}_${label}_boots.csv"
    echo "boot_id,loadavg,alarms,timer_invalid" > "$bootlog"
    incomplete=""
    load_start=$(cut -d' ' -f1 /proc/loadavg)

    for i in $(seq 1 "$N_BOOTS"); do
        boot_load=$(cut -d' ' -f1 /proc/loadavg)
        $QEMU $QEMU_FLAGS -kernel "$elf" > "$TMP" 2>&1 &
        pid=$!
        sleep "$BOOT_SECONDS"
        kill "$pid" 2>/dev/null || true
        wait "$pid" 2>/dev/null || true

        alarms=$(tr -d '\r' < "$TMP" | awk -F, '/^ALARM,/{printf "%s%s@%s", s, $2, $3; s=";"}')
        tinv=$(tr -d '\r' < "$TMP" | awk -F, '/^TIMER_INVALID,/{printf "%s%s", s, $2; s=";"}')
        echo "$i,$boot_load,$alarms,$tinv" >> "$bootlog"

        rows=$(awk '/DATA_START/{f=1;next} /DATA_END/{f=0} f && /^[0-9]/' "$TMP")
        n=$(printf '%s\n' "$rows" | grep -c '^[0-9]' || true)
        if [ "$n" -ne "$EXPECTED_CPS" ]; then
            # Catches stale or wrong firmware on the first boot instead of after 28 minutes.
            if [ "$i" -eq 1 ]; then
                echo "ERROR: $label ($elf) boot 1 produced $n rows, expected $EXPECTED_CPS"; exit 1
            fi
            incomplete="$incomplete $i"
            continue
        fi
        printf '%s\n' "$rows" | awk -F',' -v id="$i" '{print id","$0}' >> "$out"
    done

    load_end=$(cut -d' ' -f1 /proc/loadavg)
    got=$(( $(wc -l < "$out") - 1 ))
    printf '%-7s boots=%d/%d  loadavg %s -> %s' "$label" $((got / EXPECTED_CPS)) "$N_BOOTS" "$load_start" "$load_end"
    if [ -n "$incomplete" ]; then
        printf '  INCOMPLETE boot ids:%s' "$incomplete"; FAILED=1
    fi
    echo
    echo "$label: loadavg $load_start -> $load_end, incomplete:${incomplete:- none}" >> "$META"
done

[ "$FAILED" -eq 0 ] || { echo "Some boots were incomplete; see above."; exit 1; }
echo "Done. Files: $DATA_DIR/${PREFIX}_*.csv"
