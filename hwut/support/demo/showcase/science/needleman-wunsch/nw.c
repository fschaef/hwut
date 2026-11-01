/* nw.c -- global alignment by Needleman & Wunsch (1970), linear gap cost.
 *
 * usage: nw MATCH MISMATCH GAP [-m]      (scores; GAP is the cost of one gap, e.g. -1)
 * stdin: one pair per line, 'A B'. stdout per pair:
 *     score S
 *     <row A with '-' for gaps>
 *     <'|' where the column is a match>
 *     <row B with '-' for gaps>
 * '-m' also prints the score matrix (B across, A down).
 * Traceback prefers diagonal, then up (gap in B), then left (gap in A).        */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define N 64
static int M[N + 1][N + 1];

static int max3(int a, int b, int c) { int m = a > b ? a : b; return m > c ? m : c; }

static void put_reversed(const char* s, int k)
{
    while( k-- > 0 ) putchar(s[k]);
    putchar('\n');
}

static void align(const char* a, const char* b, int match, int mismatch, int gap, int show)
{
    int n = (int)strlen(a), m = (int)strlen(b), i, j;
    char ra[2 * N + 1], rb[2 * N + 1], bars[2 * N + 1];
    int k = 0;

    M[0][0] = 0;
#ifdef OFF_BY_ONE
    for(i = 1; i <= n; ++i) M[i][0] = (i - 1) * gap;     /* "the first gap is the opening" */
    for(j = 1; j <= m; ++j) M[0][j] = (j - 1) * gap;
#else
    for(i = 1; i <= n; ++i) M[i][0] = i * gap;
    for(j = 1; j <= m; ++j) M[0][j] = j * gap;
#endif
    for(i = 1; i <= n; ++i)
        for(j = 1; j <= m; ++j)
            M[i][j] = max3(M[i-1][j-1] + (a[i-1] == b[j-1] ? match : mismatch),
                           M[i-1][j] + gap, M[i][j-1] + gap);

    if( show ) {
        printf("        -");
        for(j = 0; j < m; ++j) printf("   %c", b[j]);
        printf("\n");
        for(i = 0; i <= n; ++i) {
            printf("    %c", i ? a[i-1] : '-');
            for(j = 0; j <= m; ++j) printf(" %3d", M[i][j]);
            printf("\n");
        }
    }
    i = n; j = m;
    while( i > 0 || j > 0 ) {
        if( i > 0 && j > 0 && M[i][j] == M[i-1][j-1] + (a[i-1] == b[j-1] ? match : mismatch) ) {
            ra[k] = a[i-1]; rb[k] = b[j-1]; bars[k] = a[i-1] == b[j-1] ? '|' : ' '; --i; --j;
        } else if( i > 0 && (j == 0 || M[i][j] == M[i-1][j] + gap) ) {
            ra[k] = a[i-1]; rb[k] = '-'; bars[k] = ' '; --i;
        } else {
            ra[k] = '-'; rb[k] = b[j-1]; bars[k] = ' '; --j;
        }
        ++k;
    }
    printf("score %d\n", M[n][m]);
    put_reversed(ra, k);
    put_reversed(bars, k);
    put_reversed(rb, k);
}

int main(int argc, char** argv)
{
    char a[N + 1], b[N + 1];
    if( argc < 4 ) { fprintf(stderr, "usage: nw MATCH MISMATCH GAP [-m]\n"); return 2; }
    while( scanf("%64s %64s", a, b) == 2 )
        align(a, b, atoi(argv[1]), atoi(argv[2]), atoi(argv[3]), argc > 4);
    return 0;
}
