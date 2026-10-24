#! /usr/bin/env python3
# @hwut {
#     title    = "Double-checked lazy init: one digit of a timeline decides whether a reader sees half an object"
#     features = ["priority-drawn"]
#     choices {
#         publish-late  { features = ["priority-drawn", "all-schedules", "whole-object", "built-once"]
#                         tolerance { constraints = ["breaches == 0"] } }
#         publish-early { features = ["priority-drawn", "all-schedules", "half-object-named", "built-once"]
#                         tolerance { constraints = ["breaches > 0"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  what each caller of get_config() (../config_holder.py) reads, in
         every schedule of two callers
REQUIREMENT  Every caller of get_config() reads a completely initialised
             configuration (port 8080), and the configuration is built
             exactly once, however the calls interleave.

The unit is '../config_holder.py': double-checked locking cut into atomic
steps (chk1, lock, chk2, build/publish/fill, unlock, use). 'get_publish_early'
assigns the shared reference before filling the object -- what a compiler
or CPU may do to 'instance = new Config()' without a barrier;
'get_publish_late' fills a local object and publishes it last.

THE GENERATOR INSTRUCTIONS -- timeline strings, and here the PRIORITY digit
is the point. Two triggers with a digit in the same tick fire lower digit
first:

    reader long after      W = "1111111"          R = "        11"
    reader in the window   W = "1111111"          R = "   2222222222"
      init goes first        tick 4: W(1) before R(2)
    reader in the window   W = "1111111"          R = "   2022222222"
      reader goes first      tick 4: R(0) before W(1) -- ONE digit changed
    two initialisers       W = "1111111111"  V = "2222222222"  R = "   0000000000"

Rows 2 and 3 differ in a single character. That character is the race: in
row 3 the reader's 'use' slips between the writer's 'publish' and 'fill'.
A sleep-based test can only hope for that placement; a timeline string
states it, and the GOOD shows it.

DRAWN TIMELINES ARE HIGHLIGHTS, NOT THE SPACE. A window nobody drew stays
untested: release the lock one step before 'publish', and a second
initialiser that takes the lock in between builds the object again -- the
four drawn rows never put it there. So the test also ENUMERATES every
schedule of two callers A and B: every order in which their steps can
come (a word like 'AABAB...', one letter per step), except that a caller
which just waited is not scheduled again before the other one moved -- it
could only wait again. Every caller runs the same get_config, so two
callers cover both roles, initialiser and reader. The count of schedules
that break the requirement is bound as '((breaches: N))'; the first one is
drawn as a fifth lane picture, its word turned into timeline strings.

THE STEPS ARE A MODEL: the callers are generators stepped by one thread in
the dispatcher's (or the word's) order -- no real threads, no real memory
model; 'publish' before 'fill' is written into the unit to stand for the
reordering a compiler or CPU may do.

publish-late   the reader that comes in the window finds 'none', takes the
               lock path and waits; everybody reads 8080; built once. No
               schedule breaks it: law 'breaches == 0'.
publish-early  rows 1, 2, 4 are fine; row 3 reads 'use None': half an
               object, named in the verdict. The enumeration counts every
               schedule that does so: law 'breaches > 0'.

HOW TO READ THE GOOD   One lane picture per timeline ('##! verbatim': a
step's column is its tick): what each caller did at each tick. Under it:
what each caller read, how often the object was built, the verdict.
All exact -- no threads, no clock; the dispatcher's order is the order.
The breach count is a binding, judged by the law.
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
import config_holder as unit

TIMELINES = [
    ("reader long after",                        [("W", "1111111"), ("R", "        11")]),
    ("reader in the window, init goes first",    [("W", "1111111"), ("R", "   2222222222")]),
    ("reader in the window, reader goes first",  [("W", "1111111"), ("R", "   2022222222")]),
    ("two initialisers and a reader",            [("W", "1111111111"), ("V", "2222222222"),
                                                  ("R", "   0000000000")]),
]
CHOICE_DB = {"publish-late": unit.get_publish_late, "publish-early": unit.get_publish_early}
W = 11


class StepTrigger(Trigger):
    def __init__(self, timeline, name, steps, log):
        super().__init__(timeline, name)
        self.steps, self.log, self.finished = steps, log, False

    async def fire(self, tick):
        if self.finished:
            return
        step = next(self.steps, None)
        if step is None:
            self.finished = True
        else:
            self.log.append((tick, self.name, step))
            self.finished = step.startswith("use")


def run_timeline(get_config, title, lanes):
    holder, log = unit.Holder(), []
    triggers = [StepTrigger(line, name, get_config(holder, name), log) for name, line in lanes]
    asyncio.run(TriggerDispatcher(triggers).run())
    print("timeline '%s'" % title)
    for name, line in lanes:
        print('    %s = "%s"' % (name, line))
    print("##! verbatim")
    used = sorted(set(t for t, _, _ in log))
    gaps = used != list(range(used[0], used[-1] + 1))
    print("  tick  " + "".join("%-*d" % (W, t) for t in used).rstrip()
          + ("   (ticks without a step omitted)" if gaps else ""))
    for name, _ in lanes:
        cell = dict((t, s) for t, n, s in log if n == name)
        print(("  %-4s  " % name + "".join("%-*s" % (W, cell.get(t, "")) for t in used)).rstrip())
    print("####")
    print("    read: %s   built: %d" % (", ".join("%s %s" % s for s in holder.seen), holder.built))
    broken = ["%s read port %s: a half-initialised object" % (who, port)
              for who, port in holder.seen if port != 8080]
    if holder.built != 1:
        broken.append("built %d times" % holder.built)
    broken += ["%s never got its configuration" % t.name for t in triggers if not t.finished]
    for b in broken:
        print("    !! " + b)
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


def main(choice):
    get_config = CHOICE_DB[choice]
    print("unit: config_holder.%s" % get_config.__name__)
    print("schedule strings: position = tick; a digit = the caller takes its next atomic step")
    print("in that tick, lower digit first (0 before 1 before 2); blank = no step")
    print()
    kept = [run_timeline(get_config, title, lanes) for title, lanes in TIMELINES]
    print("drawn timelines: %d, invariant kept: %d, broken: %d" % (len(kept), sum(kept), len(kept) - sum(kept)))
    print()

    def start():
        holder = unit.Holder()
        return holder, [(name, get_config(holder, name)) for name in "AB"]
    every = list(schedules(start))
    broken = [word for word, holder, stuck in every
              if stuck or holder.built != 1 or any(port != 8080 for _, port in holder.seen)]
    print("every schedule of two callers A, B, enumerated: %d, invariant kept: %d" % (len(every), len(every) - len(broken)))
    print("  (every order of the callers' steps; a caller that could only wait for the lock again")
    print("  is not rescheduled -- so the number depends on how long this unit holds the lock)")
    print("schedules breaking the invariant ((breaches: %d))   law == 0   %s"
          % (len(broken), "kept" if not broken else "BROKEN"))
    if broken:
        word = broken[0]
        print()
        run_timeline(get_config, "first broken schedule %s" % word,
                     [(name, "".join("1" if c == name else " " for c in word)) for name in "AB"])


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in CHOICE_DB:
        print("choices: %s" % ", ".join(CHOICE_DB))
        sys.exit(1)
    main(choice)
    print("<hwut-end>")
