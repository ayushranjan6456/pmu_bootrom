# Toolchain and Emulator definitions
CC = arm-none-eabi-gcc
QEMU = qemu-system-arm

# Directories
SRC_DIR = src

# Architecture and Flags
MACH = cortex-m33
CFLAGS = -mcpu=$(MACH) -mthumb -O0 -g -Wall -fno-builtin
LDFLAGS = -nostartfiles -nostdlib -T $(SRC_DIR)/linker.ld

# Source and Object files
SRCS = $(SRC_DIR)/startup.c $(SRC_DIR)/main.c $(SRC_DIR)/cusum_detector.c
OBJS = $(SRCS:.c=.o)
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

# Build the application with the GLITCH_ATTACK macro defined
app_attack.elf: $(OBJS)
	$(CC) $(CFLAGS) -DGLITCH_ATTACK -c $(SRC_DIR)/main.c -o $(SRC_DIR)/main.o
	$(CC) $(CFLAGS) $(LDFLAGS) $(SRC_DIR)/startup.o $(SRC_DIR)/main.o -o $@

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