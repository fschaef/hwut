-- SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
-- ---------------------------------------------------------------------------
--
-- PURPOSE
--        THE PROTOCOL LAYER of the vut merge plugin -- and the whole of
--        what this plugin adds.
--
-- DESCRIPTION
--        Two functions and no neovim call: fold a DOWN stream into a view,
--        and fold a decision into an UP envelope. Everything else the
--        plugin does -- buffers, diff mode, keys, streams -- is neovim's
--        and lives in 'init.lua'.
--
--        NOTHING HERE NAMES A COMPARE ITEM'S FIELDS. A message carries a
--        'kind' and a 'field_db'; the view keeps whatever arrived. So a
--        kind compare invents later is displayed the day it is emitted,
--        with no edit here.
--
--        REFUSE RATHER THAN GUESS. A message under a signature this
--        version cannot parse is refused BEFORE it is read; so is a
--        commit carrying no artifact. Both would otherwise show the
--        author something, or store something, that nobody sent.
-- ---------------------------------------------------------------------------

local M = {}

M.SIGNATURE = "vut-feed/1"

M.INTENT = { REALIGN = "realign", COMMIT = "commit", CANCEL = "cancel" }

--- RETURN: a fresh view -- what has arrived so far, and nothing else.
---         'line_pair_list' holds the alignment in arrival order;
---         'other_list' holds every message that is not a pair, so a kind
---         this version has never seen is still SHOWN rather than lost.
function M.new_view()
    return { subject_name   = nil,
             line_pair_list = {},
             other_list     = {},
             ended          = false,
             refusal        = nil }
end

--- RETURN: true, the message was taken into the view.
---         false plus a reason, it was refused.
---
--- A refused view keeps its reason, so the plugin can say WHY it is
--- showing nothing instead of showing an empty diff.
function M.accept(view, message)
    if type(message) ~= "table" then
        view.refusal = "a message that is not a record"
        return false, view.refusal
    end
    if message.signature ~= M.SIGNATURE then
        view.refusal = string.format(
            "protocol %s cannot be parsed by %s -- refusing rather than "
            .. "mis-reading", tostring(message.signature), M.SIGNATURE)
        return false, view.refusal
    end

    local kind     = message.kind or "<unnamed>"
    local field_db = message.field_db or {}

    if kind == "EndOfStreamInst" then
        view.ended = true
    elseif kind == "LinePairInst" then
        view.line_pair_list[#view.line_pair_list + 1] = field_db
    else
        view.other_list[#view.other_list + 1] = { kind = kind,
                                                  field_db = field_db }
    end
    return true
end

--- RETURN: the number of aligned rows the view holds.
function M.pair_count(view)
    return #view.line_pair_list
end

--- RETURN: true, the stream ended as the protocol says it must.
---         false, it merely stopped -- which is not the same thing, and
---         a view that merely stopped is INCOMPLETE, never 'all of it'.
function M.is_complete(view)
    return view.ended and view.refusal == nil
end

--- RETURN: the UP envelope for a decision: a table ready for
---         'vim.json.encode'.
---
--- A COMMIT carrying no text is downgraded to CANCEL. Committing an
--- absent artifact would store emptiness as the accepted behaviour, and
--- the author would never learn that the merge had produced nothing.
function M.resolution(intent, nominal_text)
    if intent == M.INTENT.COMMIT and (nominal_text == nil
                                      or nominal_text == "") then
        intent = M.INTENT.CANCEL
    end
    if intent == M.INTENT.CANCEL then nominal_text = nil end
    return { signature = M.SIGNATURE,
             intent    = intent,
             nominal   = nominal_text }
end

--- RETURN: two lists of strings -- the subject side and the nominal side
---         of the alignment, in arrival order, ready to become two
---         buffers in diff mode.
---         nil plus a reason, if the rows do not carry the two sides
---         under the names this version reads.
---
--- IT DOES NOT GUESS. An earlier version tried several plausible field
--- names and produced EMPTY rows when none matched -- a diff of nothing
--- against nothing, shown as though it were the comparison. Absent is
--- not empty: a row whose sides cannot be found is REFUSED, and the
--- plugin says so rather than showing a blank pane.
---
--- 'CELLS' and the two cell fields are the only compare names this file
--- knows. Everything else about a message is carried without being named.
---
--- A row's text lives in its CELLS, which the hub sends as nested maps --
--- so a cell is read, never parsed out of a rendering.
M.SUBJECT_CELLS = "cells_s"
M.NOMINAL_CELLS = "cells_n"
M.SUBJECT_TEXT  = "subject"
M.NOMINAL_TEXT  = "nominal"

--- RETURN: string, the joined text of a cell list.
---         nil,    the field is absent or is not a list of cells.
local function cell_text(cell_list, field)
    if type(cell_list) ~= "table" then return nil end
    local part_list = {}
    for _, cell in ipairs(cell_list) do
        if type(cell) ~= "table" then return nil end
        part_list[#part_list + 1] = tostring(cell[field] or "")
    end
    return table.concat(part_list, "")
end

function M.two_sides(view)
    local subject_list, nominal_list = {}, {}
    for i, field_db in ipairs(view.line_pair_list) do
        local subject = cell_text(field_db[M.SUBJECT_CELLS], M.SUBJECT_TEXT)
        local nominal = cell_text(field_db[M.NOMINAL_CELLS], M.NOMINAL_TEXT)
        if subject == nil and nominal == nil then
            return nil, string.format(
                "row %d carries neither '%s' nor '%s' as readable cells -- "
                .. "this DOWN stream does not carry the two sides in a form "
                .. "a client can read", i, M.SUBJECT_CELLS, M.NOMINAL_CELLS)
        end
        subject_list[i] = subject or ""
        nominal_list[i] = nominal or ""
    end
    return subject_list, nominal_list
end

return M
