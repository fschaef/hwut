"""philosophers.py -- five philosophers, five forks, real threads.

Seat i has fork i on its left and fork (i + 1) % 5 on its right. A
philosopher eats MEALS times; each meal needs both forks.

    naive     take the left fork, then the right one
    ordered   take the LOWER-numbered of the two first (resource ordering,
              Dijkstra): seat 4 takes fork 0 before fork 4

A Fork is a lock that tells a 'Table' who holds it and who waits for it, so
that an observer can draw the waits-for graph. 'Table.sat_down' is the
rendezvous of the test: every philosopher has taken -- or is blocked on --
its first fork before anyone reaches for a second. It makes the naive
table's deadlock certain instead of lucky; the ordered table passes it too.
"""
import threading

SEATS = 5
MEALS = 3


class Table:
    def __init__(self):
        self.cond = threading.Condition()
        self.holder = {}             # fork -> thread ident
        self.waiting = {}            # thread ident -> fork
        self.first_tried = set()     # thread idents that went for their first fork
        self.meals = {}              # seat -> meals eaten
        self.seated = False          # the rendezvous has happened (once)

    def sat_down(self):
        """RETURN: True once every seat has had its first fork or been blocked
                   on it at the same moment; stays True from then on."""
        self.seated = self.seated or (len(self.first_tried) == SEATS and all(
            t in self.holder.values() or self.waiting.get(t) in self.holder for t in self.first_tried))
        return self.seated


class Fork:
    def __init__(self, table, number):
        self.table, self.number, self.lock = table, number, threading.Lock()

    def take(self):
        me = threading.get_ident()
        with self.table.cond:
            self.table.waiting[me] = self
            self.table.cond.notify_all()
        self.lock.acquire()
        with self.table.cond:
            del self.table.waiting[me]
            self.table.holder[self] = me
            self.table.cond.notify_all()

    def put(self):
        with self.table.cond:
            del self.table.holder[self]
            self.table.cond.notify_all()
        self.lock.release()


def fork_order(forks, seat, policy):
    """RETURN: (first fork, second fork) the philosopher at 'seat' takes."""
    left, right = forks[seat], forks[(seat + 1) % SEATS]
    return (left, right) if policy == "naive" else tuple(sorted((left, right), key=lambda f: f.number))


def philosopher(table, forks, seat, policy):
    first, second = fork_order(forks, seat, policy)
    for meal in range(MEALS):
        if meal == 0:
            with table.cond:
                table.first_tried.add(threading.get_ident())
        first.take()
        if meal == 0:
            with table.cond:
                table.cond.wait_for(table.sat_down)
        second.take()
        with table.cond:
            table.meals[seat] = table.meals.get(seat, 0) + 1
        second.put()
        first.put()
