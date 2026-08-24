"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE BUDGET -- how many pieces of work may stand at once on
         this host. ONE budget is made above and handed to every
         Scheduler of a run; a Scheduler given a bare number makes a
         private one.

    budget = CBudget(4)          four slots; CBudget(None) is no bound
    if budget.take_f(): ...      a slot, now, or nothing
    await budget.take()          a slot, when one is free
    budget.give()                the slot back; a waiter is woken
    await budget.changed()       resolves on the next 'give()'

A slot is a slot: frame scripts, builds, session launches and tests all
take one (O-12). 'peak' records the most slots ever held at one time.
______________________________________________________________________________
"""
import asyncio
from collections import deque


class CBudget:
    """The count of work standing at once, shared by every scheduler of
    one run."""

    def __init__(self, limit=None):
        """
        RETURN: CBudget, with 'limit' slots; 'None' is no bound.

        Raises AssertionError where 'limit' is below one -- a budget of
        zero schedules nothing and is refused at the door.
        """
        assert limit is None or limit >= 1, \
               "budget limit is %r; a bound below one schedules nothing" \
               % limit
        self.limit   = limit
        self.held_n  = 0
        self.peak    = 0
        self._waiter_deque = deque()     # futures of take() and changed()

    def free_f(self):
        """RETURN: bool, True where a slot may be taken now."""
        return self.limit is None or self.held_n < self.limit

    def take_f(self):
        """RETURN: bool, True where a slot was taken, now; False where
        none is free, and nothing changed."""
        if not self.free_f(): return False
        self.held_n += 1
        self.peak    = max(self.peak, self.held_n)
        return True

    async def take(self):
        """RETURN: None, once a slot is held -- immediately where one is
        free, else after a 'give()' made one free."""
        while not self.take_f():
            await self.changed()

    def give(self):
        """RETURN: None. Returns one slot; every pending 'changed()' and
        'take()' waiter is woken.

        Raises AssertionError where no slot is held.
        """
        assert self.held_n > 0, "give() without a slot held"
        self.held_n -= 1
        while self._waiter_deque:
            future = self._waiter_deque.popleft()
            if not future.done(): future.set_result(None)

    def changed(self):
        """RETURN: asyncio.Future, resolved on the next 'give()'; the
        caller combines it with its own tasks in 'asyncio.wait'."""
        future = asyncio.get_running_loop().create_future()
        self._waiter_deque.append(future)
        return future


def budget_of(worker_max_n):
    """RETURN: CBudget, 'worker_max_n' itself where it is one already,
    else a private budget bounded by it ('None' is no bound)."""
    if isinstance(worker_max_n, CBudget): return worker_max_n
    else:                                 return CBudget(worker_max_n)
