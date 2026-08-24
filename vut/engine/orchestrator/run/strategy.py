"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE STRATEGY -- when a directory's unit of work starts (O-15).

    CStrategy.run(unit_list, emit, budget) -> list[CDirDone]   the template
    CStrategy.may_start(index, running)    -> bool             the hook

The template walks the units in walk order. Before starting unit 'index'
it asks 'may_start(index, running)' -- 'running' is the set of indices
in flight -- and asks again each time a running unit ends. Units that
raise are the caller's business: 'run' is given a coroutine factory
that already guards them.

    CLinear     may_start = not running         one directory at a time
    CSuccessor  may_start = len(running) < 2    the next starts while the
                                                current still runs
    CParallel   may_start = True                all at once

The strategy decides WHEN a unit starts and nothing else: the budget
(O-12) bounds what stands at once, the unit (O-13) owns its directory.
______________________________________________________________________________
"""
import asyncio


class CStrategy:
    """The template; a strategy overrides 'may_start'."""

    name = "strategy"

    def may_start(self, index, running):
        """
        RETURN: bool, True where the unit at 'index' (walk order) may
                start now, 'running' being the set of indices of units
                in flight.
        """
        raise NotImplementedError

    async def run(self, guarded_list):
        """
        RETURN: list[CDirDone], one per unit, in walk order.

        'guarded_list' holds one coroutine factory per unit; each
        answers a CDirDone and never raises.
        """
        done_list = [None] * len(guarded_list)
        running   = {}                          # index -> asyncio.Task
        index     = 0
        while index < len(guarded_list) or running:
            while index < len(guarded_list) \
                  and self.may_start(index, set(running)):
                running[index] = asyncio.ensure_future(
                                     guarded_list[index]())
                index += 1
            if not running: continue
            ended_set, _ = await asyncio.wait(
                               running.values(),
                               return_when=asyncio.FIRST_COMPLETED)
            for i in sorted(i for i, task in running.items()
                            if task in ended_set):
                done_list[i] = running.pop(i).result()
        return done_list


class CLinear(CStrategy):
    """One directory after another, in walk order."""
    name = "linear"

    def may_start(self, index, running):
        """RETURN: bool, True where nothing runs."""
        return not running


class CSuccessor(CStrategy):
    """The next directory starts while the current one still runs;
    the one after waits."""
    name = "successor"

    def may_start(self, index, running):
        """RETURN: bool, True where fewer than two units run."""
        return len(running) < 2


class CParallel(CStrategy):
    """Every directory at once; the budget alone bounds."""
    name = "parallel"

    def may_start(self, index, running):
        """RETURN: bool, always True."""
        return True


STRATEGY_DB = {cls.name: cls for cls in (CLinear, CSuccessor, CParallel)}
DEFAULT_STRATEGY_NAME = CLinear.name


def strategy_of(name):
    """
    RETURN: CStrategy, the strategy called 'name'.

    Raises KeyError where no strategy carries that name.
    """
    return STRATEGY_DB[name]()
