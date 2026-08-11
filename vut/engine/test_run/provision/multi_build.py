"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       THE MULTI-BUILDER -- many targets through few tool invocations.

DESCRIPTION
       'MultiBuild' is the build role's I_MultiProvider: ONE build tool,
       invoked per WAVE, serves MANY targets. What may share a wave is
       BUILD SYSTEM KNOWLEDGE, so it lives behind an interface per
       build system:

           I_BuildSystem
               waves(target_list) -> tuples of targets; every target
                       of one wave may build IN PARALLEL, and waves
                       build IN ORDER
               argv(target_tuple) -> the ONE invocation building that
                       wave -- the tool parallelises inside it

       THE SCHEME OF OPERATION (sequence: README-provider.txt, 4).
       Targets are given at construction -- the orchestrator that
       queues the proxies knows the set, and a wave partition needs
       all of it. 'start()' launches wave after wave, each ONE
       supervised invocation; a wave's end resolves the tickets of its
       targets; 'provider(target)' hands out the target's proxy, which
       parks on that ticket.

       WHAT A WAVE'S END MEANS. Exit 0: every target of the wave is
       delivered, product = the target's name, report OK, the wave's
       ProcsitterResult beside it. Anything else: the wave's targets
       answer product None, report 'build-failed' -- and every LATER
       wave answers 'target-not-built' without its invocation running:
       the system said order matters, so a broken wave breaks what
       stands on it.

       'close()' awaits the building's end and keeps the tuple of wave
       records as '.record' -- one attribution per invocation.
______________________________________________________________________________
"""
import asyncio
from   abc     import ABC, abstractmethod
from   pathlib import Path

from   ..result                   import E_TestRunResult
from   ...procsitter.procsitter   import Procsitter, E_Containment
from   ...procsitter.construction import chain
from   .core                      import Supply
from   .provider                  import (I_BuildProvider,
                                          I_ProxyProvider,
                                          I_MultiProvider)


class I_BuildSystem(ABC):
    """WHAT ONE BUILD SYSTEM KNOWS: which targets may share a wave, and
    the one invocation that builds a wave. One implementation per build
    system -- the knowledge is the system's, never the multi's."""

    @abstractmethod
    def waves(self, target_list):
        """
        RETURN: sequence of tuples of str -- every target of one tuple
                may build IN PARALLEL; the tuples build IN ORDER. Every
                given target appears in exactly one wave.
        """

    @abstractmethod
    def argv(self, target_tuple):
        """
        RETURN: list of str, the ONE invocation that builds every
                target of the wave -- the tool parallelises inside it.
        """


class MultiBuild(I_MultiProvider):
    """ONE build tool serving many targets: waves in order, one
    supervised invocation per wave, per-target proxies.

    Use as an async context manager, or 'start()'/'close()' by hand;
    the build runs in 'directory' under 'caps'.
    """

    def __init__(self, build_system, target_list, directory, caps):
        """
        RETURN: MultiBuild, not yet building.

        'build_system'   the I_BuildSystem holding the wave knowledge.
        'target_list'    every target of the visit -- a partition needs
                         the whole set, so it is given here, not
                         discovered.
        'directory'      where the invocations run.
        'caps'           the ProcsitterConfig of every invocation.
        """
        assert isinstance(build_system, I_BuildSystem), \
               "MultiBuild requires an I_BuildSystem; received a %s" \
               % type(build_system).__name__
        self.build_system = build_system
        self.directory    = Path(directory)
        self.caps         = caps
        self.record       = None     # tuple of wave records, after close
        self._wave_list   = build_system.waves(tuple(target_list))
        #  THE PARTITION LAW, refused at the door: every given target in
        #  exactly ONE wave -- a system answering otherwise is a faulty
        #  plug, named here, never a riddle downstream.
        flat = [t for wave in self._wave_list for t in wave]
        assert len(flat) == len(set(flat)) \
               and set(flat) == set(target_list), \
               "%s partitions %r into %r: not a partition" \
               % (type(build_system).__name__, tuple(target_list),
                  self._wave_list)
        self._ticket_db   = {t: asyncio.get_event_loop().create_future()
                             for t in flat}
        self._runner      = None
        self._closed      = False

    async def start(self):
        """RETURN: None. Begins building, wave after wave, in the
        background. Idempotent."""
        if self._runner is None:
            self.directory.mkdir(parents=True, exist_ok=True)
            self._runner = asyncio.ensure_future(self._build_waves())

    async def _build_waves(self):
        """
        RETURN: tuple, one ProcsitterResult per wave that RAN.

        A broken wave resolves its targets 'failed' and every later
        wave's targets 'not-reached' -- their invocations never run.
        """
        record_list = []
        broken      = False
        for wave in self._wave_list:
            if broken:
                for target in wave:
                    self._ticket_db[target].set_result("not-reached")
                continue
            record = await self._invoke(self.build_system.argv(wave))
            record_list.append(record)
            answer = "built" \
                     if record.containment is E_Containment.OK_COMPLETED \
                     else "failed"
            for target in wave:
                self._ticket_db[target].set_result((answer, record))
            if answer == "failed": broken = True
        return tuple(record_list)

    async def _invoke(self, argv):
        """RETURN: ProcsitterResult, ONE supervised invocation, its
        productions drained."""
        procsitter = Procsitter(self.caps, work_dir=str(self.directory))
        c = chain([(procsitter, argv)])
        drain = asyncio.ensure_future(self._drain(c.tail.reader))
        record_list = await asyncio.gather(*c.task_tuple)
        await drain
        return record_list[0]

    @staticmethod
    async def _drain(reader):
        """RETURN: None. Consumes a production until its end."""
        while await reader.read(65536):
            pass

    async def close(self):
        """
        RETURN: tuple, one ProcsitterResult per invocation that ran --
                also kept as '.record'. None, building never started.
                Idempotent; awaits the building's end.
        """
        if self._closed:        return self.record
        self._closed = True
        if self._runner is None: return None
        self.record = await self._runner
        return self.record

    def provider(self, target):
        """
        RETURN: I_ProxyProvider, the target's proxy into the building.

        Raises KeyError for a target outside the construction's list --
        a partition cannot grow after the fact.
        """
        if target not in self._ticket_db:
            raise KeyError("target %r is not among this building's "
                           "targets" % target)
        return TargetBuild(self, target)


class TargetBuild(I_ProxyProvider, I_BuildProvider):
    """ONE target's proxy into the building: acts as if it built, parks
    on the ticket, triggers when its wave's invocation ends. Behind the
    interface, indistinguishable from a local StageBuild."""

    def __init__(self, multi, target):
        self._multi = multi
        self.target = target

    @property
    def multi(self):
        """RETURN: MultiBuild, the building this proxy triggers on."""
        return self._multi

    async def supply(self, stop_event=None):
        """
        RETURN: Supply, product = the target's name, its wave's record
                beside it; product None with 'build-failed' when the
                wave broke, and 'target-not-built' when a wave BEFORE
                it broke -- the invocation never ran, so no record
                pretends it did.
        """
        await self._multi.start()
        answer = await self._multi._ticket_db[self.target]
        if answer == "not-reached":
            return Supply(product = None,
                          report  = E_TestRunResult.TARGET_NOT_BUILT)
        verdict, record = answer
        if verdict == "failed":
            return Supply(product     = None,
                          report      = E_TestRunResult.BUILD_FAILED,
                          record_list = (record,))
        return Supply(product     = self.target,
                      report      = E_TestRunResult.OK,
                      record_list = (record,))
