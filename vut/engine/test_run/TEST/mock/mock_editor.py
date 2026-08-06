"""A MOCK EDITOR -- the smallest thing that behaves like '$EDITOR'.

    python3 mock_editor.py append PATH     appends one line, then exits 0
    python3 mock_editor.py noop   PATH     changes nothing, exits 0
    python3 mock_editor.py fail   PATH     exits 3, touching nothing

'append' is a REAL edit, so a merge round genuinely progresses; 'noop'
is the undecided author, whom the TUI must re-prompt LOCALLY (the hub's
no-progress guard is for broken drivers, not for hesitation); 'fail' is
an editor that could not run at all.
"""
import sys

mode, path = sys.argv[1], sys.argv[2]

if   mode == "append":
    with open(path, "a") as file_handle:
        file_handle.write("appended by the mock editor\n")
elif mode == "noop":
    pass
elif mode == "fail":
    sys.exit(3)
