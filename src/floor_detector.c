#include "floor_detector.h"

const uint16_t FLOOR_TABLE[FLOOR_NUM_CP][3] = {
#include "floor_table.h"
};

uint8_t floor_check(uint32_t cp, const uint32_t sub[3]) {
    if (cp >= FLOOR_NUM_CP) return 1;
    for (int i = 0; i < 3; i++) {
        if (sub[i] < FLOOR_TABLE[cp][i]) return 1;
    }
    return 0;
}
