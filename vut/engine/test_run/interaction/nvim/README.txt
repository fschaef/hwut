============================================================================
VUT-MERGE -- NEOVIM, TWO TIERS
============================================================================

TIER 1 NEEDS NO PLUGIN. Neovim is already a merge tool, and the component
already drives merge tools ('MergeToolDisplay'). Nothing new is written:

    from vut.engine.test_run.feed import MergeToolDisplay

    driver = MergeToolDisplay(
        ["nvim", "-d", "{subject}", "{nominal}",
         "-c", "wincmd l", "-c", "file {merged}"],
        work_directory)

  The author diffs, edits, ':wq'. A tool that exits non-zero, or leaves
  no merged file, CANCELS -- an abandoned merge never becomes a nominal.
  Neovim's own diff, its own keys, its own configuration.

TIER 2 IS THE PLUGIN, and it exists for ONE thing tier 1 cannot do: show
the comparison AS COMPARE SEES IT. Tier 1 diffs two texts and re-derives
an alignment neovim invented; the plugin receives the alignment compare
ALREADY MADE -- its sections, its analogies, its tolerances -- so what
the author edits is what the verdict was about.

    DOWN   one JSON message per line on stdin, each with 'signature',
           'kind' and 'field_db'                 (RemoteDisplay)
    UP     one JSON envelope on stdout           (resolution_of)

WHAT IS BUILT ON WHAT
    vim.json          decoding and encoding      -- neovim's
    diff mode         side by side, folds, keys  -- neovim's
    the protocol      'vut-feed/1'               -- the component's
    lua/vut_merge/protocol.lua                   -- the only new logic:
                      fold a DOWN stream into a view, and a decision
                      into an envelope. NO neovim call in it, which is
                      why it is testable without neovim.

LAYOUT
    lua/vut_merge/protocol.lua   pure; the whole of what is new
    lua/vut_merge/init.lua       the neovim glue: buffers, keys, streams
    TEST/                        HWUT choices, written in Lua
============================================================================
