"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: 'hwut.cov.conv.to_pdf' -- the document of 'hwut.cov.conv.to_tex'
         compiled to PDF (coverage RATIONALE D-44).

    hwut.cov.conv.to_pdf [DIRECTORY] [-o FILE] [--style FILE]
                                DIRECTORY is the '-o' of 'hwut.cov.run'
                                ('./hwut.coverage' where none is
                                named); the PDF goes to FILE,
                                'DIRECTORY/coverage.pdf' where none is
                                named. '--style' as 'to_tex'.
    hwut.cov.conv.to_pdf --help
                                this text

THE ENGINE IS THE MACHINE'S: 'latexmk -pdf' where it stands, else
'pdflatex' twice; where neither stands the face says so by name and
writes nothing. The build runs in a directory of its own beside the
target; the '.tex', the package and the engine's log stay there under
'<target>.build/' so a failing build can be read. A reader's style
('--style FILE') is copied in beside the document.

The exit status (E-1): OK with the PDF written, FAULT where the
directory cannot be read, no engine stands, or the engine failed (its
last lines are shown), REFUSED where the command line cannot be.
______________________________________________________________________________
"""
import os
import shutil
import subprocess
import sys

from   vut.services.lib.cov.conv._face  import help_of, many_files_main
from   vut.services.lib.cov.conv.to_tex import place_style, tex_of

NAME  = "hwut.cov.conv.to_pdf"
USAGE = "usage: %s [DIRECTORY] [-o FILE] [--style FILE] | --help" % NAME
HELP  = help_of(__doc__)


def engine_argv(tex_name):
    """
    RETURN: list of list of str, the calls that make the PDF, in order.
            None, where no engine stands on this machine.
    """
    if shutil.which("latexmk"):
        return [["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error",
                 tex_name]]
    if shutil.which("pdflatex"):
        call = ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", tex_name]
        return [call, call]
    return None


def _build(write):
    """RETURN: function, the builder 'many_files_main' calls, closing
    over 'write' for the engine's tail."""
    def build(root, summary_list, found, target):
        """RETURN: str, the closing line; None where the build failed
        and 'write' said why."""
        argv_list = engine_argv("coverage.tex")
        if argv_list is None:
            write("FAULT: no TeX engine stands on this machine -- neither "
                  "'latexmk' nor 'pdflatex'; 'hwut.cov.conv.to_tex' writes "
                  "the document for one elsewhere")
            return None
        style = found["--style"]
        build_dir = target + ".build"
        os.makedirs(build_dir, exist_ok=True)
        place_style(build_dir)
        style_name = None
        if style is not None:
            style_name = os.path.basename(style)
            if style_name.endswith(".sty"): style_name = style_name[:-4]
            if os.path.isfile(style):
                shutil.copyfile(style, os.path.join(build_dir, style_name + ".sty"))
        with open(os.path.join(build_dir, "coverage.tex"), "w",
                  encoding="utf-8") as handle:
            handle.write(tex_of(root, summary_list, style_name))
        for argv in argv_list:
            done = subprocess.run(argv, cwd=build_dir, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, text=True,
                                  errors="replace")
            if done.returncode != 0:
                write("FAULT: '%s' failed in '%s':" % (" ".join(argv), build_dir))
                for line in done.stdout.splitlines()[-12:]:
                    write("    | %s" % line)
                return None
        shutil.copyfile(os.path.join(build_dir, "coverage.pdf"), target)
        return "COVERAGE PDF: %s -- %i source file(s)" % (target, len(summary_list))
    return build


def main(argv=None, write=None):
    """RETURN: E_ExitCode (E-1), as '_face.many_files_main'."""
    if write is None: write = print
    return many_files_main(NAME, USAGE, HELP, _build(write), "coverage.pdf",
                           argv, write, option_db={"--style": "FILE"})


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from vut.services._exit import guarded
    sys.exit(guarded(NAME, main, sys.argv[1:]))
