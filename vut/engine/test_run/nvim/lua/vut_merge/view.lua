-- SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
-- ---------------------------------------------------------------------------
--
-- PURPOSE
--        THE EDITOR HALF -- a folded DOWN view, shown as two panes.
--
-- DESCRIPTION
--        'protocol.lua' folds a DOWN stream into a view and knows nothing
--        of neovim. This knows neovim and nothing of the protocol: it is
--        handed two lists of lines and puts them on the screen.
--
--        THE ALIGNMENT SHOWN IS COMPARE'S. Neovim has its own diff, and
--        using it here would show a SECOND opinion beside the one under
--        test -- two alignments disagreeing, with no way to tell which
--        the verdict came from. So the panes carry compare's rows, one
--        screen line per row, and 'scrollbind' keeps them level.
--
--        THE AUTHOR EDITS THE NOMINAL PANE, and only it. The subject is
--        what the run produced; editing it would merge into a fiction.
-- ---------------------------------------------------------------------------

local M = {}

M.SUBJECT_TITLE = "vut://subject  (read-only -- what the run produced)"
M.NOMINAL_TITLE = "vut://nominal  (edit here, then :VutCommit)"

--- RETURN: number, a scratch buffer holding 'line_list'.
---         'modifiable' false makes a pane read-only.
local function scratch(line_list, name, modifiable)
    local buf = vim.api.nvim_create_buf(false, true)
    vim.api.nvim_buf_set_lines(buf, 0, -1, false, line_list)
    vim.api.nvim_buf_set_name(buf, name)
    vim.api.nvim_set_option_value("buftype", "nofile", { buf = buf })
    vim.api.nvim_set_option_value("modifiable", modifiable, { buf = buf })
    return buf
end

--- RETURN: table, the opened session
---           { subject_buf, nominal_buf, subject_win, nominal_win }
---
--- Two vertical panes, subject left and nominal right, scroll-bound so a
--- row stays beside its counterpart. The nominal pane takes the cursor,
--- since it is the only one the author may change.
function M.open(subject_list, nominal_list)
    local subject_buf = scratch(subject_list, M.SUBJECT_TITLE, false)
    local nominal_buf = scratch(nominal_list, M.NOMINAL_TITLE, true)

    local restore_buf = vim.api.nvim_get_current_buf()
    vim.cmd("silent! only")
    local subject_win = vim.api.nvim_get_current_win()
    vim.api.nvim_win_set_buf(subject_win, subject_buf)
    vim.cmd("vsplit")
    local nominal_win = vim.api.nvim_get_current_win()
    vim.api.nvim_win_set_buf(nominal_win, nominal_buf)

    for _, win in ipairs({ subject_win, nominal_win }) do
        vim.api.nvim_set_option_value("scrollbind", true, { win = win })
        vim.api.nvim_set_option_value("wrap",       false, { win = win })
        vim.api.nvim_set_option_value("number",     true,  { win = win })
    end
    vim.api.nvim_set_current_win(nominal_win)

    return { subject_buf = subject_buf, nominal_buf = nominal_buf,
             subject_win = subject_win, nominal_win = nominal_win,
             restore_buf = restore_buf }
end

--- RETURN: string, the nominal pane's content -- the ARTIFACT a COMMIT
---         carries. Plain text, never a rendering of the view: what is
---         stored must be the material, or the next comparison is made
---         against something nobody wrote.
function M.nominal_text(session)
    local line_list = vim.api.nvim_buf_get_lines(session.nominal_buf,
                                                 0, -1, false)
    return table.concat(line_list, "\n") .. "\n"
end

--- RETURN: true, the subject pane refused a change.
---         false, it accepted one -- which must never happen.
function M.subject_is_protected(session)
    local ok = pcall(vim.api.nvim_buf_set_lines,
                     session.subject_buf, 0, -1, false, { "tampered" })
    return not ok
end

--- RETURN: None. Binds the two decisions an author can take. Nothing else
---         is bound: a merge tool that invents keys fights its editor.
function M.bind(session, on_commit, on_cancel)
    local function map(key, fn)
        vim.keymap.set("n", key, fn, { buffer = session.nominal_buf })
    end
    map("<localleader>c", on_commit)
    map("<localleader>q", on_cancel)
    vim.api.nvim_buf_create_user_command(session.nominal_buf,
        "VutCommit", on_commit, {})
    vim.api.nvim_buf_create_user_command(session.nominal_buf,
        "VutCancel", on_cancel, {})
end

--- RETURN: None. RESTORES THE LAYOUT the session took. Called however
---         the session ended, so a cancelled merge leaves no pane behind.
---
--- The last window is never closed -- an editor cannot have none, and a
--- merge tool that empties the screen it borrowed is a rude one. Its
--- buffer is put back instead.
function M.close(session)
    if vim.api.nvim_win_is_valid(session.nominal_win)
       and #vim.api.nvim_list_wins() > 1 then
        vim.api.nvim_win_close(session.nominal_win, true)
    end
    if vim.api.nvim_win_is_valid(session.subject_win) then
        if #vim.api.nvim_list_wins() > 1 then
            vim.api.nvim_win_close(session.subject_win, true)
        elseif vim.api.nvim_buf_is_valid(session.restore_buf) then
            vim.api.nvim_win_set_buf(session.subject_win, session.restore_buf)
        end
    end
    for _, buf in ipairs({ session.subject_buf, session.nominal_buf }) do
        if vim.api.nvim_buf_is_valid(buf) then
            vim.api.nvim_buf_delete(buf, { force = true })
        end
    end
end

return M
