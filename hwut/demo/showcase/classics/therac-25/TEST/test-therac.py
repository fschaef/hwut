#! /usr/bin/env python3
# @hwut {
#     title    = "Therac-25 (1985-87): an operator's edit against the 8 s magnet setup -- every interleaving"
#     choices {
#         as-delivered { features = ["edit-interleavings", "window-drawn", "overdose-named"]
#                        tolerance { constraints = ["unfired == 0", "window > 0 s"] } }
#         flag-checked { features = ["edit-interleavings", "window-drawn", "never-mismatched"]
#                        tolerance { constraints = ["unfired == 0", "window == 0 s"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  the beam the Therac-25 model fires after one operator edit, for
         every moment of the edit against the setup task, and the window of
         edit times that overdose
HISTORY  Between June 1985 and January 1987 the Therac-25, a computer-
controlled radiation therapy machine of AECL, gave six patients massive
overdoses; several died. Nancy Leveson and Clark Turner's investigation
('An Investigation of the Therac-25 Accidents', IEEE Computer, July 1993)
became the standard case of software in safety-critical systems. In the
East Texas Cancer Center accidents an experienced operator typed 'x'
(X-ray) for a treatment, corrected it to 'e' (electron) with the cursor
keys within about 8 seconds, and pressed 'beam on': the machine fired the
X-ray-level current with the turntable in the electron position. The edit
had come in while the setup task was setting the bending magnets (about
8 s), and the edit flag was cleared without being read. The hardware
interlocks of the older Therac-20 had been removed.

REQUIREMENT  The beam never fires with a current set for one mode and the
             turntable placed for another -- whatever the moment of an edit.

THE UNIT  '../therac.py' -- a model of the three parties (data entry with
its edit, the setup task: read mode -> current -> 8 magnet steps, and the
'beam on' check); AS_DELIVERED clears the edit flag at the end of the magnet
setting unread; the fix looks at it first and starts the setup again.

THE TESTED SPACE: EVERY interleaving of the one edit with the setup task.
Time is a tick of one second, the parties are deterministic_timeline
triggers:
    setup task   fires every tick, priority 2
    beam on      the operator presses at tick 10 and each tick after, prio 5
    the edit     ONE firing at tick e, priority 1 (before the setup's step of
                 that tick) or 3 (after it)
    space_iterator.do([range(11), ["before", "after"]])    -> 22 runs
Ticks 0 .. 10 cover the read (0), the magnet steps (1 .. 7), 'ready' (8)
and the ticks up to the first 'beam on' (10); an edit after the beam has
fired is moot. In a tick the two orders are the only two interleavings of
an atomic edit with the setup's atomic step, so the 22 runs are all
interleavings of one edit in that time.

CHOICES
    as-delivered  every edit that lands after the read and before the setup
                  says ready fires HIGH current at an electron turntable:
                  the overdose; edits before the read or after 'ready' are
                  caught. The window is about 8 s wide, as in the report.
    flag-checked  the same timeline, the same edits: every run fires with a
                  matching current; an edit in the window costs a second
                  setup ('!' then 'S' again).
    Both: '((unfired: 0))' -- every run does fire (law 'unfired == 0'), so
    the fix is not 'never treat'.
    THE WINDOW, a QUANTITY: an edit 'before' the step of tick e lands in
    the second (e-1, e), 'after' it in (e, e+1); the seconds in which an
    edit overdoses add up to '((window: 8 s))' -- the about 8 s of the
    report, now measured on the model and judged in seconds: 'window > 0 s'
    for as-delivered, 'window == 0 s' for flag-checked. The number of
    mismatched runs stays plain, exact text beside it.

HOW TO READ THE GOOD  One run = two lanes over the ticks: 'op' (e the
edit, b 'beam on' pressed but not ready, ? beam on sees an edit, F fired)
and 'setup' (S read mode and set current, m magnet step, R ready, ! the
fix sees the edit). The verdict names current and turntable; '!!' marks a
mismatch. The column of the edit against S..R IS the race. All
'##! verbatim', all exact.
______________________________________________________________________________
"""
import asyncio
import os
import shutil
import sys

sys.path.insert(0, os.path.realpath(os.path.join(
    os.path.dirname(os.path.realpath(shutil.which("hwut"))), "..", "..")))
import hwut.test_writing_support.python.space_iterator as space_iterator
from hwut.test_writing_support.python.deterministic_timeline import Trigger, TriggerDispatcher

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import therac

CHOICE_DB = {"as-delivered": True, "flag-checked": False}
TICKS = 26
BEAM_ON_AT = 10


class Call(Trigger):
    """A trigger that calls 'action(tick)' at each digit of its timeline."""
    def __init__(self, timeline, name, action):
        super().__init__(timeline, name)
        self.action = action

    async def fire(self, tick):
        self.action(tick)


def run(as_delivered, edit_tick, order):
    m = therac.Machine(as_delivered)
    edit_line = " " * edit_tick + ("1" if order == "before" else "3")
    triggers = [Call("2" * TICKS, "setup", m.setup_step),
                Call(" " * BEAM_ON_AT + "5" * (TICKS - BEAM_ON_AT), "beam-on", m.beam_on),
                Call(edit_line, "edit", lambda t: m.edit(t, "E"))]
    asyncio.run(TriggerDispatcher(triggers).run())
    return m


def lane(m, name):
    cells = [" "] * TICKS
    for tick, who, letter in m.log:
        if who == name:
            cells[tick] = letter
    return "".join(cells).rstrip()


def main(choice):
    space = list(space_iterator.do([range(11), ["before", "after"]]))
    print("software: therac.Machine(as_delivered=%s)   first typed: X-ray, edited to: electron"
          % CHOICE_DB[choice])
    print("space: space_iterator over edit tick 0..10 x order {before, after} the setup's step = %d runs"
          % len(space))
    print()
    print("##! verbatim")
    print("run edit        lane  " + "".join(str(t // 10) if t % 10 == 0 else " " for t in range(TICKS)).rstrip())
    print("                      " + "".join(str(t % 10) for t in range(TICKS)))
    fired = mismatched = 0
    lethal = set()                         # seconds (k, k+1) in which an edit overdoses
    for k, (e, order) in enumerate(space):
        m = run(CHOICE_DB[choice], e, order)
        verdict = "did not fire"
        if m.fired:
            fired += 1
            current, table = m.fired
            ok = therac.CURRENT[table] == current
            mismatched += not ok
            if not ok:
                lethal.add(e - 1 if order == "before" else e)
            verdict = "%s current, turntable %s%s" % (current, {"X": "X-ray", "E": "electron"}[table],
                                                      "" if ok else "  !! MISMATCH: overdose")
        print("%3d t=%-2d %-6s op    %-*s  %s" % (k + 1, e, order, TICKS, lane(m, "op"), verdict))
        print("                setup %s" % lane(m, "setup"))
    print("####")
    print("(one column per second, tens on the first ruler line;")
    print(" op: e edit, b beam on not ready, ? beam on sees the edit, F fired;")
    print(" setup: S read + current, m magnets, R ready, ! edit seen)")
    print("runs that never fired: ((unfired: %d))   law == 0   %s"
          % (len(space) - fired, "kept" if fired == len(space) else "BROKEN"))
    print("runs fired with a mismatched mode: %d of %d" % (mismatched, len(space)))
    print("edit times that overdose: ((window: %d s))%s   law == 0 s   %s"
          % (len(lethal), "" if not lethal else ", from t=%d after the setup's step to t=%d before it"
             % (min(lethal), max(lethal) + 1), "kept" if not lethal else "BROKEN"))


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in CHOICE_DB:
        print("choices: %s" % ", ".join(CHOICE_DB))
        sys.exit(1)
    main(choice)
    print("<hwut-end>")
