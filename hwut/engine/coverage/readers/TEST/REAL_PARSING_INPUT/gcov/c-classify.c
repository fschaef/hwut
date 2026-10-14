#include <stdio.h>
int classify(int n) {
    if (n > 10 && n < 20) return 1;
    if (n < 0) return 2;
    switch (n) { case 3: return 3; case 4: return 4; default: break; }
    return 0;
}
int main(int argc, char **argv) {
    int total = 0;
    for (int i = 0; i < argc * 5; i++) total += classify(i);
    printf("%d\n", total);
    return 0;
}
