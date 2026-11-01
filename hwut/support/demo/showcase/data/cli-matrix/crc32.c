/* crc32.c -- print the CRC-32 (IEEE 802.3) of files.
 *
 *     crc32 [-h|--help] FILE...       '-' is standard input
 *
 * Output: "<8 hex digits>  <name>" per file, on stdout.
 * Errors: "crc32: <what>" on stderr; the other files are still processed.
 * Exit:   0 all files read, 1 a file could not be read, 2 bad command line. */
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>

static const char* USAGE = "Usage: crc32 [-h|--help] FILE...   ('-' reads standard input)\n";

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
    int status = 0, files = 0;
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "-h") == 0 || strcmp(argv[i], "--help") == 0) { fputs(USAGE, stdout); return 0; }
        if (argv[i][0] == '-' && argv[i][1] != '\0') {
            fprintf(stderr, "crc32: unknown option '%s'\n%s", argv[i], USAGE);
            return 2;
        }
    }
    for (int i = 1; i < argc; i++) {
        struct stat st;
        FILE* fh = strcmp(argv[i], "-") == 0 ? stdin : NULL;
        files++;
        if (!fh && stat(argv[i], &st) == 0 && S_ISDIR(st.st_mode)) {
            fprintf(stderr, "crc32: '%s': Is a directory\n", argv[i]); status = 1; continue;
        }
        if (!fh && !(fh = fopen(argv[i], "rb"))) {
            fprintf(stderr, "crc32: cannot open '%s': %s\n", argv[i], strerror(errno)); status = 1; continue;
        }
        printf("%08lX  %s\n", crc_of(fh), argv[i]);
        if (fh != stdin) fclose(fh);
    }
    if (files == 0) { fputs(USAGE, stderr); return 2; }
    return status;
}
