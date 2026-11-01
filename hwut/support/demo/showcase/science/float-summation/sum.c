/* sum.c -- summing doubles in different orders.
 *
 * usage: sum orders            < values      one result per order
 *        sum parallel W        < values      W threads, each sums a chunk; the
 *                                            partials are added to the total in
 *                                            the order the workers FINISH
 * values: one double per line, any strtod() syntax (hex floats keep every bit).
 * Results are printed with %.17g (round-trips a double).                        */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <pthread.h>

static double* x;
static long    n;

static double naive(const double* v, long m) { double s = 0; long i; for(i = 0; i < m; ++i) s += v[i]; return s; }

/* sum_accurate -- Kahan's compensated summation (Kahan 1965): 'c' carries the
 * low-order bits each addition loses, and feeds them into the next one.      */
static double sum_accurate(const double* v, long m)
{
    double s = 0, c = 0;
    long   i;
    for(i = 0; i < m; ++i) {
        double y = v[i] - c;
        double t = s + y;
        c = (t - s) - y;
        s = t;
    }
    return s;
}

static double pairwise(const double* v, long m)
{
    if( m <= 8 ) return naive(v, m);
    return pairwise(v, m / 2) + pairwise(v + m / 2, m - m / 2);
}

static int by_magnitude(const void* a, const void* b)
{
    double p = fabs(*(const double*)a), q = fabs(*(const double*)b);
    return p < q ? -1 : p > q;
}

static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
static double total;
static long   chunk_n, workers;

static void* worker(void* arg)
{
    long   k = (long)arg, a = k * chunk_n, b = k == workers - 1 ? n : a + chunk_n;
    double partial = naive(x + a, b - a);
    pthread_mutex_lock(&lock);
    total += partial;                                        /* arrival order */
    printf("worker %ld [%ld, %ld) partial %.17g\n", k, a, b, partial);
    fflush(stdout);
    pthread_mutex_unlock(&lock);
    return 0;
}

int main(int argc, char** argv)
{
    long   cap = 1024, i;
    char   line[128];
    x = malloc(cap * sizeof(double));
    while( fgets(line, sizeof line, stdin) ) {
        if( n == cap ) x = realloc(x, (cap *= 2) * sizeof(double));
        x[n++] = strtod(line, 0);
    }
    if( argc > 1 && strcmp(argv[1], "orders") == 0 ) {
        double* y = malloc(n * sizeof(double));
        printf("forward %.17g\n", naive(x, n));
        for(i = 0; i < n; ++i) y[i] = x[n - 1 - i];
        printf("backward %.17g\n", naive(y, n));
        memcpy(y, x, n * sizeof(double));
        qsort(y, n, sizeof(double), by_magnitude);
        printf("ascending %.17g\n", naive(y, n));
        for(i = 0; i < n / 2; ++i) { double t = y[i]; y[i] = y[n - 1 - i]; y[n - 1 - i] = t; }
        printf("descending %.17g\n", naive(y, n));
        printf("pairwise %.17g\n", pairwise(x, n));
        printf("accurate %.17g\n", sum_accurate(x, n));
        return 0;
    }
    if( argc > 2 && strcmp(argv[1], "parallel") == 0 ) {
        pthread_t t[64];
        workers = atol(argv[2]);
        chunk_n = n / workers;
        for(i = 0; i < workers; ++i) pthread_create(&t[i], 0, worker, (void*)i);
        for(i = 0; i < workers; ++i) pthread_join(t[i], 0);
        printf("total %.17g\n", total);
        return 0;
    }
    fprintf(stderr, "usage: sum orders | sum parallel W   < values\n");
    return 2;
}
