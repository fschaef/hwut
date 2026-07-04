--[[ SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer

PURPOSE: Shared output helpers for the Luau bootstrap tests.

Keeps test output deterministic and readable: 'banner' prints a section
heading, 'yn' renders a boolean as a stable word, and 'times' lists the 'time'
field of every instance in a collection in its (insertion) order. Excluded from
HWUT discovery via 'hwut-info.dat'.
]]

local M = {}

--[[ RETURN: nil. Prints a blank line then a '--- label ---' heading. ]]
function M.banner(label)
    print("")
    print("--- " .. label .. " ---")
end

--[[ RETURN: string, 'yes' for a true value and 'no' for a false one. ]]
function M.yn(value)
    if value then return "yes" else return "no" end
end

--[[ RETURN: string, the 'time' fields of 'instances' joined by ', '.

'instances' is a 1-based array of event/mode instances; the order is the
collection's own stable insertion order.
]]
function M.times(instances)
    local parts = {}
    for _, inst in ipairs(instances) do
        parts[#parts + 1] = string.format("%g", inst.time)
    end
    return table.concat(parts, ", ")
end

--[[ RETURN: table, a conditions table from alternating key, value arguments.

Builds '{ k1 = v1, k2 = v2, ... }' so a query condition reads inline:
'cond("ip", "a")'.
]]
function M.cond(...)
    local a = { ... }
    local t = {}
    for i = 1, #a, 2 do t[a[i]] = a[i + 1] end
    return t
end

return M
