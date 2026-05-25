"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: The child-side trampoline.

DISCUSSION.txt D5: the child does NOT start at the user callable
directly. It starts HERE, at a framework trampoline that:

    1. builds the SpawnerChildEventTerminal from the child ECP,
    2. start()s it - which runs the Up handshake,
    3. and ONLY THEN invokes the user callable.

The pay-off is the startup guarantee: because the trampoline completes
the handshake before the callable runs, "launch succeeded" PROVABLY
means "the channel is live", not merely "a process exists". The
Spawner's _spawn races the parent-side handshake against child-death;
the trampoline is the child-side half that makes the handshake
meaningful.

CONTEXT-MANAGER FRAME (README.txt, child terminal section)

The terminal is entered as an async context manager:

    async with SpawnerChildEventTerminal(ecp) as term:
        await invoke_callable(...)

__aenter__ -> start() (handshake + subscribe to EventChildTerminationReq)
__aexit__  -> stop()  (emit EventChildTermination + close)

so the child's EventChildTermination confirmation is emitted on EVERY
exit path - normal return, requested termination, or exception - which
is what lets the parent-side FSM tell TERM_OK from TERM_FAILURE.

EXIT-REASON MAPPING (DISCUSSION.txt D7, events.py E_TerminationReason)

The trampoline maps the callable's outcome onto the reason carried by
EventChildTermination:

    callable returns normally     -> COMPLETED
    callable observed a
      termination request          -> TERMINATED
    callable raised                -> FAILED   (reported out cleanly,
                                                not crashed silently)

ARGUMENT SHAPES (README.txt, 'args' section)

The user callable receives the child terminal as its FIRST argument,
then the user args:

    args is a tuple   ->  callable(term, *args)
    args is a dict    ->  callable(event_terminal=term, **args)

For spawn_remote_process the callable arrives as a STRING name (D4); the
trampoline resolves it by ordinary import - the import system is the
registry.

WHERE THE TRAMPOLINE RUNS

    async / thread   in this interpreter; run_trampoline() is awaited or
                     run on the worker thread by the Spawner.
    process / remote -- run_trampoline_entry() is the picklable, no-arg-
                     friendly module-level entry the child process boots
                     into; it sets up an event loop and runs
                     run_trampoline().
________________________________________________________________________________
"""
import asyncio
import importlib
import sys

from vut.engine.event.channel.parameter import EventChannelParameter

from vut.engine.spawner.terminals import SpawnerChildEventTerminal
from vut.engine.spawner.events    import E_TerminationReason


def resolve_callable(function_name: str):
    """RETURN: callable, the function named by the dotted import path.

    Raises ImportError if the module cannot be imported, and
    AttributeError if the module has no such attribute. Used for
    spawn_remote_process, whose 'callable' is a STRING because a live
    function object cannot travel to another machine (DISCUSSION.txt
    D4) - the remote side resolves it by ordinary import.

    function_name is 'package.module.function': everything up to the
    last dot is the module, the final component is the attribute.
    """
    module_path, _, attr = function_name.rpartition(".")
    if not module_path:
        raise ImportError(
            "resolve_callable: %r is not a dotted path; expected "
            "'package.module.function'." % function_name
        )
    module = importlib.import_module(module_path)
    return getattr(module, attr)


async def _invoke(callable_thing, term, args):
    """RETURN: the user callable's own return value.

    Calls the user callable with the child terminal as first argument,
    then the user args, honouring the args shape (README.txt):

        args is a tuple / list  ->  callable_thing(term, *args)
        args is a dict          ->  callable_thing(event_terminal=term,
                                                   **args)
        args is None            ->  callable_thing(term)

    If the callable returns a coroutine it is awaited, so both sync and
    async user callables are supported. Any exception the callable
    raises propagates to run_trampoline(), which maps it to a FAILED
    termination reason.
    """
    if args is None:
        result = callable_thing(term)
    elif isinstance(args, dict):
        result = callable_thing(event_terminal=term, **args)
    else:
        result = callable_thing(term, *args)

    if asyncio.iscoroutine(result):
        return await result
    return result


async def run_trampoline(child_ecp:      EventChannelParameter,
                         callable_thing,
                         args) -> E_TerminationReason:
    """RETURN: E_TerminationReason, the reason the child terminated with.

    The child-side entry described in DISCUSSION.txt D5. Builds the
    SpawnerChildEventTerminal from child_ecp, enters it as an async
    context manager (start() -> Up handshake; on exit stop() -> emit
    EventChildTermination), and runs the user callable INSIDE that
    frame, so the handshake is provably complete before the callable
    begins.

    callable_thing may be a live callable (async/thread/process) or a
    dotted-path STRING (remote); a string is resolved via
    resolve_callable() before use.

    Outcome -> reason mapping (the reason is set on the terminal so the
    EventChildTermination emitted by stop() carries it):

        normal return            -> COMPLETED
        a termination request was
          observed during the run -> TERMINATED  (the terminal records
                                     this itself on receiving
                                     EventChildTerminationReq)
        callable raised           -> FAILED       (re-raised after the
                                     reason is recorded, so the failure
                                     is also visible to the child's own
                                     runtime)

    A failure in BUILDING or STARTING the terminal (before the callable
    runs) is not a child-termination reason at all - it is a startup
    failure; it propagates to the caller (the process/thread entry),
    and the parent side observes it as child-death during the _spawn
    handshake race.
    """
    if isinstance(callable_thing, str):
        callable_thing = resolve_callable(callable_thing)

    term = SpawnerChildEventTerminal(child_ecp)

    # The context manager frame: __aenter__ runs start() (handshake);
    # __aexit__ runs stop() (emit EventChildTermination + close).
    async with term:
        try:
            await _invoke(callable_thing, term, args)
        except Exception as e:
            # The callable raised. Record FAILED so the confirmation
            # event carries it, then re-raise so the child runtime sees
            # the failure too. stop() (in __aexit__) still runs and
            # still emits the confirmation - the reason is already set.
            term.report_reason(E_TerminationReason.FAILED)
            print("run_trampoline: user callable raised: %s" % e,
                  file=sys.stderr)
            raise
        # Normal return. If a termination request was observed during
        # the run the terminal has ALREADY set TERMINATED on itself;
        # only stamp COMPLETED if it has not.
        # report_reason is idempotent-friendly: a later COMPLETED would
        # wrongly overwrite an earlier TERMINATED, so we do not call it
        # here - COMPLETED is the terminal's constructed default and
        # _on_termination_req upgrades it to TERMINATED when relevant.

    return term._exit_reason


def run_trampoline_entry(child_ecp:      EventChannelParameter,
                         callable_thing,
                         args) -> int:
    """RETURN: int, a process exit code: 0 on COMPLETED/TERMINATED,
                                         1 on FAILED or startup failure.

    The picklable, module-level entry point a spawned PROCESS (and the
    remote process) boots into. multiprocessing needs a top-level
    function; this is it. It owns the child's event loop:

        -- creates a fresh asyncio event loop,
        -- runs run_trampoline() to completion on it,
        -- maps the resulting reason (or an unhandled exception) to a
           conventional process exit code.

    async and thread children do NOT use this entry - they share the
    parent's loop and the Spawner awaits run_trampoline() directly.

    The exit code is a coarse, OS-level echo of the outcome; the
    AUTHORITATIVE outcome is the EventChildTermination already emitted
    on the channel by run_trampoline()'s context-manager exit.
    """
    try:
        reason = asyncio.run(run_trampoline(child_ecp, callable_thing, args))
    except Exception as e:
        # Startup failure, or a callable failure re-raised out of
        # run_trampoline. The channel-side confirmation (if the terminal
        # got far enough to send one) is the real signal; this code is
        # the OS-level echo.
        print("run_trampoline_entry: child terminated abnormally: %s" % e,
              file=sys.stderr)
        return 1

    return 0 if reason in (E_TerminationReason.COMPLETED,
                           E_TerminationReason.TERMINATED) else 1
