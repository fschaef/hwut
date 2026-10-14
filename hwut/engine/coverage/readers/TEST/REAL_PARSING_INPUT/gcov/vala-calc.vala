int doubled (int n) {
    if (n < 0) { return -2 * n; }
    return 2 * n;
}
void main () { stdout.printf ("%d\n", doubled (7)); }
