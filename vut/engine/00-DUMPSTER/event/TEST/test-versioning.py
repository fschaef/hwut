#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Test the EventInfo per-type version handshake (DECISION 23).

CHOICES: first_send, once_per_type, version_field, reject_uninfo, infra_exempt;

DESCRIPTION:

The first time a Terminal sends a given event TYPE, it precedes the
event with an EventInfo(event_id, version) descriptor. The receiver
caches event_id -> version and admits later events of that type; an
event whose type has no cached EventInfo is rejected and dropped.

    first_send       sending an event delivers it, and the sender has
                     recorded the type in _info_sent while the receiver
                     has cached its version in _info_seen.

    once_per_type    sending the same type twice records the type once;
                     a different type adds a second entry. The EventInfo
                     precedes only the FIRST occurrence of each type.

    version_field    the cached version is the sender type's
                     WIRE_VERSION; a subclass overriding WIRE_VERSION
                     propagates that value through the handshake.

    reject_uninfo    an event pushed onto the channel WITHOUT a
                     preceding EventInfo (bypassing send()) is rejected
                     by the receiver and never reaches the dispatcher.

    infra_exempt     EVENT_INFRA events (Up/Down) carry no EventInfo and
                     are accepted unconditionally - the handshake never
                     announces the bootstrap protocol to itself.
______________________________________________________________________________
"""
import asyncio
import sys
from   config import HwutRunner

from   vut.engine.event import (Event,
                                category,
                                EventChannelParameter,
                                EventTerminal,
                                EventInfo)


with category("TEST_LOCAL_VER"):

    class EventAlpha(Event):
        value: int

    class EventBeta(Event):
        text: str

    # A type that overrides its wire version.
    class EventV3(Event):
        WIRE_VERSION = 3
        payload: int


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


async def _drain(seconds=0.05):
    """RETURN: None. Let receive loops run to a quiescent point."""
    await asyncio.sleep(seconds)


async def _first_send():
    """RETURN: None. First send delivers event and records the type both sides."""
    a_ecp, b_ecp = EventChannelParameter.for_async()
    a = EventTerminal(a_ecp)
    b = EventTerminal(b_ecp)

    seen = []
    async def handler(ev):
        seen.append(ev.value)
    b.dispatcher.subscribe_on_event(EventAlpha, handler)

    await asyncio.gather(a.start(), b.start())

    banner("before any send")
    print("a._info_sent: %s" % sorted(a._info_sent))
    print("b._info_seen: %s" % sorted(b._info_seen))

    await a.send(EventAlpha(value=42))
    await _drain()

    banner("after first send of EventAlpha")
    print("delivered:    %s" % seen)
    print("a._info_sent: %s" % sorted(a._info_sent))
    print("b._info_seen: %s" % sorted(b._info_seen.items()))

    await asyncio.gather(a.stop(), b.stop())


async def _once_per_type():
    """RETURN: None. EventInfo precedes only the first occurrence of a type."""
    a_ecp, b_ecp = EventChannelParameter.for_async()
    a = EventTerminal(a_ecp)
    b = EventTerminal(b_ecp)

    seen = []
    async def handler(ev):
        seen.append(getattr(ev, "value", None) or getattr(ev, "text", None))
    b.dispatcher.subscribe_on_predicate(lambda ev: True, handler)

    await asyncio.gather(a.start(), b.start())

    banner("send EventAlpha twice, then EventBeta once")
    await a.send(EventAlpha(value=1))
    await a.send(EventAlpha(value=2))
    await a.send(EventBeta(text="x"))
    await _drain()

    print("delivered:    %s" % seen)
    print("a._info_sent: %s" % sorted(a._info_sent))
    print("b._info_seen: %s" % sorted(b._info_seen))

    await asyncio.gather(a.stop(), b.stop())


async def _version_field():
    """RETURN: None. The announced version is the type's WIRE_VERSION."""
    a_ecp, b_ecp = EventChannelParameter.for_async()
    a = EventTerminal(a_ecp)
    b = EventTerminal(b_ecp)

    seen = []
    async def handler(ev):
        seen.append(ev.payload)
    b.dispatcher.subscribe_on_event(EventV3, handler)

    await asyncio.gather(a.start(), b.start())

    banner("class WIRE_VERSION values")
    print("EventAlpha.WIRE_VERSION: %d" % EventAlpha.WIRE_VERSION)   # default
    print("EventV3.WIRE_VERSION:    %d" % EventV3.WIRE_VERSION)      # overridden

    await a.send(EventV3(payload=7))
    await _drain()

    banner("version cached by receiver")
    print("delivered:    %s" % seen)
    print("b._info_seen: %s" % sorted(b._info_seen.items()))

    await asyncio.gather(a.stop(), b.stop())


async def _reject_uninfo():
    """RETURN: None. An event with no preceding EventInfo is rejected."""
    a_ecp, b_ecp = EventChannelParameter.for_async()
    a = EventTerminal(a_ecp)
    b = EventTerminal(b_ecp)

    seen = []
    async def handler(ev):
        seen.append(ev.value)
    b.dispatcher.subscribe_on_event(EventAlpha, handler)

    await asyncio.gather(a.start(), b.start())

    banner("push event directly onto channel, bypassing send()")
    # No EventInfo precedes this - the admission check must reject it.
    # (The receiver logs a diagnostic to stderr; stdout stays clean.)
    await a._channel.send(EventAlpha(value=99))
    await _drain()

    print("delivered (expected empty): %s" % seen)
    print("b._info_seen (expected empty): %s" % sorted(b._info_seen))

    banner("a proper send() of the same type is then admitted")
    await a.send(EventAlpha(value=7))
    await _drain()
    print("delivered: %s" % seen)
    print("b._info_seen: %s" % sorted(b._info_seen))

    await asyncio.gather(a.stop(), b.stop())


async def _infra_exempt():
    """RETURN: None. EVENT_INFRA events carry no EventInfo announcement."""
    a_ecp, b_ecp = EventChannelParameter.for_async()
    a = EventTerminal(a_ecp)
    b = EventTerminal(b_ecp)

    await asyncio.gather(a.start(), b.start())

    banner("after handshake, no EventInfo announced for EVENT_INFRA")
    # The Up handshake exchanged EventTerminalUp on both sides, yet
    # neither side recorded an EventInfo for it: infra is exempt.
    print("a._info_sent (expected empty): %s" % sorted(a._info_sent))
    print("b._info_sent (expected empty): %s" % sorted(b._info_sent))
    print("a.is_up: %s" % a.is_up)
    print("b.is_up: %s" % b.is_up)

    await asyncio.gather(a.stop(), b.stop())


def run_first_send():    asyncio.run(_first_send())
def run_once_per_type(): asyncio.run(_once_per_type())
def run_version_field(): asyncio.run(_version_field())
def run_reject_uninfo(): asyncio.run(_reject_uninfo())
def run_infra_exempt():  asyncio.run(_infra_exempt())


HwutRunner(
    argv       = sys.argv,
    title      = "EventInfo version handshake",
    choice_map = {
        "first_send":    run_first_send,
        "once_per_type": run_once_per_type,
        "version_field": run_version_field,
        "reject_uninfo": run_reject_uninfo,
        "infra_exempt":  run_infra_exempt,
    },
).run()
