#!/bin/bash
#
# Test firmware CUSUM detector
# Runs clean boots and glitch attacks, verifies detection

set -e

echo "=== FIRMWARE CUSUM DETECTOR TEST ==="
echo ""

# Test 1: Clean boots should NOT alarm
echo "TEST 1: Clean boots (expect NO alarms)"
echo "---------------------------------------"
make clean > /dev/null 2>&1
make all > /dev/null 2>&1

alarm_count=0
for i in {1..20}; do
    output=$(timeout 0.5 make run 2>&1 || true)
    if echo "$output" | grep -q "ATTACK DETECTED"; then
        echo "  Boot $i: ❌ FALSE ALARM!"
        ((alarm_count++))
    else
        echo "  Boot $i: ✓ Clean"
    fi
done

fa_rate=$(echo "scale=1; 100*$alarm_count/20" | bc)
echo ""
echo "False alarm rate: $fa_rate% ($alarm_count/20)"
if [ $alarm_count -le 1 ]; then
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
for i in {1..20}; do
    output=$(timeout 0.5 make run 2>&1 || true)
    if echo "$output" | grep -q "ATTACK DETECTED"; then
        echo "  Attack $i: ✓ DETECTED"
        ((detect_count++))
    else
        echo "  Attack $i: ❌ MISSED!"
    fi
done

det_rate=$(echo "scale=1; 100*$detect_count/20" | bc)
echo ""
echo "Detection rate: $det_rate% ($detect_count/20)"
if [ $detect_count -ge 18 ]; then
    echo "✓ PASS: Detection rate good (>90%)"
else
    echo "❌ FAIL: Detection rate too low!"
fi

echo ""
echo "=== TEST SUMMARY ==="
echo "False Alarm Rate: $fa_rate%"
echo "Detection Rate:   $det_rate%"
echo ""

if [ $alarm_count -le 1 ] && [ $detect_count -ge 18 ]; then
    echo "✅ ALL TESTS PASSED!"
    exit 0
else
    echo "❌ SOME TESTS FAILED"
    exit 1
fi
