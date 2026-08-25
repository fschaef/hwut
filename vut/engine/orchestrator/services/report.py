"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       THE REPORT SERVICE -- 'hwut.report': ONE test, packed whole.

DESCRIPTION
       Everything a conversation about one test needs, in one dump on
       stdout: the METADATA, the SOURCE of the test application, the
       accepted GOOD, the produced OUT -- and the CADENCE, when the
       store recorded it. Made for handing a test to another pair of
       eyes, human or AI, without them asking for file after file.

           hwut.report TEST-APP [CHOICE]        the pack; when a cadence
                                                sidecar exists, each
                                                line of its stream is
                                                prefixed '<delta-t>:'
           hwut.report TEST-APP [CHOICE] -r     the files VERBATIM
                                                ('--raw'): no cadence
                                                prefixes, raw sidecars
                                                and timing sections
                                                included
           hwut.report TEST-APP [CHOICE] -c     pack the COVERAGE too
                                                ('--coverage') -- the
                                                flag is RESERVED: the
                                                pack says the gathering
                                                is owed (todo-22)

       THE BOOKKEEPER OWNS THE NAMING. This face resolves NOTHING by
       hand: 'nominal_path', 'candidate_path', 'raw_path' and
       'timing_path' answer where every record of a key lives, and the
       key is (test, choice, subject) with 'test' the source file's
       STEM -- what RECORDING uses ('operations/session.py':
       configuration.stem). A second spelling of that law here would
       be a second law; there is one.

       Whatever exists is packed; what does not is SAID in the
       metadata -- absence reported, never guessed (the house law).

       MACHINE-FREE: relative names and byte counts only -- no absolute
       paths, no dates -- so a pack can be compared, stored, or pasted
       without freezing one machine into it.

       Run from the test's directory, like every hwut command. Rendering goes to STDOUT; exit 0 with a
       pack, 2 on an unusable request.
______________________________________________________________________________
"""
import io
import os
import sys
import json
import argparse
from pathlib import Path


#  THE IMPORT CALL -- see merge.py: __config.py (this directory) does the
#  walk-up; the face adopts its package (PEP 366). Dead under '-m'.
if __package__ in (None, ""):
    import _config
    __package__ = _config.PACKAGE
from ._exit import E_ExitCode  # delayed past _config adoption


def bookkeeper_of(directory):
    """
    RETURN: Bookkeeper, the one that owns naming in that directory.

    Imported here, not at module scope: the face runs by path as well
    as by module, and the import must follow the '_config' adoption.
    """
    from ...bookkeeper.bookkeeper import Bookkeeper
    return Bookkeeper(directory)


def subject_tuple_of(bookkeeper, test, choice):
    """
    RETURN: tuple, the subjects recorded for that key, sorted -- the
            names under the candidate's stem with the sidecars
            ('.raw', '.times', '.when') left out; empty where the run
            recorded nothing.
    """
    probe     = bookkeeper.candidate_path(test, choice, "s")
    base      = probe.parent
    stem      = probe.name[:-1]
    if not base.is_dir(): return ()
    name_list = []
    for path in base.iterdir():
        name = path.name
        if not name.startswith(stem):                          continue
        if name.endswith((".raw", ".times", ".when")):          continue
        name_list.append(name[len(stem):])
    return tuple(sorted(name_list))


def find_records(directory, application, choice):
    """
    RETURN: dict, section name -> path RELATIVE to 'directory', for
            every record of this test/choice that EXISTS -- nominal,
            candidate, and the '.raw'/'.times' sidecars beside it.

    Every path comes from the BOOKKEEPER; this function spells no key
    itself. 'application' is the source file as the user typed it
    ('demo.py'); the key uses its STEM, which is what recording used.
    """
    bookkeeper = bookkeeper_of(directory)
    test       = Path(application).stem
    root       = Path(directory)
    found      = {}

    def take(section, path):
        """RETURN: None. Keeps the first hit of a section, and packs no
        path twice under two names."""
        if section in found:                    return
        if not path.is_file():                  return
        try:    relative = str(path.relative_to(root))
        except ValueError:
            relative = str(path)
        if relative in found.values():          return
        found[section] = relative

    for subject in subject_tuple_of(bookkeeper, test, choice):
        take("good %s" % subject,
             bookkeeper.nominal_path(test, choice, subject))
        take("out %s" % subject,
             bookkeeper.candidate_path(test, choice, subject))
        take("out raw %s" % subject,
             bookkeeper.raw_path(test, choice, subject))
        take("out timing %s" % subject,
             bookkeeper.timing_path(test, choice, subject))

    #  A nominal may stand where no candidate does -- an accepted test
    #  that has not been run here. Ask for the usual subjects too.
    for subject in ("stdout",):
        take("good %s" % subject,
             bookkeeper.nominal_path(test, choice, subject))
    return found


def annotate(text, delta_list):
    """
    RETURN: str, 'text' with each line prefixed '<delta-t>:' from
            'delta_list' -- the cadence written INTO the stream. Lines
            beyond the recorded deltas carry '-:' (said, not guessed).
    """
    line_list = text.splitlines()
    out_list  = []
    for i, line in enumerate(line_list):
        delta = ("%.6f" % delta_list[i]) if i < len(delta_list) else "-"
        out_list.append("%s:%s" % (delta, line))
    return "\n".join(out_list) + ("\n" if text.endswith("\n") else "")


def load_timing(path):
    """
    RETURN: list, the delta list of a '.times' sidecar (store.py
            'write_timing' wrote it); [] when unreadable.
    """
    try:
        with io.open(path, "r", encoding="utf-8") as file_handle:
            return list(json.load(file_handle).get("delta_list", []))
    except (OSError, ValueError):
        return []


def build_pack(directory, application, choice, raw_f,
               coverage_f=False):
    """
    RETURN: str, the whole pack: metadata first, then one delimited
            section per file -- source, GOOD, OUT (cadence-prefixed
            when a '.times' sidecar pairs with a stream and '-raw' was
            not asked), raw and timing sections verbatim under '-raw'.
    """
    record_db   = find_records(directory, application, choice)
    source_path = os.path.join(directory, application)

    def read(relative_path):
        """RETURN: str, the file's text, replacement-decoded."""
        with io.open(os.path.join(directory, relative_path), "r",
                     encoding="utf-8", errors="replace") as file_handle:
            return file_handle.read()

    #  -- metadata ------------------------------------------------------
    line_list = ["==[ HWUT TEST REPORT ]%s" % ("=" * 56),
                 "test:    %s" % application,
                 "choice:  %s" % (choice if choice is not None else "<none>")]
    good_key = next((k for k in record_db if k.startswith("good ")
                     and " raw " not in k and " timing " not in k), None)
    out_key  = next((k for k in record_db if k.startswith("out ")
                     and " raw " not in k and " timing " not in k), None)
    if good_key and out_key:
        verdict_hint = "OUT == GOOD (byte-identical)" \
                       if read(record_db[good_key]) \
                          == read(record_db[out_key]) else "OUT differs from GOOD"
    elif out_key:  verdict_hint = "no GOOD found -- nothing accepted yet"
    elif good_key: verdict_hint = "no OUT found -- test not run here"
    else:          verdict_hint = "neither OUT nor GOOD found"
    line_list.append("hint:    %s" % verdict_hint)
    line_list.append("files:")
    if os.path.isfile(source_path):
        line_list.append("  %-40s %6i bytes  (source)"
                         % (application,
                            os.path.getsize(source_path)))
    else:
        line_list.append("  %-40s MISSING       (source)" % application)
    for section in sorted(record_db):
        relative_path = record_db[section]
        line_list.append("  %-40s %6i bytes  (%s)"
                         % (relative_path,
                            os.path.getsize(os.path.join(directory,
                                                         relative_path)),
                            section))
    timing_db = {k: record_db[k] for k in record_db if " timing " in k}
    line_list.append("coverage: %s"
                     % ("requested -- not gathered yet (todo-22)"
                        if coverage_f else "not requested"))
    line_list.append("cadence: %s"
                     % ("as '<delta-t>:<line>' prefixes"
                        if timing_db and not raw_f else
                        "sections verbatim" if timing_db else
                        "none recorded"))

    #  -- sections ------------------------------------------------------
    def section(title, text):
        """RETURN: None. Appends one delimited section."""
        line_list.append("")
        line_list.append("==[ %s ]%s" % (title,
                                         "=" * max(1, 74 - len(title))))
        line_list.append(text.rstrip("\n"))

    if coverage_f:
        #  ASKED FOR, NOT YET GATHERED. The pack says so rather than
        #  omitting the section silently -- the house law: absence is
        #  reported, never guessed. (Gathering it is owed; see
        #  DISCUSSIONS todo-22.)
        section("COVERAGE",
                "not gathered yet -- '-c' is accepted and reserved;\n"
                "the gathering is owed (DISCUSSIONS todo-22).")

    if os.path.isfile(source_path):
        section("SOURCE: %s" % application, read(application))

    for key in sorted(record_db):
        relative_path = record_db[key]
        if " timing " in key:
            if raw_f: section("TIMING (verbatim): %s" % relative_path,
                              read(relative_path))
            continue
        if " raw " in key and not raw_f:
            continue                    # raw rides only under '-raw'
        text = read(relative_path)
        #  The cadence belongs to the RAW stream (store.py: one delta
        #  per raw line); annotate the stream its sidecar names.
        if not raw_f:
            base_key    = key.replace(" raw ", " ")
            timing_key  = ("%s timing %s"
                           % tuple(base_key.split(" ", 1))
                           if " " in base_key else None)
            delta_list  = load_timing(os.path.join(
                              directory, timing_db[timing_key])) \
                          if timing_key in timing_db else []
            if delta_list:
                text = annotate(text, delta_list)
        section("%s: %s" % (key.upper(), relative_path), text)

    return "\n".join(line_list) + "\n"


def main(argv=None):
    """
    RETURN: int, the exit code -- 0 a pack was written; 141 the reader
            left early; 2 unusable request.

    The pack goes to stdout ('hwut.report x.py c > pack.txt' or straight
    into a clipboard); the pipe is the design, so a reader that leaves
    early is an ordinary ending.
    """
    try:
        return _main(argv)
    except BrokenPipeError:
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return E_ExitCode.SIGPIPE


def _main(argv):
    """
    RETURN: int, the exit code -- 'main' without the pipe guard.
    """
    parser = argparse.ArgumentParser(
        prog="hwut.report",
        description="Pack ONE test whole -- metadata, source, GOOD, OUT "
                    "and cadence -- for handing to another pair of "
                    "eyes, human or AI.")
    parser.add_argument("application",
                        help="the test application file, e.g. "
                             "test-merge.py")
    parser.add_argument("choice", nargs="?", default=None,
                        help="the choice; absent for a test without "
                             "choices")
    parser.add_argument("-r", "--raw", action="store_true",
                        help="files verbatim: no cadence prefixes, raw "
                             "sidecars and timing sections included")
    parser.add_argument("-c", "--coverage", action="store_true",
                        help="pack the COVERAGE of this test too (not "
                             "yet gathered -- the pack says so)")
    arguments = parser.parse_args(argv)

    application = os.path.basename(arguments.application)
    directory   = os.path.dirname(os.path.abspath(
                                  arguments.application))
    sys.stdout.write(build_pack(directory, application,
                                arguments.choice, arguments.raw,
                                arguments.coverage))
    return E_ExitCode.OK


if __name__ == "__main__":
    sys.exit(main())
