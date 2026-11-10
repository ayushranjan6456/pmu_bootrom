/*
 * cusum_detector.h
 * ================
 * Firmware-embedded CUSUM fault injection detector for PMU telemetry.
 *
 * Uses fixed-point Q16.16 arithmetic (no floating-point operations).
 * Detects timing anomalies in boot stages using Mahalanobis distance
 * and CUSUM sequential change detection.
 *
 * Part of: PMU-Based Statistical Detection of FI Attacks in Secure Boot
 * Phase: 1 (QEMU Simulation)
 * Date: November 2026
 * Results: see STATUS.md
 */

#ifndef CUSUM_DETECTOR_H
#define CUSUM_DETECTOR_H

#include <stdint.h>

/* ──────────────────────────────────────────────────────────────────────
 * FIXED-POINT Q16.16 FORMAT
 * ──────────────────────────────────────────────────────────────────────
 * Signed 32-bit: 16 bits integer, 16 bits fractional
 * Range: -32768.0 to +32767.99998
 * Precision: 1/65536 ≈ 0.000015
 *
 * Example: 1.5 = 0x00018000 = 98304
 */
typedef int32_t fixed_t;

/* Convert float to Q16.16 at compile time (for model parameters) */
#define FLOAT_TO_FIXED(x)   ((fixed_t)((x) * 65536.0f))

/* Any single sub-stage above this many cycles is an automatic alarm (the
 * largest sub-stage in the clean training data is 934 cycles). */
#define SUBSTAGE_ALARM_CYCLES   4096U

/* Convert int to Q16.16 */
static inline fixed_t int_to_fixed(int32_t x) {
    return x << 16;
}

/* ──────────────────────────────────────────────────────────────────────
 * CUSUM DETECTOR MODEL
 * ──────────────────────────────────────────────────────────────────────
 * Contains calibrated parameters from Python training:
 *   - mu: mean vector (3D) for CP2 features [sub_a, sub_b, sub_c]
 *   - cov_inv: inverse covariance matrix (3x3, symmetric)
 *   - k_slack: CUSUM slack parameter (0 for the one-shot configuration)
 *   - H: alarm threshold (with k_slack = 0, alarm when MD > H)
 */
typedef struct {
    fixed_t mu[3];              /* Mean vector */
    fixed_t cov_inv[3][3];      /* Inverse covariance (symmetric) */
    fixed_t k_slack;            /* CUSUM slack parameter */
    fixed_t H;                  /* Alarm threshold */
} cusum_model_t;

/* ──────────────────────────────────────────────────────────────────────
 * CUSUM DETECTOR STATE
 * ──────────────────────────────────────────────────────────────────────
 * Runtime state for sequential change detection.
 * Initialize once at boot, update at each checkpoint.
 */
typedef struct {
    fixed_t S;                  /* CUSUM statistic (accumulator) */
    uint8_t alarm;              /* 1 = attack detected, 0 = clean */
    uint32_t alarm_cp;          /* Checkpoint index where alarm fired */
} cusum_state_t;

/* ──────────────────────────────────────────────────────────────────────
 * GLOBAL MODEL (EMBEDDED IN FLASH)
 * ──────────────────────────────────────────────────────────────────────
 * Trained model parameters from Python, converted to fixed-point.
 * Defined in cusum_detector.c, declared here as extern.
 */
extern const cusum_model_t CUSUM_MODEL;

/* ──────────────────────────────────────────────────────────────────────
 * API FUNCTIONS
 * ──────────────────────────────────────────────────────────────────────
 */

/*
 * Initialize CUSUM detector state.
 * Call once at boot start (before any checkpoints).
 *
 * Args:
 *   state: Pointer to detector state (will be zeroed)
 */
void cusum_init(cusum_state_t *state);

/*
 * Update CUSUM detector with new observation.
 * Call after each checkpoint to check for anomalies.
 *
 * Args:
 *   state: Pointer to detector state
 *   obs: Feature vector [sub_a, sub_b, sub_c] from checkpoint
 *   cp_id: Checkpoint index (for alarm logging)
 *
 * Returns:
 *   1 if attack detected (alarm fired)
 *   0 if observation is consistent with nominal behavior
 *
 * Side effects:
 *   - Updates state->S (CUSUM statistic)
 *   - Sets state->alarm = 1 if S exceeds threshold
 *   - Records state->alarm_cp if alarm fires
 */
uint8_t cusum_update(cusum_state_t *state,
                     const uint32_t obs[3],
                     uint32_t cp_id);

/*
 * Compute Mahalanobis distance: sqrt((x-mu)' * cov_inv * (x-mu))
 * Measures how many standard deviations the observation is from mean.
 *
 * Args:
 *   obs: Feature vector [sub_a, sub_b, sub_c]
 *   model: Detector model (mu, cov_inv)
 *
 * Returns:
 *   Mahalanobis distance in Q16.16 fixed-point
 *
 * Note: Uses integer square root approximation (no float ops)
 */
fixed_t mahalanobis_distance(const uint32_t obs[3],
                              const cusum_model_t *model);

/*
 * Integer square root using binary search.
 * Returns sqrt(x) in Q16.16 format.
 *
 * Args:
 *   x: Input value in Q16.16 format (must be >= 0)
 *
 * Returns:
 *   sqrt(x) in Q16.16 format
 *
 * Accuracy: Error < 0.001 for typical PMU values
 */
fixed_t fixed_sqrt(fixed_t x);

#endif /* CUSUM_DETECTOR_H */
