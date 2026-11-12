#!/bin/bash
# Runs QEMU 500 times, extracts DATA_START..DATA_END blocks, saves to CSV

mkdir -p data
OUTPUT="data/nominal_boots.csv"
TEMP_FILE="data/temp_out.txt"

echo "boot_id,cp,elapsed,sub_a,sub_b,sub_c" > "$OUTPUT"

for i in $(seq 1 500); do
    # 1. Run QEMU in the background, redirecting output to a file
    qemu-system-arm -machine mps2-an505 -cpu cortex-m33 -nographic -kernel app.elf > "$TEMP_FILE" &
    QEMU_PID=$!
    
    # 2. Wait 0.2 seconds (plenty of time for bare-metal boot), then kill QEMU
    sleep 0.8
    kill $QEMU_PID 2>/dev/null
    wait $QEMU_PID 2>/dev/null
    
    # 3. Parse the temporary file and append to the final CSV
    awk '/DATA_START/{f=1;next} /DATA_END/{f=0} f && /^[0-9]/' "$TEMP_FILE" \
        | awk -F',' -v id=$i '{print id","$0}' \
        >> "$OUTPUT"
        
    printf "\rCollected boot %d/500\n" $i
done

# Clean up the temporary file
rm -f "$TEMP_FILE"
echo -e "\nSaved to $OUTPUT"