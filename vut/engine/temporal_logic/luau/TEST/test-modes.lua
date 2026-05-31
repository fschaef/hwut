#! /usr/bin/env luau
--[[ SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer

PURPOSE: Test the mode lifecycle of the Luau bootstrap.

CHOICES: identity, init_deinit, first_wins, stamps, registry;

DESCRIPTION:

A mode class is a Queryable registry of its live instances and owns the shared
lifecycle: identity by parameter list (idempotent arming), 'init'/'deinit' once
each, an 'until' list checked first-wins, and the engine-stamped 'begin_time' /
'begin_event_index'.

    identity      arming with identical parameters returns the existing
                  instance; 'init' is not re-run and the registry stays at one.
    init_deinit   'init' runs once at arming; 'deinit' runs once at cessation.
    first_wins    the first 'until' to fire ceases the instance; no later
                  'until' is consulted.
    stamps        an instance carries the engine-stamped 'begin_time' and
                  'begin_event_index'; its parameters are readable.
    registry      the query methods answer against the live-instance set.
]]

local mini       = require("./hwut_runner_mini")
local bootstrap  = require("../bootstrap")
local T          = require("./test_support")

local yn, banner, cond = T.yn, T.banner, T.cond

--[[ RETURN: mode class WATCH(req), with init/deinit that log via 'log'.

Builds a mode kind whose 'init'/'deinit' append a line to 'log' so the test can
observe how often each hook runs.
]]
local function make_watch(b, log)
    local W = b.new_mode_class("WATCH")
    function W:init() log[#log + 1] = "init req=" .. tostring(self.req) end
    function W:deinit() log[#log + 1] = "deinit req=" .. tostring(self.req) end
    return W
end

--[[ RETURN: nil. Arming identical parameters is an idempotent no-op. ]]
local function run_identity()
    local b = bootstrap
    local log = {}
    local W = make_watch(b, log)

    banner("arm twice with identical parameters")
    local a = W.arm({ req = 1 }, 0.0, 0, { "req" })
    local a2 = W.arm({ req = 1 }, 0.2, 1, { "req" })
    print("same instance     = " .. yn(a == a2))
    print("live count        = " .. #W:list({}))
    print("init calls so far = " .. #log)

    banner("arm a different parameter set")
    W.arm({ req = 2 }, 0.3, 2, { "req" })
    print("live count        = " .. #W:list({}))
end

--[[ RETURN: nil. init runs once at arming, deinit once at cessation. ]]
local function run_init_deinit()
    local b = bootstrap
    local log = {}
    local W = make_watch(b, log)
    W.add_until(function(self, ev) return ev.k == "ACK" and ev.req == self.req end)

    banner("arm -> init")
    local a = W.arm({ req = 7 }, 0.0, 0, { "req" })
    for _, line in ipairs(log) do print(line) end

    banner("until fires -> deinit")
    W.check_until(a, { k = "ACK", req = 7 })
    print(log[#log])
    print("empty after cease = " .. yn(W:empty()))
end

--[[ RETURN: nil. The first 'until' to fire wins; no later 'until' is checked. ]]
local function run_first_wins()
    local b = bootstrap
    local order = {}
    local W = b.new_mode_class("DEADLINE")
    -- two until clauses; the first matches, so the second must not be consulted
    W.add_until(function(self, ev)
        order[#order + 1] = "checked until #1"
        return ev.k == "ACK"
    end)
    W.add_until(function(self, ev)
        order[#order + 1] = "checked until #2"
        return ev.k == "TICK"
    end)

    banner("event matches the first until")
    local a = W.arm({ id = 1 }, 0.0, 0, { "id" })
    local fired = W.check_until(a, { k = "ACK" })
    print("until fired       = " .. yn(fired))
    for _, line in ipairs(order) do print(line) end
    print("second consulted  = " .. yn(#order == 2))
end

--[[ RETURN: nil. Engine-stamped begin_time / begin_event_index and parameters. ]]
local function run_stamps()
    local b = bootstrap
    local W = b.new_mode_class("WATCH")

    banner("engine-stamped members")
    local a = W.arm({ req = 42 }, 12.5, 3, { "req" })
    print("req               = " .. tostring(a.req))
    print("begin_time        = " .. string.format("%g", a.begin_time))
    print("begin_event_index = " .. tostring(a.begin_event_index))
end

--[[ RETURN: nil. The query methods answer against the live-instance set. ]]
local function run_registry()
    local b = bootstrap
    local W = b.new_mode_class("PORT_WATCHER")
    W.arm({ port = 80 }, 0.0, 0, { "port" })
    W.arm({ port = 80 }, 0.0, 0, { "port" })   -- idempotent: same instance
    W.arm({ port = 443 }, 1.0, 1, { "port" })

    banner("counting and existence")
    print("empty()              = " .. yn(W:empty()))
    print("any()                = " .. yn(W:any({})))
    print("list() count         = " .. #W:list({}))
    print("list(port=80) count  = " .. #W:list(cond("port", 80)))
    print("has(port=443)        = " .. yn(W:has(cond("port", 443))))
    print("has(port=22)         = " .. yn(W:has(cond("port", 22))))

    banner("comparator condition: port > 100")
    print("any(port>100)        = " .. yn(W:any(cond("port", b.Greater(100)))))
    print("none(port>1000)      = " .. yn(W:none(cond("port", b.Greater(1000)))))
end

local args = {...}
mini.run(args[1], "Luau bootstrap: mode lifecycle", {
    identity    = run_identity,
    init_deinit = run_init_deinit,
    first_wins  = run_first_wins,
    stamps      = run_stamps,
    registry    = run_registry,
})
