/* hdr_check.c -- first check of a received frame of the sensor bus protocol.
 *
 *   byte 0   version (high nibble) | header length in 32-bit words (low nibble)
 *   byte 1   message type, 1..3
 *   byte 2-3 total length in bytes, big endian (header + payload)
 *
 * Checked in this order; the first failing rule is reported.          */
#include <stddef.h>
#include <stdint.h>
#include "hdr_check.h"

int hdr_check(const uint8_t *buf, size_t received)
{
    if (received < 4)                    return HDR_TRUNCATED;
    unsigned version = buf[0] >> 4;
    unsigned words   = buf[0] & 0x0f;
    unsigned type    = buf[1];
    unsigned total   = ((unsigned)buf[2] << 8) | buf[3];
    if (version != 1)                    return HDR_VERSION;
    if (words < 1)                       return HDR_HDRLEN;
    if (total < words * 4)               return HDR_TOTLEN;
    if (received < total)                return HDR_TRUNCATED;
    if (type < 1 || type > 3)            return HDR_TYPE;
    return HDR_OK;
}
