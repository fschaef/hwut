"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       THE ACQUIRE STAGE -- dependencies come to exist.

DESCRIPTION
       One stage of provision (see provision/core.py). Left OPEN by
       design: an acquisition IS a call to a procsitter -- curl, git,
       an installer -- guarded by a SATISFACTION CHECK. The stage does
       not interpret what a command does.
______________________________________________________________________________
"""
import asyncio
from   dataclasses import dataclass

from   vut.engine.test_run.result         import E_TestRunResult
from   vut.engine.procsitter.procsitter    import Procsitter, E_Containment
from   vut.engine.test_run.provision.core  import Supply


@dataclass(frozen=True)
class AcquireItem:
    """ONE DEPENDENCY: a name for the report, a SATISFACTION CHECK, and
    the command that acquires it. The stage stays open by design: an
    acquisition IS a call to a procsitter -- curl, git, an installer --
    and this item does not interpret what the command does.

        satisfied_f   () -> bool: the make semantics -- True is SKIPPED,
                      silently and fast, so a suite runs twice without
                      re-fetching the world
        argv          the supervised command that satisfies the check
    """
    name:        str
    satisfied_f: object
    argv:        tuple


class StageAcquire:
    """THE DEPENDENCIES come to exist -- once, and only where absent.

    Each item's command is A SUPERVISED CALL: own caps, own attribution
    -- the wall clock contains a hung mirror, the disk cap a runaway
    download. The first item that fails ENDS acquisition with the
    'acquisition-failed' token; items already acquired stay acquired
    (they are satisfied on the next run).

    MEMOIZED like the build, behind a lock: wire the SAME instance into
    every Provision that needs these dependencies, and the world is
    asked a single time.

    Reads the caps and place keys of the configuration.
    """

    def __init__(self, configuration, item_list, observer=None):
        self.configuration = configuration
        self.item_list     = list(item_list)
        self.observer      = observer
        self._supply       = None
        self._lock         = asyncio.Lock()

    async def supply(self, stop_event=None):
        """
        RETURN: Supply, product = the item names (satisfied or
                acquired); product None with 'acquisition-failed' when
                the world would not deliver.
        """
        async with self._lock:
            if self._supply is None:
                self._supply = await self._acquire(stop_event)
            return self._supply

    async def _acquire(self, stop_event):
        """
        RETURN: Supply, the answer 'supply()' memoizes -- items checked
                in order, absent ones acquired under supervision.
        """
        configuration = self.configuration
        record_list   = []
        for item in self.item_list:
            if item.satisfied_f():
                continue
            procsitter = Procsitter(configuration.caps,
                                    work_dir=str(
                                        configuration.test_directory))
            record = await procsitter.run(list(item.argv),
                                          stop_event=stop_event)
            record_list.append(record)
            if record.containment is not E_Containment.OK_COMPLETED \
               or not item.satisfied_f():
                #  The command ran and the check STILL says absent:
                #  that, too, is a dependency that was not delivered.
                return Supply(product     = None,
                              report      = E_TestRunResult
                                            .ACQUISITION_FAILED,
                              record_list = tuple(record_list))
        return Supply(product     = tuple(i.name for i in self.item_list),
                      record_list = tuple(record_list))
