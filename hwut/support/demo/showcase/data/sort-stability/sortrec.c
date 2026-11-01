/* sortrec.c -- sort CSV records "name,key" by key, in one of two ways.
 *
 *     sortrec merge < records      a merge sort written for this program
 *     sortrec qsort < records      the C library's qsort()
 *
 * Both compare the key only (the text after the first comma). */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define LINE_MAX_N 100000
static char* line[LINE_MAX_N];
static char* tmp[LINE_MAX_N];

static const char* key_of(const char* s)
{ const char* c = strchr(s, ','); return c ? c + 1 : s; }

static int cmp_key(const char* a, const char* b)
{ return strcmp(key_of(a), key_of(b)); }

static int cmp_qsort(const void* a, const void* b)
{ return cmp_key(*(char* const*)a, *(char* const*)b); }

static void merge_sort(char** v, size_t n)
{
    if (n < 2) return;
    size_t h = n / 2, i = 0, j = h, k = 0;
    merge_sort(v, h);
    merge_sort(v + h, n - h);
    while (i < h && j < n) tmp[k++] = cmp_key(v[j], v[i]) < 0 ? v[j++] : v[i++];
    while (i < h) tmp[k++] = v[i++];
    while (j < n) tmp[k++] = v[j++];
    memcpy(v, tmp, n * sizeof(char*));
}

int main(int argc, char** argv)
{
    char   buf[256];
    size_t n = 0;
    while (n < LINE_MAX_N && fgets(buf, sizeof buf, stdin)) line[n++] = strdup(buf);
    if (argc > 1 && strcmp(argv[1], "qsort") == 0) qsort(line, n, sizeof(char*), cmp_qsort);
    else                                            merge_sort(line, n);
    for (size_t i = 0; i < n; i++) fputs(line[i], stdout);
    return 0;
}
