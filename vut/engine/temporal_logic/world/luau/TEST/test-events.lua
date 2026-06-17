#! /usr/bin/env luau
--[[ SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer

PURPOSE: Test the Space boundary, EventBase, the flat Tracer, and event queries.

CHOICES: factory, signal, untraced, flat_ring, queries, isolation;

DESCRIPTION:

A Space owns its own Tracer and is the factory for event classes. Every event
class derives from EventBase (hence from Queryable): its membership is the flat
history ring its Space's Tracer retains for that type. There is one ring per
type, bounded by 'last'; there is no attribute keying.

    factory     a Space produces an event class derived from EventBase carrying
                the type name; 'new' stamps intrinsic 'time' and 'dt'.
    signal      'signal' stamps an occurrence and records it into the bound
                Space's Tracer, returning the instance.
    untraced    before 'watch', a type has an empty history and answers every
                query as if no occurrence exists.
    flat_ring   recorded occurrences accumulate in one ring; 'last' bounds it,
                dropping the oldest first.
    queries     the eight query methods answer against the flat ring, routing
                conditions through comparators.
    isolation   two Spaces never share history; signalling into one leaves the
                other empty.
]]

local mini       = require("./hwut_runner_mini")
local bootstrap  = require("../bootstrap")
local T          = require("./test_support")

local yn, banner, cond, times = T.yn, T.banner, T.cond, T.times

--[[ RETURN: nil. Space:new_event_class derives from EventBase and stamps time/dt. ]]
local function run_factory()
    local b = bootstrap
    local space = b.Space.new()
    local PING = space:new_event_class("PING")

    banner("event class identity")
    print("className          = " .. PING.__className)
    print("derives EventBase  = " .. yn(getmetatable(PING) == b.EventBase))

    banner("instance stamps intrinsic fields")
    local ev = PING.new({ ip = "8.8.8.8" }, 10.5, 0.5)
    print("ip   = " .. ev.ip)
    print("time = " .. string.format("%g", ev.time))
    print("dt   = " .. string.format("%g", ev.dt))
end

--[[ RETURN: nil. signal stamps an occurrence and records it into the Tracer. ]]
local function run_signal()
    local b = bootstrap
    local space = b.Space.new()
    local PING = space:new_event_class("PING")
    space.tracer:watch(PING, 5)

    banner("signal returns the stamped instance")
    local ev = PING.signal({ ip = "1.1.1.1" }, 3.0, 0.0)
    print("returned time = " .. string.format("%g", ev.time))
    print("returned ip   = " .. ev.ip)

    banner("signalled occurrence is now in history")
    print("count    = " .. #PING:list({}))
    print("has(ip=1.1.1.1) = " .. yn(PING:has(cond("ip", "1.1.1.1"))))
end

--[[ RETURN: nil. An untraced type has an empty history; queries see nothing. ]]
local function run_untraced()
    local b = bootstrap
    local space = b.Space.new()
    local PING = space:new_event_class("PING")

    banner("queries on an untraced type")
    print("empty()        = " .. yn(PING:empty()))
    print("any()          = " .. yn(PING:any({})))
    print("list() count   = " .. #PING:list({}))
    print("last() is nil  = " .. yn(PING:last({}) == nil))
end

--[[ RETURN: nil. One ring per type; 'last' bounds it, dropping oldest first. ]]
local function run_flat_ring()
    local b = bootstrap
    local space = b.Space.new()
    local PING = space:new_event_class("PING")
    space.tracer:watch(PING, 3)

    banner("record four occurrences into a ring bounded at 3")
    for _, c in ipairs({ { "a", 1.0 }, { "b", 2.0 }, { "a", 3.0 }, { "c", 4.0 } }) do
        PING.signal({ ip = c[1] }, c[2], 0.0)
        print(string.format("after t=%g : ring times = %s", c[2], times(PING:list({}))))
    end

    banner("oldest dropped")
    print("retained count = " .. #PING:list({}))
end

--[[ RETURN: nil. The eight query methods answer against the flat ring. ]]
local function run_queries()
    local b = bootstrap
    local space = b.Space.new()
    local PING = space:new_event_class("PING")
    space.tracer:watch(PING, 10)
    for _, c in ipairs({ { "a", 1.0 }, { "b", 2.0 }, { "a", 3.0 } }) do
        PING.signal({ ip = c[1] }, c[2], 0.0)
    end

    banner("existence and counting")
    print("empty()            = " .. yn(PING:empty()))
    print("any()              = " .. yn(PING:any({})))
    print("has(ip=a)          = " .. yn(PING:has(cond("ip", "a"))))
    print("has(ip=z)          = " .. yn(PING:has(cond("ip", "z"))))
    print("list(ip=a) count   = " .. #PING:list(cond("ip", "a")))

    banner("all / none")
    print("all(ip=a)          = " .. yn(PING:all(cond("ip", "a"))))
    print("none(ip=z)         = " .. yn(PING:none(cond("ip", "z"))))

    banner("temporal: last / since")
    print("last() time        = " .. string.format("%g", PING:last({}).time))
    print("last(ip=a) time    = " .. string.format("%g", PING:last(cond("ip", "a")).time))
    print("since(now=10,ip=a) = " .. string.format("%g", PING:since(10.0, cond("ip", "a"))))

    banner("comparator condition: time > 1")
    print("list(time>1) count = " .. #PING:list(cond("time", b.Greater(1))))
end

--[[ RETURN: nil. Two Spaces never share history. ]]
local function run_isolation()
    local b = bootstrap
    local s1, s2 = b.Space.new(), b.Space.new()
    local P1 = s1:new_event_class("PING")
    local P2 = s2:new_event_class("PING")
    s1.tracer:watch(P1, 5)
    s2.tracer:watch(P2, 5)
    P1.signal({ ip = "a" }, 1.0, 0.0)
    P1.signal({ ip = "b" }, 2.0, 0.0)

    banner("signal into space 1 only")
    print("space 1 count = " .. #P1:list({}))
    print("space 2 count = " .. #P2:list({}))
    print("space 2 empty = " .. yn(P2:empty()))
end

local args = {...}
mini.run(args[1], "Luau bootstrap: Space, EventBase, flat Tracer, event queries", {
    factory   = run_factory,
    signal    = run_signal,
    untraced  = run_untraced,
    flat_ring = run_flat_ring,
    queries   = run_queries,
    isolation = run_isolation,
})
