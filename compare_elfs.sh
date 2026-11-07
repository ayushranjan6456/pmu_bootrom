#!/bin/bash
echo "=== ELF File Comparison ==="
ls -lh app.elf pmu_bootrom.elf 2>/dev/null || echo "Some files missing"

echo ""
echo "=== app.elf sections ==="
arm-none-eabi-objdump -h app.elf | grep -E "Idx|\.text|\.data|\.bss"

echo ""
echo "=== pmu_bootrom.elf sections ==="
arm-none-eabi-objdump -h pmu_bootrom.elf | grep -E "Idx|\.text|\.data|\.bss"

echo ""
echo "=== Entry points ==="
echo "app.elf:"
arm-none-eabi-readelf -h app.elf | grep "Entry point"
echo "pmu_bootrom.elf:"
arm-none-eabi-readelf -h pmu_bootrom.elf | grep "Entry point"

echo ""
echo "=== Vector table (first 16 bytes) ==="
echo "app.elf:"
arm-none-eabi-objdump -D app.elf | head -15

echo "pmu_bootrom.elf:"
arm-none-eabi-objdump -D pmu_bootrom.elf | head -15
