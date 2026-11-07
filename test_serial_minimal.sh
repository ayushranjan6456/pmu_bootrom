#!/bin/bash
echo "=== Testing Serial Output on Current Machine ==="

echo ""
echo "Test 1: app.elf with -nographic"
timeout 1s qemu-system-arm -machine mps2-an505 -cpu cortex-m33 -nographic -kernel app.elf 2>&1 | head -30

echo ""
echo "Test 2: pmu_bootrom.elf with -nographic"
timeout 1s qemu-system-arm -machine mps2-an505 -cpu cortex-m33 -nographic -kernel pmu_bootrom.elf 2>&1 | head -30

echo ""
echo "Test 3: Redirecting to file"
qemu-system-arm -machine mps2-an505 -cpu cortex-m33 -nographic -kernel app.elf > /tmp/qemu_output.txt 2>&1 &
QEMU_PID=$!
sleep 1
kill $QEMU_PID 2>/dev/null
wait $QEMU_PID 2>/dev/null
echo "File contents:"
cat /tmp/qemu_output.txt
