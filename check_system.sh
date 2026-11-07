#!/bin/bash
echo "=== SYSTEM INFO ==="
echo "Date: $(date)"
echo "Hostname: $(hostname)"
echo "OS: $(uname -a)"
echo ""
echo "=== QEMU VERSION ==="
qemu-system-arm --version
echo ""
echo "=== GCC VERSION ==="
arm-none-eabi-gcc --version | head -1
echo ""
echo "=== QEMU CAPABILITIES ==="
qemu-system-arm -machine mps2-an505 -cpu cortex-m33 -accel help 2>&1 | head -10
