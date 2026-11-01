/* check.c -- the output-value check of a Bitcoin transaction, as in
 * CheckTransaction() of release 0.3.10 and of release 0.3.11 (August 2010).
 * Values are in satoshi (1 BTC = 100 000 000 satoshi), int64_t as in the
 * client. Compiled with -fwrapv: a sum that overflows wraps, as it did on
 * the x86 machines of 2010.
 *
 * Reads lines 'input output_a output_b' on stdin, prints per line
 * 'accepted' or 'rejected: <reason>'.                                      */
#include <stdint.h>
#include <stdio.h>

#define COIN      100000000LL
#define MAX_MONEY (21000000LL * COIN)

#ifndef RELEASE_0_3_11
/* 0.3.10: every output must not be negative; the outputs together must not
 * exceed the input. The sum is not checked: it may wrap.                  */
static const char *check(int64_t input, const int64_t *out, int n)
{
    int64_t value_out = 0;
    for (int i = 0; i < n; ++i) {
        if (out[i] < 0) return "rejected: negative output";
        value_out += out[i];
    }
    if (value_out > input) return "rejected: outputs exceed input";
    return "accepted";
}
#else
/* 0.3.11: an output above MAX_MONEY is refused, and so is a running sum
 * above MAX_MONEY -- the sum can no longer wrap.                          */
static const char *check(int64_t input, const int64_t *out, int n)
{
    int64_t value_out = 0;
    for (int i = 0; i < n; ++i) {
        if (out[i] < 0)         return "rejected: negative output";
        if (out[i] > MAX_MONEY) return "rejected: output above MAX_MONEY";
        value_out += out[i];
        if (value_out > MAX_MONEY) return "rejected: sum above MAX_MONEY";
    }
    if (value_out > input) return "rejected: outputs exceed input";
    return "accepted";
}
#endif

int main(void)
{
    long long input, a, b;
    while (scanf("%lld %lld %lld", &input, &a, &b) == 3) {
        int64_t out[2] = { a, b };
        printf("%s\n", check(input, out, 2));
    }
    return 0;
}
