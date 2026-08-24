#include <stdio.h>
int doubled(int n) {
    if (n < 0) { return -2 * n; }
    return 2 * n;
}
int never_called(int n) { return n + 1; }
int main(void) { printf("%d\n", doubled(9)); return 0; }
