#!/bin/bash
# Test collection - 10 boots only
mkdir -p data
OUTPUT="data/test_boots.csv"
TEMP_FILE="data/temp_out.txt"

echo "boot_id,cp,elapsed,sub_a,sub_b,sub_c" > "$OUTPUT"

for i in $(seq 1 10); do
    qemu-system-arm -machine mps2-an505 -cpu cortex-m33 -nographic -kernel app.elf > "$TEMP_FILE" 2>&1 &
    QEMU_PID=$!
    sleep 0.8
    kill $QEMU_PID 2>/dev/null
    wait $QEMU_PID 2>/dev/null
    
    awk '/DATA_START/{f=1;next} /DATA_END/{f=0} f && /^[0-9]/' "$TEMP_FILE" \
        | awk -F',' -v id=$i '{print id","$0}' \
        >> "$OUTPUT"
        
    printf "\rCollected boot %d/10" $i
done

echo ""
echo "=== Results ==="
wc -l "$OUTPUT"
echo ""
echo "Checking for corruption markers:"
echo "  CP0 elapsed=16777215: $(grep -c ',0,16777215,' "$OUTPUT" || echo 0)"
echo "  CP1 sub_a>1000000: $(awk -F',' '$2==1 && $4>1000000 {print}' "$OUTPUT" | wc -l)"
echo ""
echo "Sample data:"
head -15 "$OUTPUT"

rm -f "$TEMP_FILE"
