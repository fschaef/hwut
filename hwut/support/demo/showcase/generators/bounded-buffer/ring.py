"""ring.py -- the bounded hand-over buffer between the sensor readers
(producers) and the uplink (consumer) of a data logger, cut into atomic
steps. A producer's or consumer's work is a generator: every 'next()'
performs ONE step and yields what it did, as an event line.

    produce_check_then_put   step 1 looks for a free slot, step 2 puts --
                             another producer may put in between
    produce_guarded          step 1 prepares the item, step 2 checks for a
                             free slot AND puts, in one step
    consume                  step 1 looks for an item, step 2 takes it;
                             done when the buffer is empty and every
                             producer has closed

The ring is told how many producers it serves when it is BUILT, before any
task runs. (Counting them at their first step let a consumer that ran
first see no producer at all and quit.)
"""


class Ring:
    def __init__(self, capacity, producers):
        self.capacity = capacity
        self.items    = []
        self.open_producers = producers


def produce_check_then_put(ring, who, items):
    for item in items:
        while len(ring.items) >= ring.capacity:
            yield "%s wait full" % who
        yield "%s sees fill %d" % (who, len(ring.items))
        ring.items.append(item)
        yield "%s put %d fill %d" % (who, item, len(ring.items))
    ring.open_producers -= 1
    yield "%s closes" % who


def produce_guarded(ring, who, items):
    for item in items:
        yield "%s prepares %d" % (who, item)
        while len(ring.items) >= ring.capacity:
            yield "%s wait full" % who
        ring.items.append(item)
        yield "%s put %d fill %d" % (who, item, len(ring.items))
    ring.open_producers -= 1
    yield "%s closes" % who


def consume(ring, who):
    while True:
        if not ring.items:
            if ring.open_producers == 0:
                yield "%s done" % who
                return
            yield "%s wait empty" % who
            continue
        yield "%s sees fill %d" % (who, len(ring.items))
        item = ring.items.pop(0)
        yield "%s take %d fill %d" % (who, item, len(ring.items))
