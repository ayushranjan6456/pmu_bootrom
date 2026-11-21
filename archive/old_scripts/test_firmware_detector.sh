#!/bin/bash
#
# Test firmware CUSUM detector
# Runs clean boots and glitch attacks, verifies detection

set -e

# Number of boots to test (default 20, override with N=1000 bash script.sh)
N=${N:-20}

# Without </dev/null, QEMU can block on the terminal and the capture comes back
# empty; every boot would then look clean. Abort instead of reporting that.
check_boot() {
    if ! echo "$1" | grep -q "PMU BOOTROM"; then
        echo "ERROR: boot produced no output (QEMU did not run); aborting" >&2
        exit 2
    fi
}

echo "=== FIRMWARE CUSUM DETECTOR TEST ==="
echo "Testing with N=$N boots per test"
echo ""

# Test 1: Clean boots should NOT alarm
echo "TEST 1: Clean boots (expect NO alarms)"
echo "---------------------------------------"
make clean > /dev/null 2>&1
make all > /dev/null 2>&1

alarm_count=0
# Telemetry of every false-alarm boot, for investigating why they happen
rm -rf results/false_alarms
mkdir -p results/false_alarms
echo "boot,sub_a,sub_b,sub_c" > results/false_alarms.csv
for i in $(seq 1 $N); do
    output=$(timeout 0.5 make run 2>&1 </dev/null || true)
    check_boot "$output"
    if echo "$output" | grep -q "ATTACK DETECTED"; then
        echo "  Boot $i: ❌ FALSE ALARM!"
        alarm_count=$((alarm_count+1))
        feat=$(echo "$output" | tr -d '\r' | awk -F, '/^ALARM_FEATURES/ {print $2","$3","$4; exit}')
        echo "$i,${feat:-,,}" >> results/false_alarms.csv
        echo "$output" > results/false_alarms/boot_$i.txt
    else
        echo "  Boot $i: ✓ Clean"
    fi
done

fa_rate=$(echo "scale=1; 100*$alarm_count/$N" | bc)
echo ""
echo "False alarm rate: $fa_rate% ($alarm_count/$N)"
if [ $((alarm_count*100)) -le $((N*5)) ]; then
    echo "✓ PASS: False alarm rate acceptable (<5%)"
else
    echo "❌ FAIL: Too many false alarms!"
fi

echo ""
echo ""

# Test 2: Glitch attacks should alarm
echo "TEST 2: Glitch attacks (expect ALARMS)"
echo "---------------------------------------"
make clean > /dev/null 2>&1
make CFLAGS="-mcpu=cortex-m33 -mthumb -O0 -g -Wall -fno-builtin -DGLITCH_ATTACK" app.elf > /dev/null 2>&1

detect_count=0
for i in $(seq 1 $N); do
    output=$(timeout 0.5 make run 2>&1 </dev/null || true)
    check_boot "$output"
    if echo "$output" | grep -q "ATTACK DETECTED"; then
        echo "  Attack $i: ✓ DETECTED"
        detect_count=$((detect_count+1))
    else
        echo "  Attack $i: ❌ MISSED!"
    fi
done

det_rate=$(echo "scale=1; 100*$detect_count/$N" | bc)
echo ""
echo "Detection rate: $det_rate% ($detect_count/$N)"
if [ $((detect_count*100)) -ge $((N*90)) ]; then
    echo "✓ PASS: Detection rate good (>90%)"
else
    echo "❌ FAIL: Detection rate too low!"
fi

echo ""
echo "=== TEST SUMMARY ==="
echo "False Alarm Rate: $fa_rate%"
echo "Detection Rate:   $det_rate%"
echo ""

if [ $((alarm_count*100)) -le $((N*5)) ] && [ $((detect_count*100)) -ge $((N*90)) ]; then
    echo "✅ ALL TESTS PASSED!"
    exit 0
else
    echo "❌ SOME TESTS FAILED"
    exit 1
fi
