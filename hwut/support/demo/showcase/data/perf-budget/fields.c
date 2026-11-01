/* fields.c -- split one CSV line in place: count the fields, strip the quotes.
 *
 *     fields REPS < line          prints: "<bytes> bytes <fields> fields <ns> ns"
 *
 * The line is read once; the routine runs REPS times on fresh copies and the
 * fastest run is reported (the least disturbed by the rest of the machine). */
#define _POSIX_C_SOURCE 199309L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

/* count_fields -- commas outside quotes, plus one; quotes become blanks. */
static size_t count_fields(char* s)
{
    size_t n = 1, len = strlen(s);
    int quoted = 0;
    for (size_t i = 0; i < len; i++) {
        if (s[i] == '"')                  { quoted = !quoted; s[i] = ' '; }
        else if (s[i] == ',' && !quoted)  n++;
    }
    return n;
}

int main(int argc, char** argv)
{
    static char line[1 << 22], work[1 << 22];
    int reps = argc > 1 ? atoi(argv[1]) : 1;
    if (!fgets(line, sizeof line, stdin)) return 1;
    line[strcspn(line, "\n")] = '\0';
    size_t len = strlen(line), n = 0;
    long best = -1;
    for (int r = 0; r < reps; r++) {
        struct timespec a, b;
        memcpy(work, line, len + 1);
        clock_gettime(CLOCK_MONOTONIC, &a);
        n = count_fields(work);
        clock_gettime(CLOCK_MONOTONIC, &b);
        long ns = (b.tv_sec - a.tv_sec) * 1000000000L + (b.tv_nsec - a.tv_nsec);
        if (best < 0 || ns < best) best = ns;
    }
    printf("%zu bytes %zu fields %ld ns\n", len, n, best);
    return 0;
}
