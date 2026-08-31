"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: A THROWAWAY EXECUTABLE SCRIPT, for tests that need a real
         application to run rather than a simulated one.

    do()        writes the script and makes it executable; returns its
                path.
    CRunScript  the same, as a context manager: the script is deleted
                when the block ends, whatever ended it.
    tree_boundary()
                writes the 'hwut-root.conf' that ENDS a fixture's
                tree, so the climb has somewhere to stop.

A test that supervises processes, times them, or reads their streams
needs something REAL on the other side. Writing that by hand in every
suite produces a different half-correct fixture each time -- one
forgets the chmod, one leaves the file behind, one prints the script
in a form the GOOD cannot mask.

Prefer 'CRunScript'. 'do()' stands for the caller who owns the path
already and disposes of it themselves.
______________________________________________________________________________
"""
import os
import stat
import tempfile
from   pathlib import Path
from   typing  import ContextManager, Optional


def do(file_name:       Optional[str],
       shebang:         str,
       script_txt_list: list[str],
       display_f:       bool = True) -> Optional[str]:
    """RETURN: str,  the path of the generated, executable script
              None, if it could not be written

    'file_name'       where to write; None asks for a temporary file
    'shebang'         the interpreter, with or without the leading '#!'
    'script_txt_list' the lines of the script, without line ends
    'display_f'       print the script under a 'SCRIPT:' banner, so a
                      GOOD shows the stimulus that produced the
                      reaction

    A temporary file is created with 'delete=False': the handle closes
    before a supervised process opens the path, so the file must
    outlive it.
    """
    script_path = None

    content = shebang if shebang.startswith("#!") else f"#!{shebang}"
    content += "\n" + "\n".join(script_txt_list) + "\n"

    try:
        if file_name is None:
            with tempfile.NamedTemporaryFile(prefix="test_app_",
                                             delete=False) as tmp:
                script_path = Path(tmp.name)
        else:
            script_path = Path(file_name)

        script_path.write_text(content)
        script_path.chmod(script_path.stat().st_mode | stat.S_IEXEC)

    except Exception:
        if script_path and script_path.exists():
            try:
                script_path.unlink()
            except OSError:  # noqa: S110 -- cleanup after a failure
                #  THE WRITE ALREADY FAILED; a failure to clean up
                #  after it must not replace the first failure with a
                #  second. NARROWED to OSError: a bug here, or an
                #  interrupt, is not a thing to swallow.
                pass
        return None

    if display_f:
        if not file_name: file_name = "<temporary file>"
        print(f"SCRIPT: '{file_name}' " + "{")
        for line in content.splitlines():
            print(f"    {line}")
        print("}")

    return str(script_path)


def tree_boundary(directory, content="hwut {\n}\n"):
    """
    RETURN: str, the path written.

    THE BOUNDARY OF A FIXTURE'S TREE. Every face ASCENDS from where it
    is called, collecting each 'hwut.conf' it passes, until it meets a
    'hwut-root.conf'; a tree with none above it is REFUSED. So a
    fixture that builds a tree states its own end, and an empty block
    is a complete statement -- it says only 'the tree ends here'.

    'content' takes global parameters where a fixture wants them; they
    apply to every test of that tree unless a nearer conf or a source
    header says otherwise.
    """
    target = Path(directory) / "hwut-root.conf"
    target.write_text(content, encoding="utf-8")
    return str(target)


class CRunScript(ContextManager[str]):
    """A throwaway executable script for the duration of a 'with' block.

    The script is deleted when the block ends, whatever ended it -- so
    a suite that fails mid-way leaves no executable behind to be
    explored as a test application by a later walk.
    """
    def __init__(self, file_name, shebang, script_txt_list,
                 display_f=True):
        """RETURN: CRunScript, not yet written -- 'do()' runs at entry."""
        self.params = {'file_name':       file_name,
                       'shebang':         shebang,
                       'script_txt_list': script_txt_list,
                       'display_f':       display_f}
        self.path = None

    def __enter__(self) -> str:
        """RETURN: str, path of the generated, executable script.

        Raises RuntimeError where the script could not be written.
        """
        result = do(**self.params)
        if result is None:
            raise RuntimeError("script_runner.do() wrote no script.")

        self.path = result
        return self.path

    def __exit__(self, exc_type, exc_val, exc_tb):
        """RETURN: None; the generated script is deleted, if it exists.
        """
        if self.path and os.path.exists(self.path):
            try:
                os.unlink(self.path)
            except OSError:  # noqa: S110 -- cleanup on the way out
                #  A TEMPORARY SCRIPT THAT WILL NOT DELETE is not a
                #  reason to raise out of '__exit__' and mask whatever
                #  the block was already raising. NARROWED to OSError.
                pass

