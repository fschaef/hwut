#! /usr/bin/env python3
# @hwut {
#     title    = "Bounded buffer, two producers and a consumer: timelines generate the stream, a pype law judges it"
#     pype     = "buffer.pype"
#     features = ["law-per-timeline"]
#     choices {
#         guarded        { features = ["law-per-timeline", "never-overfull", "consumer-first"]
#                          tolerance { constraints = ["breaches == 0"] } }
#         check-then-put { features = ["law-per-timeline", "overfull-named"]
#                          tolerance { constraints = ["breaches > 0"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  the buffer of ../ring.py per timeline of two producers and a
         consumer: fill, order, losses -- as buffer.pype judges the stream
REQUIREMENT  The hand-over buffer of the data logger never holds more than
             its capacity (2), hands items out in the order they came in,
             and loses none -- for any interleaving of two sensor readers
             (producers P, Q) and the uplink (consumer C).

The unit is '../ring.py': producers and the consumer as generators of
atomic steps. 'produce_check_then_put' looks for a free slot in one step
and puts in the next; 'produce_guarded' prepares, then checks and puts in
one step.

THE GENERATOR INSTRUCTIONS -- four timelines per run, the same for both
units, three lanes each (deterministic_timeline.TriggerDispatcher); the
GOOD prints each one's strings in full:

    consumer keeps up   P first, C steps between every producer step
    producers burst     P and Q fill the buffer before C starts
    same tick, Q checks P with priority 2 lets Q check in the same tick
    consumer first      C takes the first step, before any producer --
                        the start-up order of a real logger, where the
                        uplink thread may well be scheduled first

THE STEPS ARE A MODEL: producers and consumer are generators stepped by
one thread in the dispatcher's order -- no real threads; the test proves
the step model of the code, not the OS scheduler.

THE JUDGE IS A pype LAW. This application only REPORTS what each step did
('t <tick> <event>'), as it happens, and draws the lane picture; the header
key 'pype = "buffer.pype"' makes hwut run '../TEST/buffer.pype' on that
stream. The script holds the laws as modes (IDLE -> RUN -> IDLE per
timeline): fill <= capacity after every put, FIFO order of takes, every
item put taken once, every task finished. It prints per timeline the
picture, the counts, every breach, 'law: kept/BROKEN', and owns
'<hwut-end>' (so this application prints none: HWUT_NO_TERMINAL).
The end of a timeline is an event of the dispatcher too: a task that has
not finished when its timeline runs out says so from 'on_termination', and
the law counts it.

guarded          four timelines, four times 'law: kept'. The 'consumer
                 first' timeline is there because an earlier unit counted
                 its producers as they took their FIRST step: a consumer
                 scheduled first saw no open producer, said 'done' and
                 left the producers waiting on a full buffer. The ring now
                 knows its producers when it is built. Law 'breaches == 0'.
check-then-put   timelines that let both producers see one free slot
                 overfill it: fill 3 of 2 -- named with tick and item.
                 Law 'breaches > 0'.

HOW TO READ THE GOOD   The legend of schedule strings and step codes heads
the page (printed by buffer.pype). Per timeline: the drawn strings, the
lane picture ('##! verbatim': a step's column is its tick; the buffer's
content after each tick in the last row), then the law's verdict. The
cells stay 9 wide: 'take12>0' and '[1 2 11]' need 8. All exact, except the
count of broken timelines, a binding '((breaches: N))' judged by the law.
By hand: './test-buffer.py guarded | hwut.pype buffer.pype'.
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
import ring as unit

CAPACITY = 2
TIMELINES = [
    ("consumer-keeps-up",   "1   1   1   1   1",     "  1   1   1   1   1",     " 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1 1"),
    ("producers-burst",     "11111111111111",        "  11111111111111111",     "      1111111111111111"),
    ("same-tick-Q-checks",  "1 2 2 2 2 2 2 2 2 2",   "  1 1 1 1 1 1 1 1 1 1",   "      1 1 1 1 1 1 1 1 1 1 1"),
    ("consumer-first",      " 1 1 1 1 1 1 1 1 1",    "  1 1 1 1 1 1 1 1 1",     "1 1 1 1 1 1 1 1 1 1 1 1 1 1"),
]
CHOICE_DB = {"guarded": unit.produce_guarded, "check-then-put": unit.produce_check_then_put}
W = 9


def short(event):
    """The picture's cell for an event: 'P put 11 fill 2' -> 'put11>2'."""
    w = event.split()[1:]
    if w[0] in ("put", "take"): return "%s%s>%s" % (w[0], w[1], w[3])
    if w[0] == "sees":          return "see%s" % w[2]
    if w[0] == "prepares":      return "prep%s" % w[1]
    return w[0]


class StepTrigger(Trigger):
    def __init__(self, timeline, name, steps, ring, log, producer_f):
        super().__init__(timeline, name)
        self.steps, self.ring, self.log, self.producer_f = steps, ring, log, producer_f
        self.finished = False

    async def fire(self, tick):
        if self.finished:
            return
        event = next(self.steps, None)
        if event is None:
            return
        if event.endswith((" done", " closes")):
            self.finished = True
        print("t %d %s" % (tick, event))
        self.log.append((tick, self.name, short(event)))

    def on_termination(self, end_tick):
        if not self.finished:
            print("unfinished %s" % self.name)


def run_timeline(produce, title, p_line, q_line, c_line):
    ring, log, fill_at = unit.Ring(CAPACITY, producers=2), [], {}
    print("timeline %s" % title)
    print("capacity %d" % CAPACITY)
    triggers = [StepTrigger(p_line, "P", produce(ring, "P", [1, 2]), ring, log, True),
                StepTrigger(q_line, "Q", produce(ring, "Q", [11, 12]), ring, log, True),
                StepTrigger(c_line, "C", unit.consume(ring, "C"), ring, log, False)]

    class Snapshot(Trigger):
        async def fire(self, tick):
            fill_at[tick] = list(ring.items)
    end = max(len(p_line), len(q_line), len(c_line))
    asyncio.run(TriggerDispatcher(triggers + [Snapshot("9" * end, "snapshot")]).run())

    print("picture")
    for name, line in (("P", p_line), ("Q", q_line), ("C", c_line)):
        print('    %s = "%s"' % (name, line))
    used = sorted(set(t for t, _, _ in log))
    gaps = used != list(range(used[0], used[-1] + 1))
    print("  tick    " + "".join("%-*d" % (W, t) for t in used).rstrip()
          + ("   (ticks without a step omitted)" if gaps else ""))
    for name in "PQC":
        cell = dict((t, e) for t, n, e in log if n == name)
        print(("  %s       " % name + "".join("%-*s" % (W, cell.get(t, "")) for t in used)).rstrip())
    print("  buffer  " + "".join("%-*s" % (W, "[" + " ".join(map(str, fill_at[t])) + "]") for t in used).rstrip())
    print("end-picture")
    print("end-timeline")


def main(choice):
    for title, p_line, q_line, c_line in TIMELINES:
        run_timeline(CHOICE_DB[choice], title, p_line, q_line, c_line)


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in CHOICE_DB:
        print("choices: %s" % ", ".join(CHOICE_DB))
        sys.exit(1)
    main(choice)
