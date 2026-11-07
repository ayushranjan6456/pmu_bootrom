#include <stdint.h>
#include "cusum_detector.h"

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

#define NUM_CHECKPOINTS 4

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
    for (int i = 0; i < 200; i++) x ^= (i * 7);
    t2 = systick_elapsed();

    /* Sub-stage C: clock/PLL configuration simulation */
    for (int i = 0; i < 200; i++) x = (x << 1) | (x >> 31);
    t3 = systick_elapsed();
    (void)x;

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
    for (int i = 0; i < 500; i++) x = (x << 3) ^ (x >> 5) ^ (uint32_t)i;
    t1 = systick_elapsed();

    /* Sub-stage B: public key load + modular reduction simulation */
    #ifndef GLITCH_ATTACK
        /* Normal execution: full loop */
        for (int i = 0; i < 300; i++) x ^= (x * 31337U) >> 8;
    #else
        /* GLITCH ATTACK: Skip ENTIRE sub-stage B */
        /* Extreme fault: completely bypasses security check */
        /* Creates ~300 cycle reduction (50% severity on sub_b) */
    #endif 


    t2 = systick_elapsed();

    /* Sub-stage C: signature comparison (the critical branch) */
    for (int i = 0; i < 200; i++) x = x ^ (uint32_t)(i * i);
    t3 = systick_elapsed();
    (void)x;

    boot_log[cp_id].sub_a = t1 - t0;
    boot_log[cp_id].sub_b = t2 - t1;
    boot_log[cp_id].sub_c = t3 - t2;
}

static void stage_key_derivation(uint32_t cp_id) {
    uint32_t t0, t1, t2, t3;

    /* Sub-stage A: TRNG read simulation */
    t0 = systick_elapsed();
    volatile uint32_t x = 0xCAFEBABE;
    for (int i = 0; i < 100; i++) x ^= x >> 3;
    t1 = systick_elapsed();

    /* Sub-stage B: KDF mixing */
    for (int i = 0; i < 100; i++) x = (x * 1664525U) + 1013904223U;
    t2 = systick_elapsed();

    /* Sub-stage C: key storage into secure registers */
    for (int i = 0; i < 100; i++) x = x ^ (x << 7) ^ (uint32_t)i;
    t3 = systick_elapsed();
    (void)x;

    boot_log[cp_id].sub_a = t1 - t0;
    boot_log[cp_id].sub_b = t2 - t1;
    boot_log[cp_id].sub_c = t3 - t2;
}

/* ── Main ─────────────────────────────────────────────────────────── */
int main(void)
{
    systick_init();

    uart_init();
    uart_println("=== PMU BOOTROM STUB v0.3 ===");
    uart_println("Counter: SysTick (processor clock, 24-bit)");
    uart_println("Features: elapsed_cycles | sub_a | sub_b | sub_c");
    uart_println("Detector: CUSUM (embedded, real-time)");

    /* Initialize CUSUM detector */
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

    /* Stage 2: signature verify — primary attack target */
    stage_signature_verify(2);
    pmu_checkpoint(2);

    /* ── CHECK FOR ATTACK at CP2 (primary glitch target) ── */
    uint32_t cp2_features[3] = {
        boot_log[2].sub_a,
        boot_log[2].sub_b,
        boot_log[2].sub_c
    };

    /* ── CUSUM Detection ── */
    if (cusum_update(&detector, cp2_features, 2)) {
        uart_println("\r\n!!! ATTACK DETECTED at CP2 !!!");
        uart_print("Mahalanobis distance exceeded threshold");
        uart_println("\r\nHALTING BOOT - Security violation");

        /* Security response: halt and lockup */
        while (1) {
            /* In real system: erase keys, disable peripherals */
        }
    }

    /* Stage 3: key derivation */
    stage_key_derivation(3);
    pmu_checkpoint(3);

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