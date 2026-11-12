"""Bit-exact Python mirror of the firmware Mahalanobis rule (src/cusum_detector.c), used by
calibrate_firmware.py to set H on the fixed-point distances the firmware computes, and by
validate_firmware.py to predict the firmware's decision for every collected boot."""
import math

INT32_MAX = 2**31 - 1
SUBSTAGE_ALARM_CYCLES = 4096


def to_fixed(x):
    """FLOAT_TO_FIXED: the C literal is a double, times 65536.0f, truncated toward zero."""
    return int(x * 65536.0)


def _i32(v):
    v &= 0xFFFFFFFF
    return v - (1 << 32) if v & 0x80000000 else v


def md_fixed(obs, mu_q, ci_q):
    """mahalanobis_distance(): returns the Q16.16 distance as an integer."""
    delta = [(min(int(o), 32767) << 16) - mu_q[i] for i, o in enumerate(obs)]
    y = [_i32(sum(ci_q[i][j] * delta[j] for j in range(3)) >> 16) for i in range(3)]
    q = sum(delta[i] * y[i] for i in range(3)) >> 16
    q = 0 if q < 0 else min(q, INT32_MAX)
    return math.isqrt(q << 16)


def cusum_alarm(obs, mu_q, ci_q, H_q):
    """cusum_update() on a fresh state (k = 0): one-shot rule, plus the absolute sub-stage ceiling."""
    if any(o > SUBSTAGE_ALARM_CYCLES for o in obs):
        return True
    return md_fixed(obs, mu_q, ci_q) > H_q
