-- SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
-- ---------------------------------------------------------------------------
--
-- THE EDITOR HALF, DRIVEN BY A REAL NEOVIM.
--
--     UNIT     'view.lua' -- two panes from two lists of lines.
--
--     CAUSAL CONTRACT
--              two vertical panes appear, subject left and nominal right,
--              one screen line per compare ROW; the cursor starts in the
--              nominal pane; a commit carries the nominal pane's plain
--              text.
--
--     CONSISTENCY CONTRACT
--              the subject pane REFUSES a change -- editing what the run
--              produced would merge into a fiction; the panes are
--              scroll-bound, so a row never drifts from its counterpart;
--              closing leaves no window behind.
--
--     Run headlessly: 'nvim -l test-view.lua <choice>'.
-- ---------------------------------------------------------------------------

package.path = vim.fn.fnamemodify("../lua/?.lua", ":p") .. ";" .. package.path
local view = require("vut_merge.view")

local SUBJECT = { "alpha", "WRONG", "gamma" }
local NOMINAL = { "alpha", "beta",  "gamma" }

--- RETURN: true, every claim held; false, at least one did not.
local function check(claim_list)
    local ok = true
    for _, pair in ipairs(claim_list) do
        print(string.format("  %s: %s", pair[1] and "OK  " or "FAIL", pair[2]))
        if not pair[1] then ok = false end
    end
    return ok
end

--- RETURN: None. Prints the one closing line HWUT greps for.
local function verdict(ok, sentence)
    print(string.format("%s: %s", ok and "SUCCESS" or "FAILURE", sentence))
end

local choice_map = {}

--- RETURN: None. Two panes, the alignment compare gave, not neovim's own.
choice_map.panes = function()
    local session = view.open(SUBJECT, NOMINAL)
    local subject_line = vim.api.nvim_buf_get_lines(session.subject_buf,
                                                    0, -1, false)
    local nominal_line = vim.api.nvim_buf_get_lines(session.nominal_buf,
                                                    0, -1, false)
    local diff_on = vim.api.nvim_get_option_value("diff",
                                                  { win = session.subject_win })
    print("INSPECT: subject pane = " .. table.concat(subject_line, " | "))
    print("         nominal pane = " .. table.concat(nominal_line, " | "))
    print("         rows equal   = " ..
          tostring(#subject_line == #nominal_line))
    print("         neovim's own diff engaged = " .. tostring(diff_on))
    local ok = check({
        { #subject_line == 3 and #nominal_line == 3,
          "one screen line per compare row, on both sides" },
        { subject_line[2] == "WRONG" and nominal_line[2] == "beta",
          "and the rows stand beside their counterparts" },
        { diff_on == false,
          "neovim's OWN diff is not engaged -- the alignment shown is " ..
          "compare's, not a second opinion beside it" },
    })
    view.close(session)
    verdict(ok, "the panes show compare's alignment, one row per line.")
end

--- RETURN: None. The subject is what the run produced; it is not editable.
choice_map.subject_protected = function()
    local session = view.open(SUBJECT, NOMINAL)
    local protected = view.subject_is_protected(session)
    local edited = pcall(vim.api.nvim_buf_set_lines, session.nominal_buf,
                         1, 2, false, { "beta EDITED" })
    local after = vim.api.nvim_buf_get_lines(session.nominal_buf, 0, -1, false)
    print("INSPECT: subject pane refused a change = " .. tostring(protected))
    print("         nominal pane accepted one     = " .. tostring(edited))
    print("         nominal now = " .. table.concat(after, " | "))
    local ok = check({
        { protected,
          "the subject pane REFUSES an edit" },
        { edited and after[2] == "beta EDITED",
          "and the nominal pane accepts one" },
    })
    view.close(session)
    verdict(ok, "only the nominal is the author's to change.")
end

--- RETURN: None. A commit carries the pane's plain text, not a rendering.
choice_map.commit_carries_text = function()
    local session = view.open(SUBJECT, NOMINAL)
    vim.api.nvim_buf_set_lines(session.nominal_buf, 1, 2, false,
                               { "beta RESOLVED" })
    local carried = view.nominal_text(session)
    local decision = {}
    view.bind(session,
              function() decision[#decision + 1] = "commit" end,
              function() decision[#decision + 1] = "cancel" end)
    vim.cmd("VutCommit")
    vim.cmd("VutCancel")
    print("INSPECT: carried = " .. string.format("%q", carried))
    print("         decisions taken = " .. table.concat(decision, ", "))
    local ok = check({
        { carried == "alpha\nbeta RESOLVED\ngamma\n",
          "the commit carries the pane's PLAIN text, ending in a newline" },
        { decision[1] == "commit" and decision[2] == "cancel",
          "both decisions are bound, and nothing else is" },
    })
    view.close(session)
    verdict(ok, "what is stored is the material, never a rendering.")
end

--- RETURN: None. Panes stay level, and closing leaves nothing behind.
choice_map.bound_and_closed = function()
    local before = #vim.api.nvim_list_wins()
    local session = view.open(SUBJECT, NOMINAL)
    local bound = vim.api.nvim_get_option_value("scrollbind",
                                                { win = session.subject_win })
                  and vim.api.nvim_get_option_value("scrollbind",
                                                { win = session.nominal_win })
    local cursor_in_nominal =
        vim.api.nvim_get_current_win() == session.nominal_win
    view.close(session)
    local after = #vim.api.nvim_list_wins()
    print("INSPECT: both panes scroll-bound   = " .. tostring(bound))
    print("         cursor starts in nominal  = " .. tostring(cursor_in_nominal))
    print("         windows before / after    = " ..
          tostring(before) .. " / " .. tostring(after))
    local scratch_gone = not vim.api.nvim_buf_is_valid(session.subject_buf)
    local ok = check({
        { bound,
          "both panes are scroll-bound, so a row never drifts from its pair" },
        { cursor_in_nominal,
          "the cursor starts where the author may type" },
        { after == before,
          "the layout it borrowed is RESTORED, pane for pane" },
        { scratch_gone,
          "and its scratch buffers are gone -- nothing left to stumble on" },
    })
    verdict(ok, "level, focused, and tidy on the way out.")
end

local choice = _G.arg and _G.arg[1] or nil
if choice == "--hwut-info" then
    print("The editor half, driven by a real neovim;")
    local name_list = {}
    for name, _ in pairs(choice_map) do name_list[#name_list + 1] = name end
    table.sort(name_list)
    print("CHOICES: " .. table.concat(name_list, ", ") .. ";")
    print("HAPPY: SUCCESS.*;")
elseif choice_map[choice] then
    choice_map[choice]()
else
    print("FAILURE: no such choice: " .. tostring(choice))
end
