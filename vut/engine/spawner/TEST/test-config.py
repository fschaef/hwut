#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Test - the per-kind spawner config objects (config.py).

Covers SpawnerConfig and its four concrete subclasses: the capability
flags that encode the kill asymmetry (DISCUSSION.txt D9), and the
make_ecp_pair() factories that produce the mirror ECP pair.

CHOICES
    capabilities   kind_name / supports_force_kill / supports_suspend
                   for all four kinds, plus the D9 invariants.
    ecp_pairs      make_ecp_pair() for async / thread / process:
                   pair shape, transport kind, mirror wiring.

Output is deterministic: config objects carry no timestamps, no PIDs.
The ECP objects are inspected for kind and structure only, never for
identity values that vary run to run. spawn_remote_process / remote
ECPs need a live host:port and are exercised in test-spawner.py, not
here.
________________________________________________________________________________
"""
import sys

from config import HwutRunner

from vut.engine.spawner.config import (SpawnerConfig,
                                       AsyncConfig,
                                       ThreadConfig,
                                       ProcessConfig,
                                       RemoteProcessConfig)


def run_capabilities():
    """RETURN: None.

    Reports kind_name, supports_force_kill and supports_suspend for one
    instance of each config kind, then asserts the DISCUSSION.txt D9
    invariants: a thread has no force-kill; only process and remote
    suspend.
    """
    configs = [
        AsyncConfig(),
        ThreadConfig(),
        ProcessConfig(),
        RemoteProcessConfig(host="localhost", port=9000),
    ]

    print("--- capability matrix ---")
    print("  %-9s %-16s %-16s" % ("kind", "force_kill", "suspend"))
    for c in configs:
        print("  %-9s %-16s %-16s"
              % (c.kind_name, c.supports_force_kill, c.supports_suspend))

    print("--- D9 invariants ---")
    by_kind = {c.kind_name: c for c in configs}
    # A thread can never be force-killed (D9).
    assert by_kind["thread"].supports_force_kill is False
    print("  thread has NO force-kill: OK")
    # async / thread cannot be suspended; process / remote can.
    assert by_kind["async"].supports_suspend is False
    assert by_kind["thread"].supports_suspend is False
    assert by_kind["process"].supports_suspend is True
    assert by_kind["remote"].supports_suspend is True
    print("  only process/remote support suspend: OK")
    # async can be force-killed (Task.cancel), process/remote too.
    assert by_kind["async"].supports_force_kill is True
    assert by_kind["process"].supports_force_kill is True
    assert by_kind["remote"].supports_force_kill is True
    print("  async/process/remote support force-kill: OK")

    print("--- base class refuses make_ecp_pair ---")
    try:
        SpawnerConfig().make_ecp_pair()
        print("  ERROR: base did not refuse")
    except NotImplementedError:
        print("  SpawnerConfig.make_ecp_pair() raises NotImplementedError: OK")


def run_ecp_pairs():
    """RETURN: None.

    Calls make_ecp_pair() for the async, thread and process kinds and
    reports the shape of each pair: that it is a 2-tuple, the transport
    kind of each ECP, and that the pair is a mirror (a's out queue is
    b's in queue).

    Only structure is inspected - never queue identity values, which
    differ every run.
    """
    print("--- AsyncConfig.make_ecp_pair ---")
    a, b = AsyncConfig().make_ecp_pair()
    print("  pair is 2 ECPs       : %s" % (a is not b))
    print("  a.kind / b.kind      : %s / %s" % (a.kind.name, b.kind.name))
    # Mirror wiring: a sends where b receives.
    print("  mirror wired         : %s"
          % (a.params["out_q"] is b.params["in_q"]))
    assert a.kind.name == "ASYNC" and b.kind.name == "ASYNC"
    assert a.params["out_q"] is b.params["in_q"]
    assert a.params["in_q"]  is b.params["out_q"]

    print("--- ThreadConfig.make_ecp_pair ---")
    a, b = ThreadConfig().make_ecp_pair()
    print("  a.kind / b.kind      : %s / %s" % (a.kind.name, b.kind.name))
    print("  mirror wired         : %s"
          % (a.params["out_q"] is b.params["in_q"]))
    assert a.kind.name == "THREAD" and b.kind.name == "THREAD"
    assert a.params["out_q"] is b.params["in_q"]

    print("--- ProcessConfig.make_ecp_pair (start_method threaded through) ---")
    cfg = ProcessConfig(start_method="spawn")
    a, b = cfg.make_ecp_pair()
    print("  a.kind / b.kind      : %s / %s" % (a.kind.name, b.kind.name))
    print("  start_method in params: %s" % (a.params.get("start_method"),))
    print("  mirror wired         : %s"
          % (a.params["out_q"] is b.params["in_q"]))
    assert a.kind.name == "PROCESS" and b.kind.name == "PROCESS"
    # The start method must travel on the ECP so the launcher starts the
    # child under the SAME multiprocessing context the queues were built
    # under.
    assert a.params.get("start_method") == "spawn"
    assert b.params.get("start_method") == "spawn"
    print("  start_method carried on BOTH ECPs: OK")


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "Spawner per-kind config objects",
        choice_map = {
            "capabilities": run_capabilities,
            "ecp_pairs":     run_ecp_pairs,
        },
    ).run()
