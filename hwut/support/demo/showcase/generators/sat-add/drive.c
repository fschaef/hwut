/* drive.c -- reads 'a b' pairs from stdin, prints 'a b sat_add(a,b)'. */
#include <stdio.h>
#include <stdint.h>
int32_t sat_add(int32_t a, int32_t b);
int main(void)
{
    long a, b;
    while (scanf("%ld %ld", &a, &b) == 2)
        printf("%ld %ld %ld\n", a, b, (long)sat_add((int32_t)a, (int32_t)b));
    return 0;
}
