"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.cov' COMMAND LINE -- coverage, as one executable with
         verbs (coverage RATIONALE D-13, D-20).

    hwut.cov [<wish>] [--variant=<a>,<b>] [<hwut.run options>]
                                THE RUN, for coverage: 'hwut.run
                                --coverage' with the same wish and
                                options; every test is built and run
                                for coverage, every completed run
                                harvested (coverage D-19, D-21). The
                                tool is the configuration's, selected
                                by '--variant' (E-9); elected for the
                                language else
    hwut.cov gather [--directory=<path>] [--out=<file>]
                                FOLD every record below the root into
                                ONE index whose keys are (directory,
                                run id), and write the DELIVERY BUNDLE
                                -- the gather's group-of-groups table
                                and index, plus a versioned snapshot of
                                each directory's register and group
                                table (coverage D-25). Writes into no
                                directory's 'GOOD/'.
    hwut.cov stale BUNDLE [--directory=<path>]
                                which directories of that bundle have
                                MOVED since it was taken
    hwut.cov convert [--from <form>] [--to <form>] FILE
                                the record in another spelling, on
                                stdout. Forms: 'binary' (what the store
                                holds, '.cover'), 'text' (the
                                presentation, FORMAT.txt). '--from'
                                defaults by the file's first bytes,
                                '--to' to the other form.
    hwut.cov formats            the table of tools, formats and
                                aliases, GENERATED from the registry
                                -- the one author of that table
    hwut.cov --help             this text

A first word that is a VERB ('gather', 'stale', 'convert', 'formats')
is that verb; anything else is the wish of a run. Faults set the exit
status (E-1); a record that cannot be read is refused by name and
nothing is written.
______________________________________________________________________________
"""
import os
import sys

from   vut.engine.coverage.record   import (parse_record, format_record,
                                            RecordFault)
from   vut.engine.coverage.binary   import pack_record, unpack_record, MAGIC
from   vut.engine.coverage.reader   import registered_tuple, framework_of
from   vut.engine.coverage.registry import DEFAULT_TOOL_DB
from   ._exit                       import E_ExitCode

USAGE = "usage: hwut.cov [<wish>] | convert [--from binary|text] " \
        "[--to binary|text] FILE | formats | --help"
VERB_TUPLE = ("gather", "stale", "convert", "formats")
HELP  = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip()

FORM_TUPLE = ("binary", "text")


def form_of_bytes(data):
    """
    RETURN: 'binary', the bytes begin as a zlib stream (a packed record
            begins with MAGIC, but that lies inside the compression);
            'text', they begin with the text spelling's version line.
            None, neither.
    """
    if data[:1] == b"\x78":                return "binary"
    if data.startswith(b"##VUT-COVERAGE"):  return "text"
    return None


def convert(data, source_form, target_form):
    """
    RETURN: bytes, the record in 'target_form'.

    Raises RecordFault where the bytes do not spell a record in
    'source_form'.
    """
    if source_form == "binary": record = unpack_record(data)
    else:                       record = parse_record(data.decode("utf-8"))
    if target_form == "binary": return pack_record(record)
    return format_record(record).encode("utf-8")


def formats_text():
    """
    RETURN: str, two tables read from the registry and written nowhere
            else: every tool this build READS with its format and, for
            an alias, the reader it reads through; then every LANGUAGE
            with its candidate tools in election order, a '*' marking
            the ones this build reads.
    """
    readable  = set(registered_tuple())
    line_list = ["TOOLS READ BY THIS BUILD",
                 "  %-18s %-24s %s" % ("tool", "format", "reads through")]
    for tool in sorted(readable):
        reader  = framework_of(tool)
        through = getattr(reader, "through", None)
        line_list.append("  %-18s %-24s %s"
                         % (tool, reader.source_format,
                            through.name if through is not None else "-"))
    line_list += ["", "CANDIDATES PER LANGUAGE, IN ELECTION ORDER "
                      "('*' = read by this build)"]
    for language in sorted(DEFAULT_TOOL_DB):
        words = ["%s%s" % (t, "*" if t in readable else "")
                 for t in DEFAULT_TOOL_DB[language]]
        line_list.append("  %-14s %s" % (language, "  ".join(words)))
    return "\n".join(line_list)


def _option_db(word_list, known_tuple):
    """
    RETURN: [0] dict, '--name=value' options given, by name
            [1] list of str, the words that are no option
            [2] str, the first unknown option; None where every one is
                known
    """
    option_db, rest, unknown = {}, [], None
    for word in word_list:
        if not word.startswith("--"): rest.append(word); continue
        name, _, value = word[2:].partition("=")
        if name not in known_tuple: unknown = unknown or word; continue
        option_db[name] = value
    return option_db, rest, unknown


def _gather(word_list, write):
    """
    RETURN: E_ExitCode: OK with the bundle written and its shape said,
            REFUSED on a bad option or a root that is no directory,
            EMPTY where no record stands below the root.
    """
    from vut.engine.coverage.gather import (gathered_index, snapshot_db_of,
                                            bundle_of, write_bundle,
                                            BUNDLE_FILE)
    option_db, rest, unknown = _option_db(word_list,
                                          ("directory", "out"))
    if unknown or rest:
        write("REFUSED: 'gather' takes --directory= and --out=, not "
              "'%s'" % (unknown or rest[0])); write(USAGE)
        return E_ExitCode.REFUSED
    root = os.path.abspath(option_db.get("directory") or ".")
    if not os.path.isdir(root):
        write("REFUSED: the directory '%s' does not exist" % root)
        return E_ExitCode.REFUSED

    index, directory_tuple = gathered_index(root)
    if not directory_tuple:
        write("no coverage record stands below '%s'" % root)
        return E_ExitCode.EMPTY

    snapshot_db = snapshot_db_of(root, directory_tuple)
    bundle      = bundle_of(root, index, directory_tuple, snapshot_db)
    path        = option_db.get("out") or os.path.join(root, BUNDLE_FILE)
    write_bundle(bundle, path)

    write("gathered %i directory(ies), %i file(s), %i group(s)"
          % (len(directory_tuple), len(bundle["index"]),
             len(bundle["group_of_groups"])))
    for directory in directory_tuple:
        entry = bundle["snapshot"].get(directory)
        write("  %-40s register generation %s, groups %s"
              % (directory,
                 entry["register_generation"] if entry else "<unread>",
                 entry["groups_generation"] if entry else "<unread>"))
    write("bundle: %s" % path)
    return E_ExitCode.OK


def _stale(word_list, write):
    """
    RETURN: E_ExitCode: OK where nothing moved, FAULT where a directory
            has moved or can no longer be read, REFUSED on a bad
            command line or an unreadable bundle.
    """
    from vut.engine.coverage.gather import (read_bundle, stale_tuple,
                                            GatherFault)
    option_db, rest, unknown = _option_db(word_list, ("directory",))
    if unknown or len(rest) != 1:
        write("REFUSED: 'stale' takes one BUNDLE and --directory=")
        write(USAGE)
        return E_ExitCode.REFUSED
    root = os.path.abspath(option_db.get("directory") or ".")
    try:               bundle = read_bundle(rest[0])
    except GatherFault as fault:
        write("REFUSED: %s" % fault)
        return E_ExitCode.REFUSED

    moved_list = list(stale_tuple(bundle, root))
    if not moved_list:
        write("every directory of the bundle stands as it was taken")
        return E_ExitCode.OK
    for directory, what, how in moved_list:
        write("  %-40s %s %s" % (directory, what, how))
    write("the ids still decode -- an id is issued once (bookkeeper "
          "B-2) -- but the tree has moved; gather again for a current "
          "picture.")
    return E_ExitCode.FAULT


def main(argv=None, write=None, write_bytes=None, demand=None):
    """
    RETURN: E_ExitCode (E-1): OK where the verb did its work, FAULT
            where a record could not be read, REFUSED where the command
            line itself cannot be read.

    'write' takes one line of text; 'write_bytes' takes the converted
    record whole -- stdout's buffer where none is given, so a test may
    capture the face without a process. 'demand' is the CoverageConfig
    of a run, where a face states it (the test seam; todo-13).
    """
    if write is None:       write = print
    if write_bytes is None: write_bytes = sys.stdout.buffer.write
    if argv is None:        argv = sys.argv[1:]

    if "--help" in argv:
        write(HELP)
        return E_ExitCode.OK

    if not argv or argv[0] not in VERB_TUPLE:
        #  THE RUN: the same door as 'hwut.run', the demand added.
        from .run import main as run_main
        return run_main(["--coverage"] + list(argv), write, demand=demand)

    verb, rest = argv[0], argv[1:]
    if verb == "gather":
        return _gather(rest, write)

    if verb == "stale":
        return _stale(rest, write)

    if verb == "formats":
        if rest:
            write("REFUSED: 'formats' takes no argument"); write(USAGE)
            return E_ExitCode.REFUSED
        write(formats_text())
        return E_ExitCode.OK

    source_form = target_form = None
    file_list   = []
    i = 0
    while i < len(rest):
        word = rest[i]
        if word in ("--from", "--to"):
            if i + 1 >= len(rest) or rest[i + 1] not in FORM_TUPLE:
                write("REFUSED: '%s' takes one of %s"
                      % (word, ", ".join(FORM_TUPLE))); write(USAGE)
                return E_ExitCode.REFUSED
            if word == "--from": source_form = rest[i + 1]
            else:                target_form = rest[i + 1]
            i += 2
        elif word.startswith("-"):
            write("REFUSED: unknown option '%s'" % word); write(USAGE)
            return E_ExitCode.REFUSED
        else:
            file_list.append(word); i += 1
    if len(file_list) != 1:
        write("REFUSED: 'convert' takes exactly one FILE"); write(USAGE)
        return E_ExitCode.REFUSED

    try:
        with open(file_list[0], "rb") as handle: data = handle.read()
    except OSError as fault:
        write("FAULT: %s" % fault)
        return E_ExitCode.FAULT
    if source_form is None:
        source_form = form_of_bytes(data)
        if source_form is None:
            write("FAULT: '%s' begins as neither spelling; say --from"
                  % file_list[0])
            return E_ExitCode.FAULT
    if target_form is None:
        target_form = "text" if source_form == "binary" else "binary"
    try:
        write_bytes(convert(data, source_form, target_form))
    except RecordFault as fault:
        write("FAULT: %s" % fault)
        return E_ExitCode.FAULT
    return E_ExitCode.OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
