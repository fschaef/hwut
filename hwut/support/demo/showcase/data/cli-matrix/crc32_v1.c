/* crc32_v1.c -- release 1.0 of the CRC tool, as scripts met it in the field.
 *     crc32 FILE...                                                          */
#include <stdio.h>
#include <string.h>

static unsigned long crc_of(FILE* fh)
{
    unsigned long crc = 0xFFFFFFFFul;
    int c;
    while ((c = getc(fh)) != EOF) {
        crc ^= (unsigned long)c;
        for (int k = 0; k < 8; k++) crc = (crc >> 1) ^ (0xEDB88320ul & (0ul - (crc & 1ul)));
    }
    return crc ^ 0xFFFFFFFFul;
}

int main(int argc, char** argv)
{
    if (argc < 2 || strcmp(argv[1], "--help") == 0) { printf("usage: crc32 FILE...\n"); return 1; }
    for (int i = 1; i < argc; i++) {
        FILE* fh = fopen(argv[i], "rb");
        if (!fh) { printf("error: %s not found\n", argv[i]); continue; }
        printf("%08lX  %s\n", crc_of(fh), argv[i]);
        fclose(fh);
    }
    return 0;
}
