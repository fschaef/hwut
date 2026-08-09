"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       THE REPORT SERVICE -- 'hwut report': ONE test, packed whole.

DESCRIPTION
       Everything a conversation about one test needs, in one dump on
       stdout: the METADATA, the SOURCE of the test application, the
       accepted GOOD, the produced OUT -- and the CADENCE, when the
       store recorded it. Made for handing a test to another pair of
       eyes, human or AI, without them asking for file after file.

           hwut report TEST-APP [CHOICE]        the pack; when a cadence
                                                sidecar exists, each
                                                line of its stream is
                                                prefixed '<delta-t>:'
           hwut report TEST-APP [CHOICE] -r     the files VERBATIM
                                                ('--raw'): no cadence
                                                prefixes, raw sidecars
                                                and timing sections
                                                included
           hwut report TEST-APP [CHOICE] -c     pack the COVERAGE too
                                                ('--coverage') -- the
                                                flag is RESERVED: the
                                                pack says the gathering
                                                is owed (todo-22)

       TWO NAMING CONVENTIONS, both served (the store's key law,
       store.py '_key'): the classic corpus 'GOOD/app--choice.txt', and
       the store's 'GOOD/app--choice.<subject>' with '.raw'/'.times'
       sidecars. Whatever exists is packed; what does not is SAID in
       the metadata -- absence reported, never guessed (the house law).

       MACHINE-FREE: relative names and byte counts only -- no absolute
       paths, no dates -- so a pack can be compared, stored, or pasted
       without freezing one machine into it.

       Run from the test's directory (where GOOD/ and OUT/ live), like
       every hwut command. Rendering goes to STDOUT; exit 0 with a
       pack, 2 on an unusable request.
______________________________________________________________________________
"""
import io
import os
import sys
import json
import argparse

#  THE IMPORT CALL -- see merge.py: config.py (this directory) does the
#  walk-up; the face adopts its package (PEP 366). Dead under '-m'.
if __package__ in (None, ""):
    import config
    __package__ = config.PACKAGE


def _key_stem(application, choice):
    """
    RETURN: str, the record stem of one test/choice -- the store's key
            law (store.py '_key'): 'app--choice' with a choice, 'app'
            without.
    """
    return application if choice is None \
           else "%s--%s" % (application, choice)


def find_records(directory, application, choice):
    """
    RETURN: dict, section name -> relative path, for every record of
            this test/choice that EXISTS under 'directory' -- both
            naming conventions searched, sidecars included.
    """
    stem  = _key_stem(application, choice)
    found = {}

    def take(section, relative_path):
        """RETURN: None. Keeps the first hit of a section -- ONE section
        per file: a path already packed under another name (the classic
        '.txt' re-found as store-subject 'txt') is not packed twice."""
        if   section in found:                 return
        elif relative_path in found.values():  return
        elif os.path.isfile(os.path.join(directory, relative_path)):
            found[section] = relative_path

    #  The classic corpus: one file, stdout implied.
    take("good stdout",       os.path.join("GOOD", stem + ".txt"))
    take("out stdout",        os.path.join("OUT",  stem + ".txt"))
    #  The store convention: one file per subject, sidecars beside.
    for prefix, section in (("GOOD", "good"), ("OUT", "out")):
        base = os.path.join(directory, prefix)
        if not os.path.isdir(base): continue
        for name in sorted(os.listdir(base)):
            if not name.startswith(stem + "."): continue
            subject = name[len(stem) + 1:]
            if   subject.endswith(".times"):
                take("%s timing %s" % (section, subject[:-6]),
                     os.path.join(prefix, name))
            elif subject.endswith(".raw"):
                take("%s raw %s" % (section, subject[:-4]),
                     os.path.join(prefix, name))
            else:
                take("%s %s" % (section, subject),
                     os.path.join(prefix, name))
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
        line_list.append("  %-28s %6i bytes  (source)"
                         % (application,
                            os.path.getsize(source_path)))
    else:
        line_list.append("  %-28s MISSING       (source)" % application)
    for section in sorted(record_db):
        relative_path = record_db[section]
        line_list.append("  %-28s %6i bytes  (%s)"
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

    The pack goes to stdout ('hwut report x.py c > pack.txt' or straight
    into a clipboard); the pipe is the design, so a reader that leaves
    early is an ordinary ending.
    """
    try:
        return _main(argv)
    except BrokenPipeError:
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return 141


def _main(argv):
    """
    RETURN: int, the exit code -- 'main' without the pipe guard.
    """
    parser = argparse.ArgumentParser(
        prog="hwut report",
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
