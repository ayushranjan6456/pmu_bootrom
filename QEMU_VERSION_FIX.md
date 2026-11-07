# QEMU Version Compatibility Issue

## Problem

**Symptom:** `make run` shows no UART output, just "Timer with period zero, disabling" warning.

**Root Cause:** QEMU 6.2.0 (default on Ubuntu 22.04) has a bug where MPS2-AN505 UART is not routed to console with `-nographic` flag.

## Diagnosis

Check your QEMU version:
```bash
qemu-system-arm --version
```

- ❌ **QEMU 6.2.0 or earlier**: UART output broken
- ✅ **QEMU 8.0.0 or later**: UART output works

## Solutions

### Option 1: Use Working Machine (Immediate)

Run data collection on machine with QEMU 8.x (e.g., your WSL2 machine):

```bash
# On machine with QEMU 8.2.2+
cd /mnt/c/MTech/Project/pmu_bootrom
make collect
make collect-attack

# Copy generated CSV files to analysis machine:
# - data/nominal_boots.csv
# - data/attack_boots.csv
```

Then run Python analysis on any machine.

### Option 2: Upgrade QEMU (Recommended)

#### Quick Check for Backports:
```bash
apt-cache policy qemu-system-arm
```

If version 8.x is available:
```bash
sudo apt update
sudo apt install qemu-system-arm
```

#### Install from Ubuntu 24.04 Repository:
```bash
# Add repository
sudo add-apt-repository ppa:canonical-kernel-team/ubuntu/ppa
sudo apt update
sudo apt install qemu-system-arm
```

#### Build from Source:
```bash
# Run the provided script
bash install_qemu_8.sh
```

This takes ~10 minutes and installs QEMU 8.2.2 to `/usr/local/bin/`.

### Option 3: Use Docker (Alternative)

```bash
# Pull Ubuntu 24.04 image with QEMU 8.x
docker pull ubuntu:24.04

# Run data collection in container
docker run -v $(pwd):/work -w /work ubuntu:24.04 bash -c "
  apt update && apt install -y qemu-system-arm gcc-arm-none-eabi make
  make collect
"
```

## Verification

After upgrade, test:
```bash
make run
```

Expected output:
```
=== PMU BOOTROM STUB v0.2 ===
Counter: SysTick (processor clock, 24-bit)
Features: elapsed_cycles | sub_a | sub_b | sub_c

DATA_START
cp,elapsed,sub_a,sub_b,sub_c
0,1606,0,0,0
1,6650,929,859,849
2,10408,963,810,707
3,13834,753,703,753
DATA_END

=== STAGE DURATIONS ===
Stage 1: 5044 cycles total
Stage 2: 3758 cycles total
Stage 3: 3426 cycles total

=== BOOT COMPLETE ===
```

## Technical Details

**What Changed Between QEMU 6.2 and 8.2:**
- MPS2-AN505 UART (`CMSDK_APB_UART`) character device routing
- Console backend initialization order
- Serial port `-nographic` handling

The bug causes UART writes to succeed (no crash) but output is discarded instead of being routed to stdio.

## Workaround Without Upgrade

If you cannot upgrade QEMU, modify `Makefile` to use semihosting output instead of UART (requires firmware changes - not recommended for this project).
