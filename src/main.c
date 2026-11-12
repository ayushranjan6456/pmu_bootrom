#include <stdint.h>
#include "cusum_detector.h"
#include "floor_detector.h"

/* ── UART (unchanged) ─────────────────────────────────────────────── */
#define UART0_BASE    0x50200000
#define UART0_DATA    (*((volatile uint32_t *)(UART0_BASE + 0x00)))
#define UART0_STATE   (*((volatile uint32_t *)(UART0_BASE + 0x04)))
#define UART0_CTRL    (*((volatile uint32_t *)(UART0_BASE + 0x08)))
#define UART0_BAUDDIV (*((volatile uint32_t *)(UART0_BASE + 0x10)))
#define UART_STATE_TXFULL (1 << 0)

void uart_init(void) { UART0_BAUDDIV = 16; UART0_CTRL = 1; }

void uart_putc(char c) {
    while (UART0_STATE & UART_STATE_TXFULL);
    UART0_DATA = c;
}

void uart_print(const char *s) { while (*s) uart_putc(*s++); }

void uart_print_u32(uint32_t n) {
    if (n == 0) { uart_putc('0'); return; }
    char buf[10]; int i = 0;
    while (n > 0) { buf[i++] = '0' + (n % 10); n /= 10; }
    while (i > 0) uart_putc(buf[--i]);
}

void uart_println(const char *s) { uart_print(s); uart_print("\r\n"); }

/* ── SysTick registers (always present on all Cortex-M) ──────────── */
/*
 * SysTick is a 24-bit down-counter.
 * SYST_CSR  0xE000E010 : control and status
 *   bit 0 = ENABLE      (1 = counter running)
 *   bit 2 = CLKSOURCE   (1 = processor clock, same clock as DWT)
 *   bit 16= COUNTFLAG   (set when counter reaches 0, cleared on read)
 * SYST_RVR  0xE000E014 : reload value (top of count, max 0x00FFFFFF)
 * SYST_CVR  0xE000E018 : current value (counts DOWN; write any value to clear)
 *
 * Elapsed cycles = RVR - CVR = 0x00FFFFFF - CVR
 * Max measurable without wrap: 16,777,215 cycles (~16M)
 * Our boot stages are in the thousands — no wrap needed.
 */
#define SYST_CSR  (*((volatile uint32_t *)0xE000E010))
#define SYST_RVR  (*((volatile uint32_t *)0xE000E014))
#define SYST_CVR  (*((volatile uint32_t *)0xE000E018))

#define SYST_ENABLE  (1UL << 0)
#define SYST_CLKSRC  (1UL << 2)

void systick_init(void) {
    SYST_RVR = 0x00FFFFFF;          /* load maximum reload value   */
    SYST_CSR = SYST_CLKSRC | SYST_ENABLE;  /* processor clock, start */
    SYST_CVR = 0;                   /* write any value to reload from RVR */

    /* Wait a few cycles for timer to stabilize */
    for (volatile int i = 0; i < 10; i++);
}

/*
 * Returns cycles elapsed since systick_init().
 * SysTick counts DOWN from 0xFFFFFF, so:
 *   elapsed = 0xFFFFFF - CVR
 */
static inline uint32_t systick_elapsed(void) {
    return (0x00FFFFFFUL - (SYST_CVR & 0x00FFFFFFUL));
}

/* ── PMU snapshot ─────────────────────────────────────────────────── */
/*
 * Feature vector for each checkpoint.
 *
 * On QEMU (simulation): only elapsed_cycles is real.
 *   sub_a, sub_b, sub_c are measured by breaking each boot stage
 *   into three sub-sections and timing each independently.
 *   This gives us a genuine 4-dimensional feature vector even in
 *   simulation, because each sub-stage has its own instruction mix
 *   and will shift differently under a glitch.
 *
 * On real hardware: replace systick_elapsed() with DWT_CYCCNT,
 *   DWT_CPICNT, DWT_LSUCNT, DWT_FOLDCNT for the full 5-counter
 *   hardware feature vector. The detector code does not change.
 */
typedef struct {
    uint32_t elapsed_cycles;   /* absolute cycles since boot start  */
    uint32_t sub_a;            /* sub-stage A duration (cycles)     */
    uint32_t sub_b;            /* sub-stage B duration (cycles)     */
    uint32_t sub_c;            /* sub-stage C duration (cycles)     */
} pmu_snapshot_t;

#define NUM_CHECKPOINTS 8

static pmu_snapshot_t boot_log[NUM_CHECKPOINTS];

void pmu_checkpoint(uint32_t id) {
    if (id >= NUM_CHECKPOINTS) return;
    boot_log[id].elapsed_cycles = systick_elapsed();
    /* sub fields populated by the stage functions themselves */
}

/* ── Boot stages with sub-stage timing ───────────────────────────── */
/*
 * Each stage is broken into three sub-sections (A, B, C).
 * We time each sub-section independently so that:
 *   1. We have a 4D feature vector per checkpoint (not just 1D)
 *   2. A glitch at a specific point in the stage shifts only
 *      the sub-stage it hits, giving richer detection signal
 *
 * The volatile loops prevent compiler optimisation.
 * Instruction counts and cycle counts are therefore deterministic
 * across clean boots — essential for Gaussian model assumption.
 */
static void stage_memory_init(uint32_t cp_id) {
    uint32_t t0, t1, t2, t3;

    /* Sub-stage A: stack/BSS region scan simulation */
    t0 = systick_elapsed();
    volatile uint32_t x = 0;
    for (int i = 0; i < 200; i++) x += i;
    t1 = systick_elapsed();

    /* Sub-stage B: peripheral base address probing */
    #ifdef GLITCH_FT1_CP1_MEMCHECK
        /* FT-1: Skip memory check loop (fault injection at CP1 sub_b) */
        t2 = systick_elapsed();
    #else
        for (int i = 0; i < 200; i++) x ^= (i * 7);
        t2 = systick_elapsed();
    #endif

    /* Sub-stage C: clock/PLL configuration simulation */
    for (int i = 0; i < 200; i++) x = (x << 1) | (x >> 31);
    t3 = systick_elapsed();
    (void)x;

    boot_log[cp_id].sub_a = t1 - t0;
    boot_log[cp_id].sub_b = t2 - t1;
    boot_log[cp_id].sub_c = t3 - t2;
}

static void stage_boot_mode_detect(uint32_t cp_id) {
    /*
     * NEW CP2: Boot mode selection (UART boot vs SPI vs CAN)
     * Models: pin sampling, configuration register reads, mode decode
     */
    uint32_t t0, t1, t2, t3;

    /* Sub-stage A: Pin/strap sampling simulation */
    t0 = systick_elapsed();
    volatile uint32_t mode = 0;
    for (int i = 0; i < 150; i++) mode ^= (i & 0xF); /* sample boot pins */
    t1 = systick_elapsed();

    /* Sub-stage B: Configuration register decode */
    for (int i = 0; i < 150; i++) mode = (mode << 2) | (mode >> 30);
    t2 = systick_elapsed();

    /* Sub-stage C: Mode validation and path selection */
    for (int i = 0; i < 150; i++) mode += (i * mode) & 0xFF;
    t3 = systick_elapsed();
    (void)mode;

    boot_log[cp_id].sub_a = t1 - t0;
    boot_log[cp_id].sub_b = t2 - t1;
    boot_log[cp_id].sub_c = t3 - t2;
}

static void stage_signature_verify(uint32_t cp_id) {
    /*
     * PRIMARY GLITCH ATTACK TARGET.
     * An attacker glitches during this stage to:
     *   - skip the hash comparison (make it always return "valid")
     *   - corrupt the result register before the branch
     * A glitch changes the cycle count of whichever sub-stage it hits.
     * Our detector sees the shift in the feature vector.
     */
    uint32_t t0, t1, t2, t3;

    /* Sub-stage A: hash computation (SHA-256 simulation) */
    t0 = systick_elapsed();
    volatile uint32_t x = 0xDEADBEEF;
    #ifdef GLITCH_FT4_CP2_DOUBLE
        /* FT-4: Skip hash loop (double fault: both sub_a and sub_b) */
        t1 = systick_elapsed();
    #else
        for (int i = 0; i < 500; i++) x = (x << 3) ^ (x >> 5) ^ (uint32_t)i;
        t1 = systick_elapsed();
    #endif

    /* Sub-stage B: public key load + modular reduction simulation */
    #if defined(GLITCH_FT4_CP2_DOUBLE)
        /* FT-4: Skip verification loop (double fault with sub_a) */
        t2 = systick_elapsed();
    #elif !defined(GLITCH_ATTACK)
        #define SUB_B_ITERS 300
        for (int i = 0; i < SUB_B_ITERS; i++) x ^= (x * 31337U) >> 8;
        t2 = systick_elapsed();
    #else
        /* GLITCH ATTACK: skip GLITCH_SKIP_PCT percent of the loop iterations
         * (default 100 = bypass the whole sub-stage, no loop is emitted). */
        #ifndef GLITCH_SKIP_PCT
            #define GLITCH_SKIP_PCT 100
        #endif
        #define SUB_B_ITERS (300 * (100 - GLITCH_SKIP_PCT) / 100)
        #if SUB_B_ITERS > 0
        for (int i = 0; i < SUB_B_ITERS; i++) x ^= (x * 31337U) >> 8;
        #endif
        t2 = systick_elapsed();
    #endif

    /* Sub-stage C: signature comparison (the critical branch) */
    #ifndef GLITCH_FT2_CP2_COMPARE
        for (int i = 0; i < 200; i++) x = x ^ (uint32_t)(i * i);
    #endif
    #ifdef GLITCH_FT5_CORRUPT_FLAG
        /* FT-5: extra work inside sub-stage C (timing grows instead of shrinking) */
        volatile uint32_t verify_flag = 1;
        for (int i = 0; i < 50; i++) verify_flag ^= (x & 0x1);
        (void)verify_flag;
    #endif
    t3 = systick_elapsed();
    (void)x;

    boot_log[cp_id].sub_a = t1 - t0;
    boot_log[cp_id].sub_b = t2 - t1;
    boot_log[cp_id].sub_c = t3 - t2;
}

static void stage_decrypt(uint32_t cp_id) {
    /*
     * NEW CP4: Firmware decryption stage
     * Models: Key derivation, IV setup, AES block decryption
     */
    uint32_t t0, t1, t2, t3;

    /* Sub-stage A: Key derivation for decryption */
    t0 = systick_elapsed();
    volatile uint32_t key = 0x12345678;
    for (int i = 0; i < 250; i++) key = (key * 1664525U) + 1013904223U; /* LCG */
    t1 = systick_elapsed();

    /* Sub-stage B: IV setup and block counter init */
    for (int i = 0; i < 250; i++) key ^= (key << 13) ^ (key >> 17);
    t2 = systick_elapsed();

    /* Sub-stage C: AES decryption simulation (block cipher rounds) */
    for (int i = 0; i < 250; i++) key = ((key << 5) ^ (key >> 3)) + i;
    t3 = systick_elapsed();
    (void)key;

    boot_log[cp_id].sub_a = t1 - t0;
    boot_log[cp_id].sub_b = t2 - t1;
    boot_log[cp_id].sub_c = t3 - t2;
}

static void stage_integrity_check(uint32_t cp_id) {
    /*
     * NEW CP5: Post-decrypt integrity validation
     * Models: CRC, authentication tag verify, rollback counter check
     */
    uint32_t t0, t1, t2, t3;

    /* Sub-stage A: CRC-32 computation over firmware */
    t0 = systick_elapsed();
    volatile uint32_t crc = 0xFFFFFFFF;
    for (int i = 0; i < 300; i++) crc = (crc >> 8) ^ (crc & 0xFF) ^ i;
    t1 = systick_elapsed();

    /* Sub-stage B: Authentication tag verification (HMAC simulation) */
    for (int i = 0; i < 300; i++) crc ^= (crc * 31337U) >> 8;
    t2 = systick_elapsed();

    /* Sub-stage C: Rollback counter and version check */
    for (int i = 0; i < 300; i++) crc = (crc << 1) | ((crc >> 31) ^ (i & 1));
    t3 = systick_elapsed();
    (void)crc;

    boot_log[cp_id].sub_a = t1 - t0;
    boot_log[cp_id].sub_b = t2 - t1;
    boot_log[cp_id].sub_c = t3 - t2;
}

static void stage_memory_setup(uint32_t cp_id) {
    /*
     * NEW CP6: Memory protection and isolation setup
     * Models: MMU config, MPU regions, TrustZone-M boundaries
     */
    uint32_t t0, t1, t2, t3;

    /* Sub-stage A: MPU region programming */
    t0 = systick_elapsed();
    volatile uint32_t mpu = 0;
    for (int i = 0; i < 180; i++) mpu |= (i << (i & 0x1F));
    t1 = systick_elapsed();

    /* Sub-stage B: TrustZone-M SAU configuration */
    for (int i = 0; i < 180; i++) mpu ^= (mpu >> 7) | (i << 16);
    t2 = systick_elapsed();

    /* Sub-stage C: Memory barrier and permission validation */
    for (int i = 0; i < 180; i++) mpu = (mpu + i) ^ (mpu >> 3);
    t3 = systick_elapsed();
    (void)mpu;

    boot_log[cp_id].sub_a = t1 - t0;
    boot_log[cp_id].sub_b = t2 - t1;
    boot_log[cp_id].sub_c = t3 - t2;
}

static void stage_handoff(uint32_t cp_id) {
    /*
     * CP7: Final handoff preparation to application firmware
     * Models: Stack setup, register init, jump vector preparation
     */
    uint32_t t0, t1, t2, t3;

    /* Sub-stage A: Stack pointer and frame setup */
    t0 = systick_elapsed();
    volatile uint32_t sp = 0x20010000; /* app stack base */
    #ifdef GLITCH_FT3_CP7_HANDOFF
        /* FT-3: Skip stack setup loop (fault injection at CP7 sub_a) */
        t1 = systick_elapsed();
    #else
        for (int i = 0; i < 120; i++) sp += (i * 4); /* stack frame calc */
        t1 = systick_elapsed();
    #endif

    /* Sub-stage B: Application entry point validation */
    for (int i = 0; i < 120; i++) sp ^= (sp >> 11) ^ i;
    t2 = systick_elapsed();

    /* Sub-stage C: Final register state and jump preparation */
    for (int i = 0; i < 120; i++) sp = (sp << 3) | ((sp >> 29) & 0x7);
    t3 = systick_elapsed();
    (void)sp;

    boot_log[cp_id].sub_a = t1 - t0;
    boot_log[cp_id].sub_b = t2 - t1;
    boot_log[cp_id].sub_c = t3 - t2;
}

/* ── Detection helpers ────────────────────────────────────────────── */

/*
 * A checkpoint's readings are usable only if SysTick did not wrap or stall:
 * elapsed must rise, stay below the 24-bit maximum, and cover the three
 * sub-stages. Under heavy host load QEMU's SysTick (host time) breaks this.
 * Both detectors skip an invalid checkpoint, so a fault that also corrupts
 * the timer would pass; real hardware (DWT) has no such wrap.
 */
static uint8_t timer_ok(uint32_t id)
{
    const pmu_snapshot_t *s = &boot_log[id];
    uint32_t prev = boot_log[id - 1].elapsed_cycles;
    if (s->elapsed_cycles >= 0x00FFFFFFUL || s->elapsed_cycles <= prev) return 0;
    uint32_t step = s->elapsed_cycles - prev;
    if (s->sub_a > step || s->sub_b > step || s->sub_c > step) return 0;
    return (s->sub_a + s->sub_b + s->sub_c <= step);
}

/* Prints the alarm. In COLLECT_MODE the boot continues so the telemetry is still recorded. */
static void report_alarm(const char *detector, uint32_t cp, const uint32_t f[3])
{
    uart_print("\r\n!!! ATTACK DETECTED at CP"); uart_print_u32(cp);
    uart_print(" ("); uart_print(detector); uart_println(") !!!");
    uart_print("ALARM,"); uart_print(detector); uart_putc(','); uart_print_u32(cp);
    uart_print("\r\nALARM_FEATURES,");
    uart_print_u32(f[0]); uart_putc(',');
    uart_print_u32(f[1]); uart_putc(',');
    uart_print_u32(f[2]);
    uart_println("\r\nHALTING BOOT - Security violation");
#ifndef COLLECT_MODE
    while (1) {
        /* In real system: erase keys, disable peripherals */
    }
#endif
}

/* Floor check on every stage checkpoint; Mahalanobis (CUSUM) on CP3 only. */
static void check_checkpoint(uint32_t cp, cusum_state_t *detector)
{
    if (!timer_ok(cp)) {
        uart_print("TIMER_INVALID,"); uart_print_u32(cp); uart_print("\r\n");
        return;
    }
    uint32_t f[3] = { boot_log[cp].sub_a, boot_log[cp].sub_b, boot_log[cp].sub_c };
    if (cp == 3 && cusum_update(detector, f, 3)) report_alarm("mahalanobis", cp, f);
    if (floor_check(cp, f)) report_alarm("floor", cp, f);
}

/* ── Main ─────────────────────────────────────────────────────────── */
int main(void)
{
    systick_init();

    uart_init();
    uart_println("=== PMU BOOTROM STUB v0.3 ===");
    uart_println("Counter: SysTick (processor clock, 24-bit)");
    uart_println("Features: elapsed_cycles | sub_a | sub_b | sub_c");
    uart_println("Detector: floor check (CP1-7) + Mahalanobis CUSUM (CP3)");

    cusum_state_t detector;
    cusum_init(&detector);

    /* Checkpoint 0: boot start baseline
     * Note: Includes UART init overhead (~400-1000 cycles)
     * This is consistent across boots, so doesn't affect detection
     */
    pmu_checkpoint(0);

    /* Stage 1: memory init */
    stage_memory_init(1);
    pmu_checkpoint(1);
    check_checkpoint(1, &detector);

    /* Stage 2: boot mode detection */
    stage_boot_mode_detect(2);
    pmu_checkpoint(2);
    check_checkpoint(2, &detector);

    /* Stage 3: signature verify — primary attack target */
    stage_signature_verify(3);
    pmu_checkpoint(3);
    check_checkpoint(3, &detector);

    /* Stage 4: decrypt firmware image */
    stage_decrypt(4);
    pmu_checkpoint(4);
    check_checkpoint(4, &detector);

    /* Stage 5: integrity check (CRC, auth tag, rollback) */
    stage_integrity_check(5);
    pmu_checkpoint(5);
    check_checkpoint(5, &detector);

    /* Stage 6: memory protection setup (MPU, TrustZone-M) */
    stage_memory_setup(6);
    pmu_checkpoint(6);
    check_checkpoint(6, &detector);

    /* Stage 7: handoff preparation */
    stage_handoff(7);
    pmu_checkpoint(7);
    check_checkpoint(7, &detector);

    /* ── Output: one line per checkpoint, CSV format ── */
    /*
     * CSV format makes it trivial to pipe into Python for analysis.
     * Next step: run this 500 times, collect all lines, fit Gaussian.
     * Format: cp,elapsed,sub_a,sub_b,sub_c
     */
    uart_println("\r\nDATA_START");
    uart_print("cp,elapsed,sub_a,sub_b,sub_c\r\n");
    for (int i = 0; i < NUM_CHECKPOINTS; i++) {
        uart_print_u32(i);              uart_putc(',');
        uart_print_u32(boot_log[i].elapsed_cycles); uart_putc(',');
        uart_print_u32(boot_log[i].sub_a);          uart_putc(',');
        uart_print_u32(boot_log[i].sub_b);          uart_putc(',');
        uart_print_u32(boot_log[i].sub_c);          uart_print("\r\n");
    }
    uart_println("DATA_END");

    /* ── Human-readable deltas ── */
    uart_println("\r\n=== STAGE DURATIONS ===");
    for (int i = 1; i < NUM_CHECKPOINTS; i++) {
        uint32_t d = boot_log[i].elapsed_cycles - boot_log[i-1].elapsed_cycles;
        uart_print("Stage "); uart_print_u32(i);
        uart_print(": "); uart_print_u32(d);
        uart_println(" cycles total");
    }

    uart_println("\r\n=== BOOT COMPLETE ===");
    while (1);
    return 0;
}