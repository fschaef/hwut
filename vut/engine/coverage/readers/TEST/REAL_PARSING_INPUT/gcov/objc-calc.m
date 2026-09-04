#include <stdio.h>
int doubled(int n) {
    if (n < 0) { return -2 * n; }
    return 2 * n;
}
int main(void) { printf("%d\n", doubled(6)); return 0; }
