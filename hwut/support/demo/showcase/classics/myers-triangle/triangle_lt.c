/* triangle_lt.c -- Myers' triangle program, the textbook slip: "<" where "<=" is meant.
 * Reads lines 'a b c' (int), prints one word per line:
 * invalid | equilateral | isosceles | scalene                              */
#include <stdio.h>

static const char* classify(int a, int b, int c)
{
    long long x = a, y = b, z = c;          /* sums in 64 bit: no overflow */
    if (a <= 0 || b <= 0 || c <= 0)              return "invalid";
    if (x + y <  z || x + z <  y || y + z <  x)  return "invalid";  /* a+b == c passes */
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
