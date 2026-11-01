/* drive.c -- per line 'version words total received type': builds a buffer
 * of exactly 'received' bytes (heap, so a sanitizer sees every overread) and
 * prints the code letter of hdr_check: . V H L T Y                       */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "hdr_check.h"
int main(void)
{
    unsigned v, w, total, received, type;
    while (scanf("%u %u %u %u %u", &v, &w, &total, &received, &type) == 5) {
        uint8_t full[4] = { (uint8_t)(v << 4 | w), (uint8_t)type,
                            (uint8_t)(total >> 8), (uint8_t)total };
        uint8_t *buf = malloc(received ? received : 1);
        memset(buf, 0, received);
        memcpy(buf, full, received < 4 ? received : 4);
        printf("%c\n", ".VHLTY"[hdr_check(buf, received)]);
        free(buf);
    }
    return 0;
}
