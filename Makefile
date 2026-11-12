# Toolchain and Emulator definitions
CC = arm-none-eabi-gcc
QEMU = qemu-system-arm

# Directories
SRC_DIR = src

# Architecture and Flags
MACH = cortex-m33
CFLAGS = -mcpu=$(MACH) -mthumb -O0 -g -Wall -fno-builtin $(EXTRA_CFLAGS)
LDFLAGS = -nostartfiles -nostdlib -T $(SRC_DIR)/linker.ld

# Source and Object files
SRCS = $(SRC_DIR)/startup.c $(SRC_DIR)/main.c $(SRC_DIR)/cusum_detector.c $(SRC_DIR)/floor_detector.c
OBJS = $(SRCS:.c=.o)

# Rebuild objects when any header changes (a stale object after a table edit corrupts a dataset).
$(OBJS): $(wildcard $(SRC_DIR)/*.h)
TARGET = app.elf

# QEMU configuration
QEMU_FLAGS = -machine mps2-an505 -cpu $(MACH) -nographic

# Default target builds the application
all: $(TARGET)

# Rule to link object files into the final executable
$(TARGET): $(OBJS)
	$(CC) $(CFLAGS) $(LDFLAGS) $^ -o $@

# Rule to compile C source files into object files
$(SRC_DIR)/%.o: $(SRC_DIR)/%.c
	$(CC) $(CFLAGS) -c $< -o $@

# Convenience target to build and immediately run in QEMU
run: $(TARGET)
	$(QEMU) $(QEMU_FLAGS) -kernel $(TARGET)

# Cleanup target to remove compiled artifacts
clean:
	rm -f $(OBJS) $(TARGET)

# Target to boot QEMU paused and waiting for GDB
debug-server: $(TARGET)
	$(QEMU) $(QEMU_FLAGS) -kernel $(TARGET) -s -S

# Convenience target to collect 500 boot samples for the PMU model
collect: $(TARGET)
	bash scripts/collect.sh


# --- Attack Simulation Targets ---

# Non-halting clean build for training data: an alarm does not stop the boot,
# so no clean boot is dropped from the dataset.
app_collect.elf: $(SRCS)
	$(CC) $(CFLAGS) -DCOLLECT_MODE $(LDFLAGS) $^ -o $@

# Original attack build: CP3 sub_b loop removed (100% skip)
app_attack.elf: $(SRCS)
	$(CC) $(CFLAGS) -DGLITCH_ATTACK -DCOLLECT_MODE $(LDFLAGS) $^ -o $@

# FT-1: Skip CP1 memory check loop (sub_b)
app_ft1.elf: $(SRCS)
	$(CC) $(CFLAGS) -DGLITCH_FT1_CP1_MEMCHECK -DCOLLECT_MODE $(LDFLAGS) $^ -o $@

# FT-2: Skip CP3 signature comparison loop (sub_c)
app_ft2.elf: $(SRCS)
	$(CC) $(CFLAGS) -DGLITCH_FT2_CP2_COMPARE -DCOLLECT_MODE $(LDFLAGS) $^ -o $@

# FT-3: Skip CP7 handoff stack setup loop (sub_a)
app_ft3.elf: $(SRCS)
	$(CC) $(CFLAGS) -DGLITCH_FT3_CP7_HANDOFF -DCOLLECT_MODE $(LDFLAGS) $^ -o $@

# FT-4: Skip both CP3 sub_a and sub_b (double loop fault, tests blind spot)
app_ft4.elf: $(SRCS)
	$(CC) $(CFLAGS) -DGLITCH_FT4_CP2_DOUBLE -DCOLLECT_MODE $(LDFLAGS) $^ -o $@

# FT-5: Variable corruption (adds extra work rather than skipping)
app_ft5.elf: $(SRCS)
	$(CC) $(CFLAGS) -DGLITCH_FT5_CORRUPT_FLAG -DCOLLECT_MODE $(LDFLAGS) $^ -o $@

# Convenience target to collect 50 boots under attack
collect-attack: app_attack.elf
	@echo "Collecting attacked boot samples..."
	@OUTPUT="data/attack_boots.csv" TEMP_FILE="data/temp_attack.txt"; \
	echo "boot_id,cp,elapsed,sub_a,sub_b,sub_c" > "$$OUTPUT"; \
	for i in $$(seq 1 50); do \
		$(QEMU) $(QEMU_FLAGS) -kernel app_attack.elf > "$$TEMP_FILE" & \
		QEMU_PID=$$!; \
		sleep 0.8; \
		kill $$QEMU_PID 2>/dev/null; \
		wait $$QEMU_PID 2>/dev/null; \
		awk '/DATA_START/{f=1;next} /DATA_END/{f=0} f && /^[0-9]/' "$$TEMP_FILE" \
			| awk -F',' -v id=$$i '{print id","$$0}' >> "$$OUTPUT"; \
		printf "\rCollected attacked boot %d/50" $$i; \
	done; \
	rm -f "$$TEMP_FILE"; \
	echo "\nSaved to $$OUTPUT"

# Prevent Make from confusing these targets with actual files
.PHONY: all run clean