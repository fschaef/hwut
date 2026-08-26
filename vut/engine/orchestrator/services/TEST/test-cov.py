#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.cov' FACE -- convert, formats, and the door.

CHOICES: convert, formats, refused, help;

convert    a text record becomes binary and comes back byte-identical;
           the form is told by the file's first bytes, or stated; a
           record that reads in neither spelling is a FAULT, not an
           empty output.
formats    the table of tools and candidates is GENERATED from the
           registry -- this GOOD is the one place the table is written
           down (coverage RATIONALE D-13).
refused    an unknown verb, an unknown option, a form that is not one,
           two files: refused by name with the usage line.
help       the text, and the empty command line.
______________________________________________________________________________
"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))

import config                                                    # noqa F401
from   config import HwutRunner                                  # noqa F401,E402

from   vut.engine.orchestrator.services.cov import main          # noqa E402

RECORD_TEXT = ("##VUT-COVERAGE 2\n##run:      0.1,3\n##language: c\n"
               "##tool:     gcov\n##format:   gcov-annotated\n"
               "##counts:   no\nSF:parser/core.c\nEX:3+12,5+5\nCV:3+12\n"
               "BR:5*1/2\nSF:parser/table.c\nEX:\nCV:\n")


def call(argument_list, directory):
    """
    RETURN: bytes, what the face wrote as the record. Shows the command
            line, the lines the face writes, and the exit status; a
            path under the temporary directory is shown as '<dir>'.
    """
    shown = [a.replace(directory, "<dir>") for a in argument_list]
    print("$ hwut.cov %s" % " ".join(shown))
    line_list, chunk_list = [], []
    status = main(argument_list, line_list.append, chunk_list.append)
    for line in line_list:
        for piece in str(line).replace(directory or "\0", "<dir>") \
                              .split("\n"):
            print("    %s" % piece if piece else "")
    data = b"".join(chunk_list)
    if data:
        print("    [%i bytes written to stdout]" % len(data))
    print("    [status %d]" % status)
    return data


def check(pair_list):
    """RETURN: True, every claim held; False, at least one did not."""
    ok = True
    for holds, claim in pair_list:
        print("  %s: %s" % ("OK  " if holds else "FAIL", claim))
        if not holds: ok = False
    return ok


def verdict(ok, sentence):
    """RETURN: None. The one closing line HWUT greps for."""
    print("%s: %s" % ("SUCCESS" if ok else "FAILURE", sentence))


def test_convert():
    """Text to binary and back."""
    directory = tempfile.mkdtemp(prefix="vut_cov_")
    text_path = os.path.join(directory, "r.cover.txt")
    bin_path  = os.path.join(directory, "r.cover")
    with open(text_path, "w", encoding="utf-8") as fh: fh.write(RECORD_TEXT)

    binary = call(["convert", text_path], directory)
    with open(bin_path, "wb") as fh: fh.write(binary)
    back   = call(["convert", bin_path], directory)
    print("    the text that came back {")
    for line in back.decode().splitlines(): print("      %s" % line)
    print("    }")
    stated = call(["convert", "--from", "text", "--to", "text", text_path],
                  directory)
    with open(os.path.join(directory, "x"), "wb") as fh: fh.write(b"???")
    call(["convert", os.path.join(directory, "x")], directory)
    call(["convert", os.path.join(directory, "missing")], directory)

    ok = check([
        (binary[:1] == b"\x78", "the binary form is a zlib stream"),
        (back.decode() == RECORD_TEXT,
         "binary -> text is byte-identical to the text that went in"),
        (stated.decode() == RECORD_TEXT,
         "text -> text, stated, is the identity"),
    ])
    shutil.rmtree(directory)
    verdict(ok, "one record, two spellings; the face converts on demand.")


def test_formats():
    """The generated table."""
    call(["formats"], "")
    verdict(True, "the table has one author, the registry, and this is "
                  "its printout.")


def test_refused():
    """Refused by name."""
    directory = tempfile.mkdtemp(prefix="vut_cov_")
    p = os.path.join(directory, "a")
    with open(p, "w") as fh: fh.write(RECORD_TEXT)
    for argument_list in (["explain", p],
                          ["convert", "--to", "yaml", p],
                          ["convert", "--bogus", p],
                          ["convert", p, p],
                          ["convert"],
                          ["formats", "extra"]):
        call(argument_list, directory)
    shutil.rmtree(directory)
    verdict(True, "the door refuses by name, with the usage line.")


def test_help():
    """The help text and the empty line."""
    call(["--help"], "")
    call([], "")
    verdict(True, "help on request; an empty command line is EMPTY.")


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "hwut.cov: convert, formats, and the door",
        choice_map = {
            "convert": test_convert,
            "formats": test_formats,
            "refused": test_refused,
            "help":    test_help,
        },
        happy      = "SUCCESS.*",
    ).run()
