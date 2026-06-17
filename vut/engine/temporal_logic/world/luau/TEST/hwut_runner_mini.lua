--[[ SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer

PURPOSE: Minimal HWUT runner for Luau tests in this directory.

The (old) HWUT framework needs two behaviours from a test executable:

  * given the argument '--hwut-info', print the test title followed by ';' and a
    newline, then a line 'CHOICES:' listing the available choices; and
  * given a choice name as the first argument, run the matching test function.

Nothing more is required here -- no interactive mode, no threading, no
suggestion engine. The first program argument (delivered by the
'./call_luau.sh *.lua -a' wrapper as a vararg) is taken as the choice.

USAGE (from a test file):

    local mini = require("./hwut_runner_mini")
    local args = {...}
    mini.run(args[1], "My Title", {
        choice_a = function() ... end,
        choice_b = function() ... end,
    })
]]

local M = {}

--[[ RETURN: array, the keys of 'choice_map' sorted alphabetically.

The stable choice ordering printed under '--hwut-info'.
]]
local function sorted_keys(choice_map)
    local keys = {}
    for k in pairs(choice_map) do keys[#keys + 1] = k end
    table.sort(keys)
    return keys
end

--[[ RETURN: nil

Prints the '--hwut-info' block: the title (a ';' is appended unless already
present) on its own line, then a 'CHOICES:' line with each choice
comma-separated and ending with a ';'. This is the shape the HWUT framework
parses.
]]
--[[ RETURN: nil

Prints the '--hwut-info' block: the title (a ';' is appended unless already
present) on its own line, then a 'CHOICES:' line with each choice
comma-separated and ending with a ';'.
]]
local function print_info(title, choices)
    if string.sub(title, -1) == ";" then
        print(title)
    else
        print(title .. ";")
    end
    -- Use the default print behavior which handles the terminating newline.
    print("CHOICES: " .. table.concat(choices, ", ") .. ";")
end

--[[ RETURN: nil

The single entry point. 'choice' is the first program argument; 'title' is the
suite title; 'choice_map' maps a choice name to a zero-argument function.

  * choice '--hwut-info' (or nil/empty) prints the info block;
  * a known choice runs its function;
  * an unknown choice prints an error line listing the available choices.
]]
function M.run(choice, title, choice_map)
    local choices = sorted_keys(choice_map)

    if choice == "--hwut-info" or choice == nil or choice == "" then
        print_info(title, choices)
        return
    end

    local fn = choice_map[choice]
    if fn == nil then
        print("error: choice '" .. tostring(choice) .. "' not available.")
        print("error: available: " .. table.concat(choices, ", ") .. ".")
        return
    end

    fn()
end

return M
