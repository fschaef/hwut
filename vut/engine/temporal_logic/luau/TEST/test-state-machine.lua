#! /usr/bin/env luau
--[[ SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer

PURPOSE: Test the state-machine habitat of the Luau bootstrap.

CHOICES: single_active, switched_deinit, default_restore;

DESCRIPTION:

A state machine is a habitat for member modes with single-active semantics:
arming one member deactivates the previous one (its 'switched' fires, its
'deinit' runs). An optional default member (an implicit VOID when unspecified)
becomes active when the active member ceases with no successor.

    single_active    switching to a member makes it the sole active member; the
                     previous one is no longer live.
    switched_deinit  the outgoing member's 'deinit' runs, and it sees that it
                     ceased by being switched out.
    default_restore  when the active member ceases by its own 'until' with no
                     successor, the default member is armed.
]]

local mini       = require("./hwut_runner_mini")
local bootstrap  = require("../bootstrap")
local T          = require("./test_support")

local yn, banner = T.yn, T.banner

--[[ RETURN: nil. Switching to a member makes it the sole active member. ]]
local function run_single_active()
    local b = bootstrap
    local SLEEP = b.new_mode_class("SM.SLEEP")
    local RUN = b.new_mode_class("SM.RUN")
    local SM = b.new_state_machine_class("SM")

    banner("arm SLEEP, then switch to RUN")
    local s = SLEEP.arm({}, 0.0, 0, {})
    SM.switch_to(s)
    print("active is SLEEP   = " .. yn(SM._active == s))
    print("SLEEP live        = " .. yn(not SLEEP:empty()))

    local r = RUN.arm({}, 1.0, 1, {})
    SM.switch_to(r)
    print("active is RUN     = " .. yn(SM._active == r))
    print("SLEEP live        = " .. yn(not SLEEP:empty()))
    print("RUN live          = " .. yn(not RUN:empty()))
end

--[[ RETURN: nil. The outgoing member's deinit runs and sees 'switched'. ]]
local function run_switched_deinit()
    local b = bootstrap
    local log = {}
    local SLEEP = b.new_mode_class("SM.SLEEP")
    function SLEEP:deinit()
        log[#log + 1] = "SLEEP deinit, switched=" .. yn(self._switched == true)
    end
    local RUN = b.new_mode_class("SM.RUN")
    local SM = b.new_state_machine_class("SM")

    banner("switch SLEEP out by arming RUN")
    local s = SLEEP.arm({}, 0.0, 0, {})
    SM.switch_to(s)
    local r = RUN.arm({}, 1.0, 1, {})
    SM.switch_to(r)
    for _, line in ipairs(log) do print(line) end
    print("SLEEP empty       = " .. yn(SLEEP:empty()))
end

--[[ RETURN: nil. Default member is armed when the active one ceases unsucceeded. ]]
local function run_default_restore()
    local b = bootstrap
    local ACTIVE = b.new_mode_class("SM.ACTIVE")
    local VOID = b.new_mode_class("SM.VOID")
    local SM = b.new_state_machine_class("SM")
    -- default arms a VOID member
    SM.set_default(function()
        local v = VOID.arm({}, 9.0, 9, {})
        return v
    end)
    ACTIVE.add_until(function(self, ev) return ev.k == "DONE" end)

    banner("active member ceases by its own until")
    local a = ACTIVE.arm({}, 0.0, 0, {})
    SM.switch_to(a)
    print("active is ACTIVE  = " .. yn(SM._active == a))

    ACTIVE.check_until(a, { k = "DONE" })
    SM.ensure_active()
    print("ACTIVE empty      = " .. yn(ACTIVE:empty()))
    print("default restored  = " .. yn(not VOID:empty()))
    print("active is VOID    = " .. yn(SM._active ~= nil and SM._active ~= a))
end

local args = {...}
mini.run(args[1], "Luau bootstrap: state-machine habitat", {
    single_active   = run_single_active,
    switched_deinit = run_switched_deinit,
    default_restore = run_default_restore,
})
