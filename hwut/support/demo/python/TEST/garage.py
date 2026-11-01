#! /usr/bin/env python3
#
# @hwut {
#     title    = "Demo: a garage's space counter -- a space, a stream and races, generated"
#     interactive = true
#     choices {
#         space       { features = ["space-from-hocon", "space-iterator", "hwut-runner"]
#                       tolerance { constraints = ["mismatches == 0"] } }
#         random      { features = ["deterministic-stream", "hwut-runner"]
#                       tolerance { constraints = ["mismatches == 0"] } }
#         race-naive  { features = ["deterministic-timeline", "space-iterator", "hwut-runner"]
#                       tolerance { constraints = ["overbooked > 0"] } }
#         race-atomic { features = ["deterministic-timeline", "space-iterator", "hwut-runner"]
#                       tolerance { constraints = ["overbooked == 0"] } }
#     }
# }
#
"""
______________________________________________________________________________
SUBJECT  the counter of free spaces at a garage's gates: which cars it
         admits, which it refuses, and how many stand inside.
REQUIREMENT  The garage admits a car only while a space is free, lets a car
             out only while one stands inside, and never holds more cars
             than it has spaces -- also when two gates admit at once.

No choice writes its cases out by hand. Each GENERATES them, with one of
hwut's helpers for writing tests (hwut/test_writing_support/python):

space        'garage-space.hocon' states the tested space -- capacities,
             cars arriving, cars leaving -- in hwut's HOCON, read by
             'hwut_hocon'. A reviewer edits the space without reading
             Python. 'space_iterator.do' walks every combination: 3 x 5 x
             4 = 60 cases. Each is printed as one cell of a matrix, and
             checked against the model: admitted = min(arriving,
             capacity), out = min(leaving, admitted).

random       'DeterministicStream(4711)' draws 1000 cars arriving and
             leaving at a garage of 5. The draw is the same on every
             machine and in every language hwut supports -- the stream is
             a linear congruential generator, not Python's 'random' -- so
             the GOOD is exact, and a failing run can be replayed by its
             seed.

race-naive   two gates, one free space. A gate CHECKS whether a space is
             free, and later ADMITS its car. 'deterministic_timeline'
             runs the two gates as Triggers on timelines drawn as
             strings -- '1 1 ' fires at tick 0 and tick 2 -- so every
             interleaving is played exactly, not hoped for with sleeps.
             'space_iterator' generates all six interleavings of two
             two-step gates in four ticks. Where both gates check before
             either admits, both admit: the garage is overbooked. The law
             is 'overbooked > 0': the GOOD is the accepted violation
             report.

race-atomic  the same six interleavings, the gate checking and admitting
             in ONE step under the counter's lock. 'overbooked == 0'.

THE FRONT END is hwut's HwutRunner: the choice map below is the whole
command line, '--hwut-info' included. The header says
'interactive = true': hwut starts the application ONCE and asks for the
choices one after another in that one process -- an accelerator only: a
choice's output equals what it prints when run alone.
______________________________________________________________________________
"""
import os
import sys

import hwut.test_writing_support.python.space_iterator as space_iterator
import hwut.test_writing_support.python.hwut_hocon as hwut_hocon
from hwut.test_writing_support.python.deterministic_random   import DeterministicStream
from hwut.test_writing_support.python.deterministic_timeline import Trigger, TriggerDispatcher
from hwut.test_writing_support.python.hwut_runner            import HwutRunner

HERE = os.path.dirname(os.path.abspath(__file__))


class Garage:
    """The unit under test: a counter of the spaces a garage has."""

    def __init__(self, capacity):
        """RETURN: None. An empty garage of 'capacity' spaces."""
        self.capacity = capacity
        self.occupied = 0

    def free(self):
        """RETURN: int, the number of spaces free now -- negative where
                   the garage is overbooked."""
        return self.capacity - self.occupied

    def arrive(self):
        """
        RETURN: True, a car was admitted, if a space was free;
                False, else (the car is refused).
        """
        if self.free() <= 0: return False
        self.occupied += 1
        return True

    def leave(self):
        """
        RETURN: True, a car drove out, if one stood inside;
                False, else.
        """
        if self.occupied == 0: return False
        self.occupied -= 1
        return True


# _____________________________________________________________________________
# space -- the tested space from HOCON, walked by space_iterator
#
def read_space(path):
    """
    RETURN: list of (str, list), the dimensions of the space in 'path', in
            the order written: (name, values).
    Every fault the HOCON reader found is printed with '!!' first.
    """
    with open(path) as fh:
        line_list = [hwut_hocon.SourceLine(text.rstrip("\n"), i + 1, 0)
                     for i, text in enumerate(fh)]
    document, fault_list = hwut_hocon.parse(line_list, os.path.basename(path))
    for fault in fault_list:
        print("!! %s" % fault)
    space = document.get("space").node
    return [(e.key, [item.value for item in e.node.item_list])
            for e in space.entry_list]


def space():
    """RETURN: None. Prints every case of the space as a matrix cell."""
    dimension_list = read_space(os.path.join(HERE, "garage-space.hocon"))
    name_list  = [name for name, _ in dimension_list]
    value_list = [values for _, values in dimension_list]
    print("space: %s" % "  x  ".join("%s %s" % (n, v) for n, v in dimension_list))
    print("cell: cars inside / cars refused at the gate ('!!' differs from the model)")
    mismatch_n = 0
    row_db = {}
    for capacity, arriving, leaving in space_iterator.do(value_list):
        garage   = Garage(capacity)
        refused  = [garage.arrive() for _ in range(arriving)].count(False)
        for _ in range(leaving): garage.leave()
        admitted = min(arriving, capacity)
        expected = (admitted - min(leaving, admitted), arriving - admitted)
        got      = (garage.occupied, refused)
        mark     = "  " if got == expected else "!!"
        mismatch_n += got != expected
        row_db.setdefault((capacity, arriving), []).append("%d/%d%s" % (got + (mark,)))
    for capacity in value_list[0]:
        print("capacity %d   %s" % (capacity, "  ".join("leave %-3d" % l for l in value_list[2]).rstrip()))
        for arriving in value_list[1]:
            print(("  arrive %d   %s" % (arriving, "  ".join("%-9s" % c for c in row_db[(capacity, arriving)]))).rstrip())
    print("cases %d, differing from the model ((mismatches: %d))" % (len(row_db) * len(value_list[2]), mismatch_n))


# _____________________________________________________________________________
# random -- a deterministic stream of arrivals and departures
#
def random_stream():
    """RETURN: None. Prints the summary of 1000 drawn cars, model-checked."""
    stream   = DeterministicStream(4711)
    garage   = Garage(5)
    model    = 0
    count_db = {"arrive": 0, "refused": 0, "leave": 0, "empty": 0}
    histogram = [0] * 6
    mismatch_n = 0
    strip = ""
    for i in range(1000):
        if stream.coin(0.55):
            count_db["arrive"] += 1
            if not garage.arrive(): count_db["refused"] += 1
            model = min(5, model + 1)
            strip += "+"
        else:
            count_db["leave"] += 1
            if not garage.leave(): count_db["empty"] += 1
            model = max(0, model - 1)
            strip += "-"
        mismatch_n += garage.occupied != model
        histogram[garage.occupied] += 1
    print("seed 4711, garage of 5, 1000 cars drawn: '+' arrives, '-' leaves")
    print("first 60: %s" % strip[:60])
    print("arrivals %(arrive)d, refused %(refused)d; departures %(leave)d, from an empty garage %(empty)d" % count_db)
    print("cars inside after each event:")
    for n, count in enumerate(histogram):
        print("    %d  %4d  %s" % (n, count, "#" * (count // 10)))
    print("steps differing from the model ((mismatches: %d))" % mismatch_n)


# _____________________________________________________________________________
# race -- two gates on drawn timelines
#
class Gate(Trigger):
    """A gate on a timeline: its first tick checks, its second admits."""

    def __init__(self, name, timeline, garage, atomic, log):
        """RETURN: None."""
        Trigger.__init__(self, timeline, name)
        self.garage, self.atomic, self.log = garage, atomic, log
        self.step = 0
        self.saw_free = False

    async def fire(self, pseudo_time):
        """RETURN: None. Performs the gate's next step at 'pseudo_time'."""
        if self.step == 0 and self.atomic:
            self.saw_free = self.garage.arrive()
            self.log("%s checks+admits" % self.name if self.saw_free else "%s refuses" % self.name)
        elif self.step == 0:
            self.saw_free = self.garage.free() > 0
            self.log("%s sees %d free" % (self.name, self.garage.free()))
        elif self.atomic:
            self.log("%s opens" % self.name if self.saw_free else "%s stays shut" % self.name)
        elif self.saw_free:
            self.garage.occupied += 1                     # the naive admit
            self.log("%s admits" % self.name)
        else:
            self.log("%s refuses" % self.name)
        self.step += 1


def interleaving_list():
    """
    RETURN: list of (str, str), every pair of timelines in four ticks in
            which each of two gates fires twice, never at the same tick:
            gate A's and gate B's.
    """
    result = []
    for a1, a2, b1, b2 in space_iterator.do([range(4)] * 4):
        if a1 < a2 and b1 < b2 and len({a1, a2, b1, b2}) == 4:
            line = lambda x, y: "".join("1" if t in (x, y) else " " for t in range(4))
            result.append((line(a1, a2), line(b1, b2)))
    return result


async def race(atomic):
    """RETURN: None. Plays every interleaving of two gates at one space."""
    print("one free space, two gates, one car at each; timelines: a digit fires")
    print("    gate A  gate B  what happens                                    inside")
    overbooked_n = 0
    for timeline_a, timeline_b in interleaving_list():
        garage, event_list = Garage(1), []
        gate_list = [Gate("A", timeline_a, garage, atomic, event_list.append),
                     Gate("B", timeline_b, garage, atomic, event_list.append)]
        await TriggerDispatcher(gate_list).run()
        mark = "!!" if garage.occupied > garage.capacity else "  "
        overbooked_n += garage.occupied > garage.capacity
        print(("    \"%s\"  \"%s\"  %-46s  %d %s" % (timeline_a, timeline_b, ", ".join(event_list),
                                                  garage.occupied, mark)).rstrip())
    print("interleavings overbooking the garage ((overbooked: %d)) of %d"
          % (overbooked_n, len(interleaving_list())))


async def race_naive():
    """RETURN: None. The gates check, then admit, in two steps."""
    await race(atomic=False)


async def race_atomic():
    """RETURN: None. The gates check and admit in one step."""
    await race(atomic=True)


HwutRunner(sys.argv, "Demo: a garage's space counter -- a space, a stream and races, generated;",
           {"space":       space,
            "random":      random_stream,
            "race-naive":  race_naive,
            "race-atomic": race_atomic}).run()
