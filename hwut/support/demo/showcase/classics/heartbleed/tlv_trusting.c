/* tlv_trusting.c -- release 2.3 of tlv.c: trusts the length byte of a record.
 *     record = type (1 byte) | length (1 byte) | value (length bytes)
 * Returns the number of records, or -1 when the block is malformed.
 * The checksum over all values is returned through 'sum'.             */
#include <stddef.h>
#include <stdint.h>

int tlv_walk(const uint8_t *buf, size_t len, unsigned *sum)
{
    const uint8_t *p = buf, *end = buf + len;
    int n = 0;
    *sum = 0;
    while (p < end) {
        if (end - p < 2)            return -1;      /* header cut off */
        size_t vlen = p[1];
        /* (release 2.3: the value length is trusted) */
        for (size_t i = 0; i < vlen; ++i) *sum += p[2 + i];
        p += 2 + vlen;
        ++n;
    }
    return n;
}
