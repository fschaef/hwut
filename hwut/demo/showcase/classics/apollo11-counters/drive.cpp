// drive.cpp -- Verilator test bench for counters.v: one clock per memory
// cycle. Reads one line per cycle from stdin, "T C S" (pulse bits that
// arrived during it), prints one character per cycle for what the cycle did
// ('.' program, '1' TIME1, 'T' CDUT, 'S' CDUS), then a newline and the final
// counter values "time1 cdut cdus".
#include "Vcounters.h"
#include "verilated.h"
#include <cstdio>

int main(int argc, char** argv) {
    Verilated::commandArgs(argc, argv);
    Vcounters* top = new Vcounters;
    const char glyph[4] = {'.', '1', 'T', 'S'};
    top->rst = 1; top->clk = 0; top->eval(); top->clk = 1; top->eval();
    top->rst = 0;
    int t, c, s;
    while (std::scanf("%d %d %d", &t, &c, &s) == 3) {
        top->p_time1 = t; top->p_cdut = c; top->p_cdus = s;
        top->clk = 0; top->eval();
        top->clk = 1; top->eval();
        std::putchar(glyph[top->slot & 3]);
    }
    std::printf("\n%u %u %u\n", (unsigned)top->time1, (unsigned)top->cdut, (unsigned)top->cdus);
    top->final();
    delete top;
    return 0;
}
