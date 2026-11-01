#! /usr/bin/env python3
#
# @hwut {
#     title    = "hwut.support <language>: the support and its demonstration, written out and importable (E-217)"
#     caps     { timeout_sec = 1800 cpu_sec = 7200 memory_mb = 8192 file_size_mb = 512
#                child_process_max_n = 512 disk_mb = 8192 }   # each choice builds and runs a whole demonstration, twice
#     choices {
#         faces      { features = ["support-faces"] }
#         refused    { features = ["support-refused"] }
#         python     { features = ["support-written", "support-importable"] }
#         perl       { features = ["support-written", "support-importable"] }
#         c          { features = ["support-written", "support-importable"] }
#         cpp        { features = ["support-written", "support-importable"] }
#         java       { features = ["support-written", "support-importable"] }
#         rust       { features = ["support-written", "support-importable"] }
#         go         { features = ["support-written", "support-importable"] }
#         node       { features = ["support-written", "support-importable"] }
#         verilog    { features = ["support-written", "support-importable"] }
#         vhdl       { features = ["support-written", "support-importable"] }
#         bash       { features = ["support-written", "support-importable"] }
#         powershell { features = ["support-written", "support-importable"]
#                      caps { file_size_mb = 2097152 } }   # .NET maps a 2 TiB file (W^X), as the demonstration says
#         erlang     { features = ["support-written", "support-importable"] }
#         guile      { features = ["support-written", "support-importable"] }
#         haskell    { features = ["support-written", "support-importable"] }
#         prolog     { features = ["support-written", "support-importable"] }
#         fortran    { features = ["support-written", "support-importable"] }
#     }
# }
#
"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: 'hwut.support <language> <dir>' -- what it writes, what it says,
         and that what it says is enough.

    faces       'hwut.support' offers the languages of LANGUAGES.conf, each
                with a title and a demonstration; a word naming none is
                refused with the list.
    refused     a directory not empty, one word, three words, the retired
                'hwut.demo.python'.
    <language>  (1) the face writes '<dir>'; its words are shown with
                '<dir>' for the place. The written demonstration runs, its
                MAKE IT IMPORTABLE lines applied (most languages need none
                for it; node needs its 'npm install'). (2) Written again
                with its marked line pointing nowhere, every variable the
                MAKE IT IMPORTABLE lines set first unset, and only those lines
                applied, the demonstration runs again: the lines are all a
                test of one's own needs. 'nowhere' is a path in the test's
                own temporary directory, which is checked not to stand.
______________________________________________________________________________
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

import config                                               # noqa: F401
HWUT = config.HWUT_DIRECTORY
BIN  = os.path.join(HWUT, "bin")
sys.path.insert(0, os.path.dirname(HWUT))
from hwut.services.lib.support import core                  # noqa: E402

EXPORT_RE = re.compile(r"\bexport\s+([A-Za-z_][A-Za-z0-9_]*)=")
RESULT_RE = re.compile(r"^RESULTS: (\d+) ok, (\d+) fail")


def shown(text, place):
    """RETURN: str, 'text' with the path 'place' written as '<dir>'."""
    return text.replace(os.path.abspath(place), "<dir>").replace(place, "<dir>")


def results(test_dir, prologue=""):
    """
    RETURN: str, the RESULTS line of 'hwut --plain' in 'test_dir', its
            times cut off -- run by bash after 'prologue', with hwut's
            'bin/' first on PATH.
    """
    script = "%s\ncd '%s' && hwut --plain 2>&1" % (prologue, test_dir)
    env = dict(os.environ, PATH=BIN + os.pathsep + os.environ.get("PATH", ""))
    done = subprocess.run(["bash", "-c", script], capture_output=True,
                          text=True, env=env)
    for line in done.stdout.splitlines():
        m = RESULT_RE.match(line)
        if m: return "RESULTS: %s ok, %s fail" % m.groups()
    return "NO RESULTS -- %s" % (done.stdout + done.stderr).strip()[-400:]


def face(*word_list):
    """RETURN: CompletedProcess, 'hwut.support' run with 'word_list'."""
    return subprocess.run([os.path.join(BIN, "hwut.support")] + list(word_list),
                          capture_output=True, text=True)


def test_faces():
    db = core.language_db(HWUT)
    demo_set = set(n for n in os.listdir(os.path.join(HWUT, "support", "demo"))
                   if os.path.isdir(os.path.join(HWUT, "support", "demo", n,
                                                 "TEST")))
    print("languages:  %i" % len(db))
    print("titled:     all: %s" % all(entry["title"] for entry in db.values()))
    print("a demonstration each: %s" % (set(db) <= demo_set))
    done = face("cobol", "x")
    print("hwut.support cobol <dir> -> exit %i" % done.returncode)
    print("    %s" % done.stdout.splitlines()[0])
    print("    the list is the languages: %s"
          % (done.stdout.split("the languages: ")[-1].strip()
             == ", ".join(db)))


def test_refused():
    root = tempfile.mkdtemp(prefix="hwut_support_refused_")
    try:
        with open(os.path.join(root, "x"), "w") as fh: fh.write("x\n")
        for word_list in (["python", root], ["python"],
                          ["python", root, "three"]):
            done = face(*word_list)
            print("hwut.support %s -> exit %i"
                  % (shown(" ".join(word_list), root), done.returncode))
            for line in done.stdout.splitlines()[:1]:
                print("    %s" % shown(line, root))
        done = subprocess.run([os.path.join(BIN, "hwut.demo.python"),
                               os.path.join(root, "d")],
                              capture_output=True, text=True)
        print("hwut.demo.python <dir> -> exit %i" % done.returncode)
        for line in done.stdout.splitlines()[:1]:
            print("    %s" % shown(line, root))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_language(language):
    root = tempfile.mkdtemp(prefix="hwut_support_%s_" % language)
    try:
        place = os.path.join(root, "as-written")
        done  = face(language, place)
        print("-- hwut.support %s <dir>   (exit %i)" % (language,
                                                       done.returncode))
        for line in done.stdout.splitlines():
            print("   %s" % shown(line, place))
        if done.returncode != 0: return
        print("   <dir>: %s" % " ".join(sorted(os.listdir(place))))
        bare    = os.path.join(root, "bare")
        nowhere = os.path.join(root, "hwut-support-not-here")
        assert not os.path.exists(nowhere)
        test, entry = core.written(language, bare, replacement=nowhere)
        print("-- as written, the MAKE IT IMPORTABLE lines applied")
        print("   %s" % results(os.path.join(place, "TEST"), "\n".join(
              l.replace("<dir>", os.path.abspath(place)) for l in entry["use"])))
        #  PATH is kept: without it nothing runs; the fallback is then the
        #  only other way to the support, and it points nowhere.
        name_set = sorted(set(EXPORT_RE.findall("\n".join(entry["use"])))
                          - {"PATH"})
        prologue = "\n".join(["unset %s" % n for n in name_set]
                             + [l.replace("<dir>", os.path.abspath(bare))
                                for l in entry["use"]])
        print("-- the marked line pointing nowhere; unset: %s; then only the "
              "MAKE IT IMPORTABLE lines" % (" ".join(name_set) or "nothing"))
        print("   %s" % results(test, prologue))
        if language == "python":
            check = subprocess.run(
                ["bash", "-c", "%s\ncd / && python3 -c 'from hwut_runner "
                 "import HwutRunner; import hwut_hocon, hwut_fsm, "
                 "space_iterator, deterministic_random, "
                 "deterministic_timeline; print(\"the copy imports\")'"
                 % prologue], capture_output=True, text=True,
                env={k: v for k, v in os.environ.items()
                     if k != "PYTHONPATH"})
            print("   %s" % (check.stdout.strip() or check.stderr.strip()[-300:]))
    finally:
        shutil.rmtree(root, ignore_errors=True)


choice = sys.argv[1]
if   choice == "faces":   test_faces()
elif choice == "refused": test_refused()
else:                     test_language(choice)
print("<hwut-end>")
