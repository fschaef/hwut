#! /usr/bin/env lua5.4
-- SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
-- ---------------------------------------------------------------------------
--
-- THE MERGE PLUGIN'S PROTOCOL LAYER.
--
--     UNIT     'vut_merge.protocol' -- the whole of what the plugin adds.
--              Buffers, diff mode and keys are neovim's; nothing here
--              calls neovim, which is why this runs under plain Lua.
--
--     CAUSAL CONTRACT
--              a real DOWN stream folds into a view; the view yields two
--              sides of EQUAL length, so neovim's diff shows the
--              alignment COMPARE made rather than one it re-derives; a
--              decision folds into an UP envelope.
--
--     CONSISTENCY CONTRACT
--              a foreign signature is refused BEFORE the message is read;
--              a kind this version has never seen is SHOWN, not lost; a
--              stream that merely stopped is not 'all of it'; a COMMIT
--              with no artifact is downgraded to CANCEL.
--
--     HWUT does not care what language a test is written in. This one is
--     Lua, prints its choices, and is judged by its GOOD file exactly as
--     the Python ones are.
-- ---------------------------------------------------------------------------

package.path = (arg[0]:match("(.*)/") or ".") .. "/../lua/?.lua;" ..
               (arg[0]:match("(.*)/") or ".") .. "/../lua/?/init.lua;" ..
               package.path

local protocol = require("vut_merge.protocol")
local HERE     = (arg[0]:match("(.*)/") or ".")

--- RETURN: true if every claim held, false otherwise. Prints one line
---         per claim, so a failure names itself.
local function check(claim_list)
    local ok = true
    for _, pair in ipairs(claim_list) do
        print(string.format("  %s: %s", pair[1] and "OK  " or "FAIL",
                            pair[2]))
        if not pair[1] then ok = false end
    end
    return ok
end

--- RETURN: nil. Prints the one closing line HWUT greps for.
local function verdict(ok, sentence)
    print(string.format("%s: %s", ok and "SUCCESS" or "FAILURE", sentence))
end

--- RETURN: the captured DOWN stream of the real compare engine.
local function fixture()
    return dofile(HERE .. "/down_fixture.lua")
end

--- RETURN: a view with the whole fixture folded into it.
local function folded()
    local view = protocol.new_view()
    for _, message in ipairs(fixture()) do protocol.accept(view, message) end
    return view
end

local choice_db = {}

--- A REAL DOWN STREAM folds into a view. The fixture is captured from the
--- compare engine itself, so this is what compare emits and not what
--- somebody believed it emits.
choice_db.fold = function()
    local view = folded()
    print("INSPECT: kinds carried:")
    for _, message in ipairs(fixture()) do
        print("           " .. message.kind)
    end
    print(string.format("         aligned rows = %d, complete = %s",
                        protocol.pair_count(view),
                        tostring(protocol.is_complete(view))))
    return check({
        { protocol.pair_count(view) == 3,
          "one aligned row per line pair of the comparison" },
        { protocol.is_complete(view),
          "the stream ENDED, it did not merely stop" },
        { #view.other_list == 3,
          "the header, the setup and the section are kept, not discarded" },
        { view.refusal == nil,
          "nothing was refused" },
    }), "a real DOWN stream folds into a view."
end

--- THE TWO SIDES ARE THE SAME LENGTH, always. That is the whole reason a
--- plugin exists beside 'nvim -d': neovim's diff then shows the alignment
--- COMPARE made, instead of re-deriving one of its own.
choice_db.two_sides = function()
    local view = folded()
    local subject_list, nominal_list = protocol.two_sides(view)

    local unreadable = protocol.new_view()
    for _, message in ipairs({
        { signature = protocol.SIGNATURE, kind = "LinePairInst",
          field_db = { cells_s = "SubjectCell(subject='alpha')",
                       cells_n = "NominalCell(nominal='alpha')" } },
        { signature = protocol.SIGNATURE, kind = "EndOfStreamInst",
          field_db = {} }}) do protocol.accept(unreadable, message) end
    local refused, reason = protocol.two_sides(unreadable)

    print("INSPECT: today's DOWN stream, row for row:")
    for i = 1, #subject_list do
        print(string.format("           %-8s | %s",
                            subject_list[i], nominal_list[i]))
    end
    print("         a stream carrying cells as TEXT -> " ..
          (refused == nil and "REFUSED" or "accepted"))
    print("         reason: " .. (reason or ""):sub(1, 54))
    return check({
        { subject_list ~= nil and #subject_list == #nominal_list,
          "the two sides are read from the CELLS, and are the same length" },
        { subject_list[2] == "WRONG" and nominal_list[2] == "beta",
          "row for row, the alignment COMPARE made" },
        { subject_list[1] == "alpha" and subject_list[3] == "gamma",
          "and the rows that agree carry their text too" },
        { refused == nil and reason ~= nil,
          "a stream whose cells are NOT readable is refused, with a " ..
          "reason -- never rendered as blank panes" },
    }), "the alignment shown is compare's, or none is shown."
end

--- A KIND THIS VERSION HAS NEVER SEEN is shown, not lost. Compare may
--- widen its output without the plugin being edited.
choice_db.unknown_kind = function()
    local view = protocol.new_view()
    protocol.accept(view, { signature = protocol.SIGNATURE,
                            kind      = "ProvenanceInst",
                            field_db  = { origin = "analogy-db",
                                          confidence = 0.91 } })
    local kept = view.other_list[1]
    print(string.format("INSPECT: a kind never seen before: %s", kept.kind))
    print(string.format("         its fields survived: origin=%s confidence=%s",
                        tostring(kept.field_db.origin),
                        tostring(kept.field_db.confidence)))
    return check({
        { kept.kind == "ProvenanceInst",
          "an unknown kind is KEPT under its own name" },
        { kept.field_db.origin == "analogy-db",
          "with its fields intact, though this version names none of them" },
    }), "compare may widen its output; the plugin needs no edit."
end

--- REFUSE RATHER THAN GUESS. A foreign signature is refused before the
--- message is read, and the view says WHY it is showing nothing.
choice_db.foreign = function()
    local view = protocol.new_view()
    local ok, reason = protocol.accept(view, { signature = "some-other/9",
                                               kind = "LinePairInst" })
    local after = protocol.pair_count(view)
    print(string.format("INSPECT: a message under 'some-other/9' -> %s",
                        tostring(ok)))
    print(string.format("         reason kept: %s",
                        (reason or ""):sub(1, 52)))
    print(string.format("         rows taken from it: %d", after))
    return check({
        { ok == false, "the message is refused" },
        { after == 0,  "and nothing of it enters the view" },
        { view.refusal ~= nil,
          "the view keeps WHY, so it can say that rather than show an "
          .. "empty diff" },
        { protocol.is_complete(view) == false,
          "and a refused view is never 'complete'" },
    }), "refuse before reading; never mis-read."
end

--- A STREAM THAT MERELY STOPPED IS NOT ALL OF IT. Without the explicit
--- end, a truncated comparison would be edited as though it were whole.
choice_db.truncated = function()
    local view = protocol.new_view()
    local all  = fixture()
    for i = 1, #all - 1 do protocol.accept(view, all[i]) end   -- drop the end
    local whole = folded()
    print(string.format("INSPECT: every message but the last -> complete = %s",
                        tostring(protocol.is_complete(view))))
    print(string.format("         the whole stream           -> complete = %s",
                        tostring(protocol.is_complete(whole))))
    return check({
        { protocol.is_complete(view) == false,
          "a stream that stopped is INCOMPLETE" },
        { protocol.pair_count(view) == protocol.pair_count(whole),
          "though it carried every row -- stopping is not emptiness" },
        { protocol.is_complete(whole),
          "only an explicit end makes a view complete" },
    }), "stopping and ending are not the same thing."
end

--- THE UP ENVELOPE. A COMMIT with no artifact is downgraded to CANCEL:
--- committing an absent stream would store emptiness as the accepted
--- behaviour.
choice_db.envelope = function()
    local committed = protocol.resolution(protocol.INTENT.COMMIT,
                                          "merged text\n")
    local hollow    = protocol.resolution(protocol.INTENT.COMMIT, "")
    local cancelled = protocol.resolution(protocol.INTENT.CANCEL,
                                          "ignored text")
    for _, row in ipairs({ { "commit with text", committed },
                           { "commit with none", hollow },
                           { "cancel",           cancelled } }) do
        print(string.format("INSPECT: %-17s -> intent %-8s nominal %s",
                            row[1], row[2].intent,
                            row[2].nominal and
                            string.format("%q", row[2].nominal) or "nil"))
    end
    return check({
        { committed.intent == "commit" and
          committed.nominal == "merged text\n",
          "a commit carries the plain artifact" },
        { hollow.intent == "cancel",
          "a commit with NO artifact is downgraded to CANCEL" },
        { cancelled.nominal == nil,
          "a cancel carries nothing, whatever it was handed" },
        { committed.signature == protocol.SIGNATURE,
          "every envelope is signed" },
    }), "an empty commit is refused, not stored."
end

-- ---------------------------------------------------------------------------
-- The HWUT contract: '--hwut-info' lists the choices; a choice name runs it.
-- ---------------------------------------------------------------------------
local name_list = {}
for name in pairs(choice_db) do name_list[#name_list + 1] = name end
table.sort(name_list)

if arg[1] == nil or arg[1] == "--hwut-info" then
    print("The merge plugin's protocol layer (Lua);")
    print("CHOICES: " .. table.concat(name_list, ", ") .. ";")
    print("HAPPY: SUCCESS.*;")
    os.exit(0)
end

local choice = choice_db[arg[1]]
if choice == nil then
    print("FAILURE: no choice named '" .. tostring(arg[1]) .. "'")
    os.exit(1)
end
local ok, sentence = choice()
verdict(ok, sentence)
