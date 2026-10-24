/* bsearch.c -- java.util.Arrays.binarySearch(int[] a, int key), in C with
 * Java's int: 32 bit, two's complement, wrapping (compile with -fwrapv).
 *
 * The array is VIRTUAL: a[i] = i for 0 <= i < n. A real int[2^31 - 1] needs
 * 8 GiB; the algorithm only ever reads a[mid], so a function will do. Like
 * the JVM, the accessor checks the index: outside [0, n) the search ends
 * with ArrayIndexOutOfBoundsException.
 *
 * MIDPOINT selects the line that computes the midpoint (-DMIDPOINT=...):
 *   MID_DIV2  (low + high) / 2                     as in Bloch's post (2006)
 *   MID_USHR  (int)((unsigned)low + (unsigned)high) >> 1     Java's '>>>'
 *   MID_SUB   low + (high - low) / 2
 *
 * stdin:  lines 'n key';  stdout: one line per search
 *   found <index> probes <p>
 *   absent insert <point> probes <p>
 *   AIOOBE index <mid> low <low> high <high> sum <low+high as int> probes <p>
 */
#include <stdio.h>
#include <stdint.h>

#define MID_DIV2 1
#define MID_USHR 2
#define MID_SUB  3

static int32_t n_g;

static int read_a(int32_t i, int32_t* value)
{
    if (i < 0 || i >= n_g) return 0;          /* the JVM's bounds check     */
    *value = i;                               /* a[i] = i                   */
    return 1;
}

static void binary_search(int32_t key)
{
    int32_t low = 0, high = n_g - 1, probes = 0;
    while (low <= high) {
#if   MIDPOINT == MID_DIV2
        int32_t mid = (low + high) / 2;
#elif MIDPOINT == MID_USHR
        int32_t mid = (int32_t)(((uint32_t)low + (uint32_t)high) >> 1);
#elif MIDPOINT == MID_SUB
        int32_t mid = low + (high - low) / 2;
#endif
        int32_t mid_val;
        ++probes;
        if (!read_a(mid, &mid_val)) {
            printf("AIOOBE index %d low %d high %d sum %d probes %d\n",
                   mid, low, high, (int32_t)(low + high), probes);
            return;
        }
        if      (mid_val < key) low  = mid + 1;
        else if (mid_val > key) high = mid - 1;
        else { printf("found %d probes %d\n", mid, probes); return; }
    }
    printf("absent insert %d probes %d\n", low, probes);
}

int main(void)
{
    long long n, key;
    while (scanf("%lld %lld", &n, &key) == 2) {
        n_g = (int32_t)n;
        binary_search((int32_t)key);
    }
    return 0;
}
