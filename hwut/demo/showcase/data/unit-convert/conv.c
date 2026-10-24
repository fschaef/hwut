/* conv.c -- convert pressures between units through a factor table.
 *
 *     conv <table> < requests       request: "<value> <from> <to> [<via>]"
 *
 * The table holds "<unit> <pascal per unit>" lines ('#' comments). A value
 * is converted to <via> (default: Pa) and from there to <to>; prints the
 * result with 17 significant digits, one line per request.             */
#include <stdio.h>
#include <string.h>

static char   name[32][16];
static double factor[32];
static int    n;

static double pa_per(const char* unit)
{
    for (int i = 0; i < n; i++) if (strcmp(name[i], unit) == 0) return factor[i];
    fprintf(stderr, "conv: unknown unit '%s'\n", unit);
    return 0.0 / 0.0;
}

int main(int argc, char** argv)
{
    char line[256], from[16], to[16], via[16];
    double v;
    FILE* fh = argc > 1 ? fopen(argv[1], "r") : NULL;
    if (!fh) { fprintf(stderr, "conv: no table\n"); return 2; }
    while (n < 32 && fgets(line, sizeof line, fh))
        if (line[0] != '#' && sscanf(line, "%15s %lf", name[n], &factor[n]) == 2) n++;
    fclose(fh);
    while (fgets(line, sizeof line, stdin)) {
        int k = sscanf(line, "%lf %15s %15s %15s", &v, from, to, via);
        if (k < 3) continue;
        if (k == 3) strcpy(via, "Pa");
        double mid = v * pa_per(from) / pa_per(via);
        printf("%.17g\n", mid * pa_per(via) / pa_per(to));
    }
    return 0;
}
