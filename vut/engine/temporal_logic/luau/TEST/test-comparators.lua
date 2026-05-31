#! /usr/bin/env luau
--[[ SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer

PURPOSE: Test the comparison core of the Luau bootstrap.

CHOICES: dispatch, comparators, glob, pattern;

DESCRIPTION:

The bootstrap exposes one comparison core: '_match(actual, expected)' routes to
a comparator's ':match' when 'expected' is a comparator value object, and falls
back to '==' for a literal. The comparator classes are the value objects that
participate in that dispatch.

    dispatch      _match falls back to '==' for a literal 'expected', and
                  delegates to ':match' when 'expected' is a comparator.
    comparators   the numeric/equality comparators (Approx, Less, LessEq,
                  Greater, GreaterEq, Eq, UnEq) each match as specified.
    glob          Glob translates '*', '?', and '[...]' and anchors the whole
                  string.
    pattern       Pattern matches against a Luau native string pattern.
]]

local mini       = require("./hwut_runner_mini")
local bootstrap  = require("../bootstrap")
local T          = require("./test_support")

local yn = T.yn

--[[ RETURN: nil. _match uses '==' for literals and ':match' for comparators. ]]
local function run_dispatch()
    local b = bootstrap

    T.banner("literal expected -> equality")
    print("_match(5, 5)          = " .. yn(b._match(5, 5)))
    print("_match(5, 6)          = " .. yn(b._match(5, 6)))
    print("_match('a', 'a')      = " .. yn(b._match("a", "a")))

    T.banner("comparator expected -> :match")
    print("_match(5, Greater(3)) = " .. yn(b._match(5, b.Greater(3))))
    print("_match(5, Greater(9)) = " .. yn(b._match(5, b.Greater(9))))
end

--[[ RETURN: nil. Numeric and equality comparators match per specification.

Each comparator is exercised through '_match(actual, comparator)' -- the same
dispatch path the engine uses -- rather than calling ':match' directly.
]]
local function run_comparators()
    local b = bootstrap

    T.banner("Approx(1.0, 0.05)")
    local approx = b.Approx(1.0, 0.05)
    print("1.02 -> " .. yn(b._match(1.02, approx)))
    print("1.20 -> " .. yn(b._match(1.20, approx)))

    T.banner("ordering comparators against 5")
    for _, name in ipairs({ "Less", "LessEq", "Greater", "GreaterEq" }) do
        local cmp = b[name](5)
        print(string.format("%-9s : 4=%s 5=%s 6=%s", name,
            yn(b._match(4, cmp)), yn(b._match(5, cmp)), yn(b._match(6, cmp))))
    end

    T.banner("Eq / UnEq against 5")
    local eq, uneq = b.Eq(5), b.UnEq(5)
    print("Eq   : 5=" .. yn(b._match(5, eq)) .. " 6=" .. yn(b._match(6, eq)))
    print("UnEq : 5=" .. yn(b._match(5, uneq)) .. " 6=" .. yn(b._match(6, uneq)))
end

--[[ RETURN: nil. Glob handles '*', '?', '[...]' and anchors the whole string. ]]
local function run_glob()
    local b = bootstrap
    local cases = {
        { "tester_?_intruder", "tester_4_intruder" },
        { "tester_?_intruder", "tester_44_intruder" },
        { "192.168.*",         "192.168.0.1" },
        { "192.168.*",         "10.0.0.1" },
        { "file[0-9]",         "file7" },
        { "file[0-9]",         "fileX" },
        { "abc",               "abcd" },
    }
    T.banner("Glob(pattern) matched against actual")
    for _, c in ipairs(cases) do
        print(string.format("%-20s vs %-20s -> %s",
            c[1], c[2], yn(b._match(c[2], b.Glob(c[1])))))
    end
end

--[[ RETURN: nil. Pattern matches a Luau native string pattern. ]]
local function run_pattern()
    local b = bootstrap
    local cases = {
        { "^%d+$", "123" },
        { "^%d+$", "12a" },
        { "%w+",   "word" },
        { "^%u",   "Abc" },
        { "^%u",   "abc" },
    }
    T.banner("Pattern(pattern) matched against actual")
    for _, c in ipairs(cases) do
        print(string.format("%-8s vs %-6s -> %s",
            c[1], c[2], yn(b._match(c[2], b.Pattern(c[1])))))
    end
end

local args = {...}
mini.run(args[1], "Luau bootstrap: comparison core (_match and comparators)", {
    dispatch    = run_dispatch,
    comparators = run_comparators,
    glob        = run_glob,
    pattern     = run_pattern,
})
