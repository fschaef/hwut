#include "Vtb.h"
#include "verilated.h"
#include "verilated_cov.h"

int main(int argc, char** argv) {
    VerilatedContext ctx;
    ctx.commandArgs(argc, argv);
    Vtb top{&ctx};
    while (!ctx.gotFinish()) {
        top.eval();
        if (!top.eventsPending()) break;
        ctx.time(top.nextTimeSlot());
    }
    top.final();
    ctx.coveragep()->write("coverage.dat");
    return 0;
}
