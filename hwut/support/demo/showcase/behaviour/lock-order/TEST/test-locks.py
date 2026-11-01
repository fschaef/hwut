#! /usr/bin/env python3
# @hwut {
#     title    = "Account locks: one global lock order, checked lockdep-style over real threads"
#     choices {
#         ordered { features = ["money-conserved", "one-order"]
#                   tolerance { constraints = ["total == 300", "cycles == 0"] } }
#         naive   { features = ["money-conserved", "cycle-named"]
#                   tolerance { constraints = ["total == 300", "cycles > 0"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  the lock order the transfer threads were seen to take (held ->
         taken), its cycles, and the money left in the accounts
REQUIREMENT  Locks are taken in one global order (by account name), so no
             set of threads can ever deadlock; and transfers conserve money.

The unit is '../accounts.py': transfers between accounts, one lock each,
with a try-lock-and-back-off that keeps a lock-order mistake from hanging
the process -- and so hides it. Four real threads run against one bank:

    T1  20 x  A -> B  (1 each)        T3  20 x  C -> A  (3 each)
    T2  20 x  B -> C  (2 each)        T4   5 x  audit: locks A, B, C

Every lock event goes, as it happens, into 'lockdep.pype' (the LAW, after
the kernel's lockdep): taking Y while holding X adds the edge X -> Y to a
lock-order graph, and a cycle in the graph is a deadlock waiting for its
moment -- whether or not this run happened to stall. The pype prints the
graph as a matrix (row held, column taken), the edges with the threads that
witnessed them, the cycles, and the final balances.

ordered  '../accounts.py': every mark of the matrix lies above the
         diagonal -- one order, A before B before C. No cycle.
naive    the BROKEN FIXTURE '../accounts_naive.py' (source lock first): the
         mark C -> A falls below the diagonal and closes the ring
         A -> B -> C -> A, named with the thread that holds and takes each
         link. The run itself may or may not have stalled -- the finding is
         the same on every run, which is the point of checking the ORDER
         instead of waiting for the deadlock.

HWUT CONCEPTS  pype (modes RUNNING -> SETTLED) turns a nondeterministic
interleaving into a deterministic graph; the GOOD file compares it exactly.
Two constraint bindings carry the law into hwut's own judgment:
'((total: N))' with 'total == 300' on both choices -- whatever the order of
the transfers, the sum must stay -- and '((cycles: N))' with 'cycles == 0'
for ordered, 'cycles > 0' for naive, so 'hwut.accept' refuses a
re-recording with a cycle, or a naive fixture that no longer shows one. (A
choice that states its own tolerance does not see the header's, so each
choice states 'total == 300'.) 'hwut.run.stability'
agrees on every key. A reviewer reads the matrix: marks below the diagonal
are the bug.
______________________________________________________________________________
"""
import os
import random
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))


class TracedLock:
    """A lock that reports what its users do with it, as they do it."""
    def __init__(self, name, say):
        self.name, self.say, self.lock = name, say, threading.Lock()

    def acquire(self, timeout):
        me = threading.current_thread().name
        if self.lock.acquire(timeout=timeout):
            self.say("%s got %s" % (me, self.name))
            return True
        self.say("%s timed out on %s" % (me, self.name))
        return False

    def release(self):
        self.say("%s released %s" % (threading.current_thread().name, self.name))
        self.lock.release()


def main(choice):
    Bank = __import__("accounts" if choice == "ordered" else "accounts_naive").Bank
    pype = subprocess.Popen(["hwut.pype", os.path.join(HERE, "lockdep.pype")],
                            stdin=subprocess.PIPE, text=True)
    say_lock = threading.Lock()

    def say(text):
        with say_lock:
            pype.stdin.write(text + "\n")
            pype.stdin.flush()

    say("scenario: accounts A, B, C at 100 each; T1 moves 1 A->B, T2 2 B->C, T3 3 C->A, 20 times "
        "each; T4 audits (locks A, B, C) 5 times")
    say("opening total 300")
    bank = Bank({"A": 100, "B": 100, "C": 100}, lambda name: TracedLock(name, say))

    def mover(src, dst, amount):
        for _ in range(20):
            time.sleep(random.uniform(0.0, 0.001))       # think time: interleave
            bank.transfer(src, dst, amount)

    def auditor():
        for _ in range(5):
            time.sleep(random.uniform(0.0, 0.004))
            held = bank._take(["A", "B", "C"])
            sum(bank.balance_db.values())
            for name in reversed(held):
                bank.lock_db[name].release()

    pool = [threading.Thread(target=mover, args=("A", "B", 1), name="T1"),
            threading.Thread(target=mover, args=("B", "C", 2), name="T2"),
            threading.Thread(target=mover, args=("C", "A", 3), name="T3"),
            threading.Thread(target=auditor, name="T4")]
    for thread in pool:
        thread.start()
    for thread in pool:
        thread.join()
    say("threads joined")
    for name in sorted(bank.balance_db):
        say("balance %s %d" % (name, bank.balance_db[name]))
    pype.stdin.close()
    return pype.wait()


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in ("ordered", "naive"):
        print("choices: ordered, naive")
        sys.exit(1)
    sys.exit(main(choice))
