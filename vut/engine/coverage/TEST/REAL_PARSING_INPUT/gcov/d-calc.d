import std.stdio;
int doubled(int n) {
    if (n < 0) { return -2 * n; }
    return 2 * n;
}
void main() { writeln("answer ", doubled(8)); }
