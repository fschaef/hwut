/* triangle_int.c -- Myers' triangle program, sums in int: a + b overflows.
 * Reads lines 'a b c' (int), prints one word per line:
 * invalid | equilateral | isosceles | scalene                              */
#include <stdio.h>

static const char* classify(int a, int b, int c)
{
    int x = a, y = b, z = c;                /* sums in int: MAX + MAX wraps */
    if (a <= 0 || b <= 0 || c <= 0)              return "invalid";
    if (x + y <= z || x + z <= y || y + z <= x)  return "invalid";
    if (a == b && b == c)                        return "equilateral";
    if (a == b || b == c || a == c)              return "isosceles";
    return "scalene";
}

int main(void)
{
    int a, b, c;
    while (scanf("%d %d %d", &a, &b, &c) == 3) puts(classify(a, b, c));
    return 0;
}
