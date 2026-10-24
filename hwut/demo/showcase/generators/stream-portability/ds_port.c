/* ds_port.c -- DeterministicStream (hwut test_writing_support) in C, for the
 * firmware side of a test: the target replays the stream the host recorded.
 * usage: ds_port int|gauss SEED N                                        */
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static uint64_t state;

static long long next_int(long long lo, long long hi)
{
    state = (48271u * state) % 2147483647u;
    if (lo == hi) return lo;
    return lo + (long long)(state % (uint64_t)(hi - lo + 1));
}
static double next_float(void) { return next_int(0, 1000000) / 1000001.0; }
static double gauss(double mu, double sigma)
{
    double u1 = next_float() + 1e-9, u2 = next_float();
    double z0 = sqrt(-2.0 * log(u1)) * cos(2.0 * M_PI * u2);
    return z0 * sigma + mu;
}

int main(int argc, char **argv)
{
    long long seed = atoll(argv[2]);
    long n = atol(argv[3]);
    state = (uint64_t)(seed & 0x7FFFFFFF);
    for (long i = 0; i < n; ++i) {
        if (strcmp(argv[1], "int") == 0) printf("%lld\n", next_int(0, 999));
        else                             printf("%.17g\n", gauss(0.0, 1.0));
    }
    return 0;
}
