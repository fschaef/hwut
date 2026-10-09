"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: 'hwut.cov.conv.to_humans' -- a coverage file in its TEXT
         spelling, on stdout (coverage RATIONALE D-20, D-43).

    hwut.cov.conv.to_humans [--from <form>] [--to <form>] FILE
                                the record in another spelling. Forms:
                                'binary' (what the store and the output
                                directory hold, '.cover'), 'text' (the
                                presentation, 'database/FORMAT.txt').
                                '--from' defaults by the file's first
                                bytes, '--to' to the OTHER form -- so
                                the bare call turns a '.cover' into
                                text, and '--to binary' turns the text
                                back. A per-case record (version 4) and
                                a file of an output directory (version
                                3) are each converted as what they are.
    hwut.cov.conv.to_humans --help
                                this text

A record that cannot be read is refused by name and nothing is
written; the exit status says so (E-1).
______________________________________________________________________________
"""
import sys

from   vut.engine.coverage.api   import (parse_record, format_record,
                                         RecordFault)
from   vut.engine.coverage.api   import pack_record, unpack_record
from   vut.engine.coverage.api   import (binary_version, format_gathered,
                                         pack_gathered, parse_gathered,
                                         unpack_gathered)
from   vut.services._exit        import E_ExitCode

NAME  = "hwut.cov.conv.to_humans"
USAGE = ("usage: %s [--from binary|text] [--to binary|text] FILE | --help"
         % NAME)
HELP  = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip()

FORM_TUPLE = ("binary", "text")

GATHERED_TEXT_LINE = b"##VUT-COVERAGE 3"


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
    RETURN: bytes, the record in 'target_form'. A record of version 3,
            the gathered coverage of one source file in an output
            directory (D-42, D-43), is converted as such; any other
            is a per-case record.

    Raises RecordFault where the bytes do not spell a record in
    'source_form'.
    """
    if source_form == "binary": gathered_f = binary_version(data) == 3
    else:                       gathered_f = data.startswith(GATHERED_TEXT_LINE)
    if gathered_f:
        if source_form == "binary": gathered = unpack_gathered(data)
        else: gathered = parse_gathered(data.decode("utf-8"))
        if target_form == "binary": return pack_gathered(gathered)
        return format_gathered(gathered).encode("utf-8")
    if source_form == "binary": record = unpack_record(data)
    else:                       record = parse_record(data.decode("utf-8"))
    if target_form == "binary": return pack_record(record)
    return format_record(record).encode("utf-8")


def main(argv=None, write=None, write_bytes=None):
    """
    RETURN: E_ExitCode (E-1): OK where the file was converted, FAULT
            where it could not be read, REFUSED where the command line
            itself cannot be read.

    'write' takes one line of text; 'write_bytes' takes the converted
    record whole -- stdout's buffer where none is given, so a test may
    capture the face without a process.
    """
    if write is None:       write = print
    if write_bytes is None: write_bytes = sys.stdout.buffer.write
    if argv is None:        argv = sys.argv[1:]

    if "--help" in argv or "-h" in argv:
        from vut.services._core import man_page
        write(man_page(NAME, HELP, usage=USAGE))
        return E_ExitCode.OK

    source_form = target_form = None
    file_list   = []
    i = 0
    while i < len(argv):
        word = argv[i]
        if word in ("--from", "--to"):
            if i + 1 >= len(argv) or argv[i + 1] not in FORM_TUPLE:
                write("REFUSED: '%s' takes one of %s"
                      % (word, ", ".join(FORM_TUPLE))); write(USAGE)
                return E_ExitCode.REFUSED
            if word == "--from": source_form = argv[i + 1]
            else:                target_form = argv[i + 1]
            i += 2
        elif word.startswith("-"):
            write("REFUSED: unknown option '%s'" % word); write(USAGE)
            return E_ExitCode.REFUSED
        else:
            file_list.append(word); i += 1
    if len(file_list) != 1:
        write("REFUSED: %s takes exactly one FILE" % NAME); write(USAGE)
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
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from vut.services._exit import guarded
    sys.exit(guarded(NAME, main, sys.argv[1:]))
