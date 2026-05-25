"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Public surface of the Spawner component.

The Spawner launches a task/process/function into parallel execution
over the 'event' subsystem and supervises its lifecycle. See README.txt
for the design and DISCUSSION.txt for the reasoning behind it.

WHAT TO IMPORT

Spawning - the four entry functions:

    from vut.engine.spawner import (spawn_async, spawn_thread,
                                    spawn_process, spawn_remote_process)

Configuration - the per-kind config objects (one per spawn kind):

    from vut.engine.spawner import (AsyncConfig, ThreadConfig,
                                    ProcessConfig, RemoteProcessConfig)

State - the child-state machine's states, for polling .child_state():

    from vut.engine.spawner import E_ChildState

Each spawn_* returns a SpawnerParentEventTerminal (a real EventTerminal
plus .terminate / .suspend / .resume / .child_state) or None on startup
failure. The terminal type is exported for type annotations; it is not
constructed directly by users.

The four SPAWNER-category events are exported for consumers that
subscribe to them (e.g. awaiting EventChildStateChanged); they are not
constructed directly by users either.
________________________________________________________________________________
"""
from vut.engine.spawner.enums      import E_ChildState
from vut.engine.spawner.events     import (EventChildTerminationReq,
                                           EventChildTermination,
                                           EventChildKilled,
                                           EventChildStateChanged,
                                           E_TerminationReason)
from vut.engine.spawner.config     import (SpawnerConfig,
                                           AsyncConfig,
                                           ThreadConfig,
                                           ProcessConfig,
                                           RemoteProcessConfig)
from vut.engine.spawner.terminals  import (SpawnerParentEventTerminal,
                                           SpawnerChildEventTerminal)
from vut.engine.spawner.spawner    import (Spawner,
                                           spawn_async,
                                           spawn_thread,
                                           spawn_process,
                                           spawn_remote_process)

__all__ = [
    # spawning
    "spawn_async", "spawn_thread", "spawn_process", "spawn_remote_process",
    # configuration
    "SpawnerConfig", "AsyncConfig", "ThreadConfig", "ProcessConfig",
    "RemoteProcessConfig",
    # state
    "E_ChildState",
    # events
    "EventChildTerminationReq", "EventChildTermination",
    "EventChildKilled", "EventChildStateChanged", "E_TerminationReason",
    # terminals (mostly for type annotations)
    "SpawnerParentEventTerminal", "SpawnerChildEventTerminal",
    # the hub (rarely needed directly)
    "Spawner",
]
