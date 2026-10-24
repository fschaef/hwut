/* cobs.c -- Consistent Overhead Byte Stuffing for a serial link.
 *
 *     cobs enc < hex-lines        one frame per line, bytes as hex
 *     cobs dec < hex-lines
 *
 * Encoding removes every 0x00 from a frame, so 0x00 can delimit frames on
 * the wire. Each block starts with a code byte: the distance to the next
 * zero (1..254 data bytes + 1), or 0xFF for 254 data bytes and NO zero. */
#include <stdio.h>
#include <string.h>

#define N_MAX 4096

static size_t encode(const unsigned char* in, size_t n, unsigned char* out)
{
    size_t code_at = 0, o = 1;
    unsigned char code = 1;
    for (size_t i = 0; i < n; i++) {
        if (in[i] == 0) {
            out[code_at] = code; code_at = o++; code = 1;
        } else {
            out[o++] = in[i];
            if (++code == 0xFF) { out[code_at] = code; code_at = o++; code = 1; }
        }
    }
    out[code_at] = code;
    return o;
}

static size_t decode(const unsigned char* in, size_t n, unsigned char* out)
{
    size_t i = 0, o = 0;
    while (i < n) {
        unsigned char code = in[i++];
        for (unsigned char k = 1; k < code && i < n; k++) out[o++] = in[i++];
        if (code != 0xFF && i < n) out[o++] = 0;
    }
    return o;
}

int main(int argc, char** argv)
{
    static char          line[3 * N_MAX];
    static unsigned char in[N_MAX], out[N_MAX + N_MAX / 254 + 2];
    int enc = argc > 1 && strcmp(argv[1], "enc") == 0;
    while (fgets(line, sizeof line, stdin)) {
        size_t n = 0; unsigned v; int used; char* p = line;
        while (n < N_MAX && sscanf(p, "%2x%n", &v, &used) == 1) { in[n++] = (unsigned char)v; p += used; }
        size_t m = enc ? encode(in, n, out) : decode(in, n, out);
        for (size_t k = 0; k < m; k++) printf("%02X", out[k]);
        printf("\n");
    }
    return 0;
}
