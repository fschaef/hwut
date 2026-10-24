#! /usr/bin/env python3
# @hwut {
#     title    = "Two withdrawals race on one account: interleavings drawn as timeline strings"
#     features = ["drawn-interleaving"]
#     choices {
#         locked   { features = ["drawn-interleaving", "all-schedules", "money-conserved"]
#                    tolerance { constraints = ["breaches == 0"] } }
#         unlocked { features = ["drawn-interleaving", "all-schedules", "lost-update-named"]
#                    tolerance { constraints = ["breaches > 0"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  the cash paid and the final balance of ../account.py in every
         interleaving of two withdrawals
REQUIREMENT  However two withdrawals interleave, the cash dispensed plus the
             final balance equals the opening balance, and the balance
             never goes below zero (opening 100; A withdraws 80, B 50:
             exactly one of them may be paid).

The unit is '../account.py': a withdrawal as a generator of atomic steps
(begin/lock, read, check, write or refuse, end/unlock). 'withdraw_unlocked'
is check-then-act as first written; 'withdraw_locked' takes the account's
lock first (a step that finds it taken yields 'wait' and does not advance).

THE GENERATOR INSTRUCTIONS are four timeline strings per task, handed to
hwut's deterministic_timeline.TriggerDispatcher: a digit at position t
means "this task performs its next step at tick t"; within one tick the
lower digit goes first, equal digits in registration order (A before B).
A race is DRAWN, not provoked by sleeping and hoping:

    serial       A = "11111     "   B = "     11111"
    interleaved  A = "1111111111"   B = "1111111111"   A first in each tick
    B wins ties  A = "2222222222"   B = "1111111111"   B first in each tick
    staggered    A = "1 1 1 1 1 1 1 1 1"   B = " 1 1 1 1 1 1 1 1 1"

Serial is the reference; the other three place B's read between A's read
and A's write -- the window of check-then-act. Every task has spare ticks,
so a waiting task can still finish. The same four timelines run against
both units: the timeline is the scenario, the unit is what varies.

DRAWN TIMELINES ARE HIGHLIGHTS, NOT THE SPACE. Four hand-drawn timelines
miss what nobody thought of: a lock released one step before the write
lets B read in that window, and none of the four puts B there. So the
test also ENUMERATES every schedule: every order in which the two tasks
can take their steps (a word like 'AAABBAABBB', one letter per step),
except that a task which just waited is not scheduled again before the
other one moved -- it could only wait again. The invariant is judged in
each; the count of schedules that break it is bound as '((breaches: N))'
and the first one is drawn as a fifth lane picture, its word turned into
timeline strings.

THE STEPS ARE A MODEL: the withdrawals are generators stepped by one
thread in the dispatcher's (or the word's) order -- no real threads, no
real lock; the test proves the step model of the code, not the OS.

locked     every timeline pays exactly one withdrawal; B waits while A
           holds the lock (or the other way round). All 32 schedules keep
           the invariant: law 'breaches == 0'.
unlocked   serial pays one; the three racing timelines pay BOTH: 130 cash
           from 100, the second write overwrites the first (lost update).
           200 of the 252 schedules do so: law 'breaches > 0'.

HOW TO READ THE GOOD   One lane picture per timeline ('##! verbatim':
a step's column is its tick): the drawn strings, then per tick the step
each task performed and the balance after the tick. Under it the
bookkeeping and the verdict. Read across a lane pair: where both 'read 100'
come before the first 'write', the race is open. All exact: there are no
threads; the dispatcher's order is the only order. The breach count is a
binding, judged by the law.
______________________________________________________________________________
"""
import asyncio
import os
import shutil
import sys

sys.path.insert(0, os.path.realpath(os.path.join(
    os.path.dirname(os.path.realpath(shutil.which("hwut"))), "..", "..")))
from hwut.test_writing_support.python.deterministic_timeline import Trigger, TriggerDispatcher

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import account as unit

OPENING = 100
TASKS = [("A", 80), ("B", 50)]
TIMELINES = [
    ("serial",      "11111     ",          "     11111"),
    ("interleaved", "1111111111",          "1111111111"),
    ("B wins ties", "2222222222",          "1111111111"),
    ("staggered",   "1 1 1 1 1 1 1 1 1",   " 1 1 1 1 1 1 1 1 1"),
]
CHOICE_DB = {"locked": unit.withdraw_locked, "unlocked": unit.withdraw_unlocked}
W = 10


class StepTrigger(Trigger):
    """Performs the task's next atomic step when its digit comes up."""
    def __init__(self, timeline, name, steps, log):
        super().__init__(timeline, name)
        self.steps, self.log, self.done, self.last = steps, log, False, None

    async def fire(self, tick):
        if self.done:
            return
        try:
            self.last = next(self.steps)
            self.log.append((tick, self.name, self.last))
        except StopIteration:
            self.done = True


def run_timeline(withdraw, title, lines):
    account = unit.Account(OPENING)
    log, balance_at = [], {}
    triggers = [StepTrigger(line, name, withdraw(account, name, amount), log)
                for (name, amount), line in zip(TASKS, lines)]

    class Bookkeeper(Trigger):           # digit 9 in every tick: after the tasks
        async def fire(self, tick):
            balance_at[tick] = account.balance
    end = max(len(l) for l in lines)
    asyncio.run(TriggerDispatcher(triggers + [Bookkeeper("9" * end, "books")]).run())

    print("timeline '%s'" % title)
    for (name, amount), line in zip(TASKS, lines):
        print('    %s = "%s"   withdraw %d' % (name, line, amount))
    print("##! verbatim")
    used = sorted(set(t for t, _, _ in log))
    gaps = used != list(range(used[0], used[-1] + 1))
    print("  tick     " + "".join("%-*d" % (W, t) for t in used).rstrip()
          + ("   (ticks without a step omitted)" if gaps else ""))
    for name, amount in TASKS:
        cell = dict((t, s) for t, n, s in log if n == name)
        print(("  %s(%d)    " % (name, amount) + "".join("%-*s" % (W, cell.get(t, "")) for t in used)).rstrip())
    print("  balance  " + "".join("%-*d" % (W, balance_at[t]) for t in used).rstrip())
    print("####")
    paid = sum(a for _, a in account.dispensed)
    unfinished = [t.name for t in triggers if not t.done and t.last not in ("end", "unlock")]
    print("    paid: %s   cash out %d + balance %d = %d   (opening %d)"
          % (", ".join("%s %d" % d for d in account.dispensed) or "nobody",
             paid, account.balance, paid + account.balance, OPENING))
    broken = []
    if paid + account.balance != OPENING:
        broken.append("%d appeared from nowhere: a write overwrote another (lost update)"
                      % (paid + account.balance - OPENING))
    if account.balance < 0:
        broken.append("balance below zero")
    if unfinished:
        broken.append("unfinished: %s" % ", ".join(unfinished))
    for b in broken:
        print("    !! %s" % b)
    print("    invariant: %s" % ("kept" if not broken else "BROKEN"))
    print()
    return not broken


def schedules(start):
    """Every order in which the tasks of start() can take their steps.
    start() -> (world, [(name, generator)]); yields (word, world, stuck).
    A generator cannot be copied, so each prefix is replayed from scratch."""
    names = [n for n, _ in start()[1]]

    def replay(word):
        world, tasks = start()
        gens, last = dict(tasks), {}
        for ch in word:
            last[ch] = next(gens[ch])
        return world, gens, last

    def explore(word, finished):
        _, _, last = replay(word)
        moved = False
        for n in names:
            if n in finished or (word.endswith(n) and last.get(n) == "wait"):
                continue                      # done, or it would only wait again
            _, gens, _ = replay(word)
            if next(gens[n], None) is None:
                finished = finished | {n}
                continue
            moved = True
            yield from explore(word + n, finished)
        if not moved:
            world, gens, _ = replay(word)
            yield word, world, [n for n in names if next(gens[n], None) is not None]

    yield from explore("", frozenset())


def breaks(account, stuck):
    paid = sum(a for _, a in account.dispensed)
    return paid + account.balance != OPENING or account.balance < 0 or stuck


def main(choice):
    withdraw = CHOICE_DB[choice]
    print("unit: account.%s, opening balance %d" % (withdraw.__name__, OPENING))
    print("schedule strings: position = tick; a digit = the task takes its next atomic step")
    print("in that tick, lower digit first, equal digits A before B; blank = no step")
    print()
    kept = [run_timeline(withdraw, title, lines) for title, *lines in TIMELINES]
    print("drawn timelines: %d, invariant kept: %d, broken: %d" % (len(kept), sum(kept), len(kept) - sum(kept)))
    print()

    def start():
        account = unit.Account(OPENING)
        return account, [(name, withdraw(account, name, amount)) for name, amount in TASKS]
    every = list(schedules(start))
    broken = [word for word, account, stuck in every if breaks(account, stuck)]
    print("every schedule, enumerated: %d (every order of the two tasks' steps; a task" % len(every))
    print("  that could only wait again is not rescheduled), invariant kept: %d" % (len(every) - len(broken)))
    print("schedules breaking the invariant ((breaches: %d))   law == 0   %s"
          % (len(broken), "kept" if not broken else "BROKEN"))
    if broken:
        word = broken[0]
        print()
        run_timeline(withdraw, "first broken schedule %s" % word,
                     ["".join("1" if c == name else " " for c in word) for name, _ in TASKS])


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in CHOICE_DB:
        print("choices: %s" % ", ".join(CHOICE_DB))
        sys.exit(1)
    main(choice)
    print("<hwut-end>")
