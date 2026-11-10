#include <stdio.h>
#include <stdint.h>
#include <math.h>
#include <stdlib.h>
#include "../src/cusum_detector.h"

#define SAT_FLOAT_MD 180.0
#define MD_TOL 0.05

/* Float reference: Mahalanobis distance with the same quantised parameters */
static double fl(const uint32_t o[3]) {
    double d[3], y[3], q = 0;
    for (int i = 0; i < 3; i++) {
        d[i] = (double)(o[i] > 32767u ? 32767u : o[i]) - CUSUM_MODEL.mu[i] / 65536.0;
    }
    for (int i = 0; i < 3; i++) {
        y[i] = 0;
        for (int j = 0; j < 3; j++) {
            y[i] += CUSUM_MODEL.cov_inv[i][j] / 65536.0 * d[j];
        }
    }
    for (int i = 0; i < 3; i++) {
        q += d[i] * y[i];
    }
    return q < 0 ? 0 : sqrt(q);
}

int main(void) {
    int fail = 0;
    srand(12345);
    double maxerr_all = 0, maxerr_below = 0, max_dis_dist = 0;
    long n = 0, disagree = 0, nearthr = 0, saturated = 0;
    double Hf = CUSUM_MODEL.H / 65536.0;

    /* 1: Random observations over a wide range (0..4096) including around the nominal cluster */
    for (long k = 0; k < 3000000; k++) {
        uint32_t o[3];
        int mode = k % 3;
        for (int i = 0; i < 3; i++) {
            o[i] = (uint32_t)(mode == 0 ? rand() % 4097 : mode == 1 ? 400 + rand() % 600 : 560 + rand() % 300);
        }
        double f = fl(o);
        double x = mahalanobis_distance(o, &CUSUM_MODEL) / 65536.0;
        double e = fabs(f - x);
        if (e > maxerr_all) maxerr_all = e;
        if (f < SAT_FLOAT_MD) {
            if (e > maxerr_below) maxerr_below = e;
        } else {
            saturated++;
        }
        n++;
        if (fabs(f - Hf) < MD_TOL) nearthr++;

        cusum_state_t s;
        cusum_init(&s);
        int al = cusum_update(&s, o, 2);
        int ref = (f > Hf);
        if (al != ref) {
            disagree++;
            if (fabs(f - Hf) > max_dis_dist) max_dis_dist = fabs(f - Hf);
        }
    }
    printf("samples %ld  float MD >= %.0f (saturated in fixed point): %ld\n", n, SAT_FLOAT_MD, saturated);
    printf("max |fixed-float| MD error: all samples = %.6f, float MD < %.0f = %.6f\n", maxerr_all, SAT_FLOAT_MD, maxerr_below);
    printf("decision disagreements = %ld, largest |MD-H| among them = %.6f  (samples within +-%.2f of H: %ld)\n", disagree, max_dis_dist, MD_TOL, nearthr);
    if (maxerr_below > MD_TOL) { printf("FAIL: MD error below saturation exceeds %.2f\n", MD_TOL); fail = 1; }
    if (disagree > 0 && max_dis_dist >= MD_TOL) { printf("FAIL: a decision disagreement is %.2f or more from H\n", MD_TOL); fail = 1; }

    /* 2: Extremes must ALARM (fail-closed) */
    uint32_t ex[][3] = {
        {0, 0, 0}, {0, 500, 500}, {4097, 500, 500}, {500, 4097, 500}, {500, 500, 4097},
        {32767, 32767, 32767}, {32768, 0, 0}, {65535, 65535, 65535}, {0xFFFFFFFFu, 0, 0},
        {0xFFFFFF00u, 0xFFFFFF00u, 0xFFFFFF00u}, {0x80000000u, 0x80000000u, 0x80000000u}, {4096, 4096, 4096}
    };
    for (unsigned i = 0; i < sizeof ex / sizeof ex[0]; i++) {
        cusum_state_t s;
        cusum_init(&s);
        int al = cusum_update(&s, ex[i], 2);
        double mdfixed = mahalanobis_distance(ex[i], &CUSUM_MODEL) / 65536.0;
        double mdfloat = fl(ex[i]);
        printf("obs {%u,%u,%u}: alarm=%d  MDfixed=%.3f MDfloat=%.3f\n", ex[i][0], ex[i][1], ex[i][2], al, mdfixed, mdfloat);
        if (!al) { printf("FAIL: extreme input did not alarm\n"); fail = 1; }
    }

    /* 3: MD-only path (no 4096 auto-alarm) must saturate not wrap, for large values */
    uint32_t big[][3] = {{10000, 10000, 10000}, {32767, 0, 32767}, {40000, 0, 0}, {0xFFFFFFFFu, 0xFFFFFFFFu, 0xFFFFFFFFu}};
    for (unsigned i = 0; i < 4; i++) {
        double md = mahalanobis_distance(big[i], &CUSUM_MODEL) / 65536.0;
        printf("MD-only {%u,%u,%u} = %.2f\n", big[i][0], big[i][1], big[i][2], md);
        if (fabs(md - 181.02) > 0.01) { printf("FAIL: MD did not saturate at 181.02\n"); fail = 1; }
    }

    /* 4: sqrt exactness vs libm over full range */
    long bad = 0;
    double me = 0;
    for (long k = 0; k < 2000000; k++) {
        int32_t x = (int32_t)(((uint64_t)rand() << 16 ^ rand()) & 0x7FFFFFFF);
        double r = fixed_sqrt(x) / 65536.0;
        double t = sqrt(x / 65536.0);
        double e = fabs(r - t);
        if (e > me) me = e;
        if (e > 1.0 / 65536.0 + 1e-9) bad++;
    }
    printf("fixed_sqrt: max err %.7f (1 LSB=%.7f) over 2e6 values, >1LSB: %ld ; sqrt(0)=%d sqrt(-5)=%d sqrt(INT32_MAX)=%.4f\n", me, 1.0 / 65536, bad, fixed_sqrt(0), fixed_sqrt(-5), fixed_sqrt(INT32_MAX) / 65536.0);
    if (bad != 0) { printf("FAIL: fixed_sqrt exceeds 1 LSB\n"); fail = 1; }

    /* 5: State reuse: the alarm stays latched; calls are sequenced explicitly */
    cusum_state_t s;
    cusum_init(&s);
    uint32_t hi[3] = {500, 5000, 500};
    uint32_t ok[3] = {695, 583, 502};
    int first = cusum_update(&s, hi, 2);
    int second = cusum_update(&s, ok, 2);
    printf("latched: first=%d then clean=%d (expect 1 then 1)\n", first, second);
    if (first != 1 || second != 1) { printf("FAIL: alarm did not latch\n"); fail = 1; }
    cusum_init(&s);
    int al_ok = cusum_update(&s, ok, 2);
    printf("clean-center obs alarm=%d S=%.3f\n", al_ok, s.S / 65536.0);
    if (al_ok) { printf("FAIL: clean-center observation alarmed\n"); fail = 1; }

    printf(fail ? "FAIL\n" : "PASS\n");
    return fail;
}
