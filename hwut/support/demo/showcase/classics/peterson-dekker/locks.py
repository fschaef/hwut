"""locks.py -- three entry protocols for two processes 0 and 1, as explicit
STEP MACHINES: step() performs ONE atomic action of one process (a read or a
write of a shared variable), the unit of interleaving. A process's whole
local state is its program counter 'pc'; with the shared variables it makes
the system state, so the state space is finite and can be walked.

    peterson          flag[i] = 1; turn = j; wait while flag[j] and turn == j
                      (G. L. Peterson, 'Myths About the Mutual Exclusion
                      Problem', Information Processing Letters 12(3), 1981)
    turn-first        the same two writes in the other order: turn = j first,
                      then flag[i] = 1
    flag-after-check  the naive lock: wait while flag[j], THEN flag[i] = 1

Each process runs FOREVER: entry protocol -> critical section (one step
inside) -> flag[i] = 0 -> entry protocol again. So a wrong exit protocol
shows in the second and later entries. A waiting process re-reads on each of
its steps. Each step returns a one-letter code for the picture:
    t  wrote turn     f  raised its flag     w  read and waits
    r  read, may go   C  in the critical section    x  lowered its flag
"""


class Shared:
    def __init__(self):
        self.flag = [0, 0]
        self.turn = 0

    def key(self):
        return (self.flag[0], self.flag[1], self.turn)


# program points at which a process is INSIDE (passed its entry, not yet out)
INSIDE = {"peterson": (3, 4), "turn-first": (3, 4), "flag-after-check": (2, 3)}


def step(name, shared, i, pc):
    """RETURN: (next pc, code) -- one atomic action of process i at 'pc'."""
    j = 1 - i
    if name in ("peterson", "turn-first"):
        first, second = (0, 1) if name == "peterson" else (1, 0)
        if pc == first:                                  # raise own flag
            shared.flag[i] = 1
            return pc + 1, "f"
        if pc == second:                                 # give way
            shared.turn = j
            return pc + 1, "t"
        if pc == 2:
            if shared.flag[j] and shared.turn == j:
                return 2, "w"
            return 3, "r"
        if pc == 3:
            return 4, "C"
        shared.flag[i] = 0                               # pc 4: exit
        return 0, "x"
    # flag-after-check
    if pc == 0:
        if shared.flag[j]:
            return 0, "w"
        return 1, "r"
    if pc == 1:
        shared.flag[i] = 1
        return 2, "f"
    if pc == 2:
        return 3, "C"
    shared.flag[i] = 0                                   # pc 3: exit
    return 0, "x"
