#!/bin/bash
# Enhanced collection script for multiple fault types
# Collects N boots for each fault type plus clean baseline

set -e

QEMU="qemu-system-arm"
QEMU_FLAGS="-machine mps2-an505 -cpu cortex-m33 -nographic"
BOOT_TIMEOUT=0.8  # seconds to let each boot run

# Default values
N_BOOTS=100
DATA_DIR="data"
OUTPUT_PREFIX="ft_collection"

# Parse arguments
if [ $# -ge 1 ]; then
    N_BOOTS=$1
fi

if [ $# -ge 2 ]; then
    OUTPUT_PREFIX=$2
fi

echo "=== Fault Type Data Collection ==="
echo "Date: $(date -Iseconds)"
echo "Collecting $N_BOOTS boots per fault type"
echo "QEMU: $($QEMU --version | head -1)"
echo ""

# Fault types to collect
declare -A FAULT_TYPES
FAULT_TYPES[clean]="app.elf"
FAULT_TYPES[ft1]="app_ft1.elf"
FAULT_TYPES[ft2]="app_ft2.elf"
FAULT_TYPES[ft3]="app_ft3.elf"
FAULT_TYPES[ft4]="app_ft4.elf"
FAULT_TYPES[ft5]="app_ft5.elf"
FAULT_TYPES[attack]="app_attack.elf"  # Original CP3 sub_b removal

# Build all firmware variants
echo "Building all firmware variants..."
make clean > /dev/null 2>&1
for fw in "${FAULT_TYPES[@]}"; do
    if [ ! -f "$fw" ]; then
        target=$(basename "$fw")
        echo "  Building $target..."
        make "$target" > /dev/null 2>&1
    fi
done
echo ""

# Function to collect boots for one fault type
collect_fault_type() {
    local label=$1
    local firmware=$2
    local output_file="${DATA_DIR}/${OUTPUT_PREFIX}_${label}.csv"
    local temp_file="${DATA_DIR}/temp_${label}.txt"

    echo "Collecting $label ($N_BOOTS boots)..."
    echo "boot_id,cp,elapsed,sub_a,sub_b,sub_c" > "$output_file"

    for i in $(seq 1 $N_BOOTS); do
        # Run QEMU in background
        $QEMU $QEMU_FLAGS -kernel "$firmware" > "$temp_file" 2>&1 &
        QEMU_PID=$!

        # Wait for boot to complete
        sleep $BOOT_TIMEOUT

        # Kill QEMU
        kill $QEMU_PID 2>/dev/null || true
        wait $QEMU_PID 2>/dev/null || true

        # Extract CSV data (between DATA_START and DATA_END)
        # Prepend boot_id to each line
        awk '/DATA_START/{f=1;next} /DATA_END/{f=0} f && /^[0-9]/' "$temp_file" \
            | awk -F',' -v id=$i '{print id","$0}' >> "$output_file"

        # Progress indicator
        if (( i % 10 == 0 )); then
            printf "\r  Progress: %d/%d" $i $N_BOOTS
        fi
    done

    echo ""  # newline after progress
    rm -f "$temp_file"

    # Count how many boots were captured
    local n_captured=$(( $(wc -l < "$output_file") - 1 ))
    local n_expected=$(( N_BOOTS * 8 ))  # 8 checkpoints per boot
    echo "  Captured: $n_captured rows (expected $n_expected)"

    if [ $n_captured -lt $(( n_expected * 95 / 100 )) ]; then
        echo "  WARNING: Missing >5% of data!"
    fi

    echo "  Saved to $output_file"
    echo ""
}

# Collect data for each fault type
for label in clean ft1 ft2 ft3 ft4 ft5 attack; do
    firmware=${FAULT_TYPES[$label]}
    collect_fault_type "$label" "$firmware"
done

echo "=== Collection Complete ==="
echo "Output files in $DATA_DIR/${OUTPUT_PREFIX}_*.csv"
echo ""
echo "Summary:"
for label in clean ft1 ft2 ft3 ft4 ft5 attack; do
    file="${DATA_DIR}/${OUTPUT_PREFIX}_${label}.csv"
    if [ -f "$file" ]; then
        n_rows=$(( $(wc -l < "$file") - 1 ))
        n_boots=$(( n_rows / 8 ))
        printf "  %-10s %4d boots (%5d rows)\n" "$label:" $n_boots $n_rows
    fi
done
