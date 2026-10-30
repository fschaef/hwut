"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.good.link' COMMAND LINE -- a case held against ANOTHER
         case's GOOD (bookkeeper B-32, services E-209). As 'cp' and 'ln -s'
         read: what stands first, what is made last.

    hwut.good.link [--force] <good.txt> <good-file>
    hwut.good.link [--force] <good.txt>... <test-directory>
    hwut.good.link [--force] <test-directory> <test-directory>

    <good.txt>        a '.txt' in a GOOD/ -- the text that is shared
    <good-file>       the case that is linked, spelt as its GOOD file:
                      'b/TEST/GOOD/test-b.sh--y.txt' (or '.link')
    <test-directory>  as target: the link takes the text's own name in
                      its GOOD/; as source: every '.txt' of its GOOD/

writes 'GOOD/<case>.link', one line, the text's path from there, and
enters the case in the book as accepted -- no recording, no 'hwut.accept':
the case is held against a text somebody accepted already.

WHAT IS REFUSED, by name, and then nothing is written:
    a source that is no '.txt' in a GOOD/ (a '.link' is never linked:
    link the text it names)
    a target whose test does not stand in its directory
    a link onto its own case
    a target beyond the source's root ('hwut-root.conf' bounds a link)

WHAT IS NOT OVERWRITTEN: a target case that has a '.txt' or a '.link'
already. Each is listed, and kept; '--force' replaces it.

EXIT STATUS: 0 OK (written, or nothing owed), 1 FAULT (something kept),
2 REFUSED (the command line, or a rule above).
______________________________________________________________________________
"""
import os
import sys
from   pathlib import Path

from ..._core                     import usage_line
from ..._exit                     import E_ExitCode
from ....engine.bookkeeper.api    import (Bookkeeper, LinkFault,
                                          boundary_fault, carries_unaccepted_f,
                                          key_parts_of, text_path_of,
                                          write_link)
from ._good                       import (good_directory_of, in_good_f,
                                          link_name_of, shown,
                                          text_tuple_of)

FACE  = "hwut.good.link"
USAGE = usage_line("usage: %s" % FACE,
                   ("[--force]", "<good.txt|test-directory>...",
                    "<good-file|test-directory>"))

HELP = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip() \
       + "\n" + USAGE


def main(argv=None, write=None):
    """
    RETURN: E_ExitCode, the exit status (see the module purpose).
    """
    if write is None: write = print
    if argv is None:  argv  = sys.argv[1:]
    if "--help" in argv:
        from ..._core import man_page
        write(man_page(FACE, HELP))
        return E_ExitCode.OK
    force_f   = "--force" in argv
    word_list = [word for word in argv if word != "--force"]
    unknown   = [word for word in word_list if word.startswith("-")]
    if unknown or len(word_list) < 2:
        if unknown:
            write("REFUSED: '%s' does not take: %s" % (FACE, ", ".join(unknown)))
        else:
            write("REFUSED: '%s' wants what stands and what is made" % FACE)
        write(USAGE)
        return E_ExitCode.REFUSED

    pair_list, refusal_list = pairs_of(word_list[:-1], word_list[-1])
    refusal_list.extend(rule_refusal for pair in pair_list
                        for rule_refusal in [refusal_of(*pair)] if rule_refusal)
    if refusal_list:
        for line in refusal_list: write("REFUSED: %s" % line)
        write("NOTE: nothing was linked")
        return E_ExitCode.REFUSED

    kept_list = []
    for source, link in pair_list:
        own = text_path_of(link)
        if (own.exists() or link.exists()) and not force_f:
            kept_list.append(own if own.exists() else link)
            continue
        if own.exists(): own.unlink()
        link.parent.mkdir(parents=True, exist_ok=True)
        try:
            write_link(link, source)
        except LinkFault as fault:          # checked above; said, never lost
            write("FAULT: %s" % fault)
            return E_ExitCode.FAULT
        test, choice, _ = key_parts_of(link.name)
        Bookkeeper(link.parent.parent).note_accept(
            test, choice, aspirant_f=carries_unaccepted_f(str(source)))
        write("LINKED  %s -> %s" % (shown(link), shown(source)))
    if kept_list:
        write("NOT OVERWRITTEN -- a GOOD stands; '--force' replaces it:")
        for path in kept_list: write("    %s" % shown(path))
        return E_ExitCode.FAULT
    return E_ExitCode.OK


def pairs_of(source_word_list, target_word):
    """
    RETURN: (list[(Path, Path)], list[str]) -- every (text, link) the
            words ask for, and why a word cannot be read, by name.
    """
    target       = Path(target_word)
    target_dir_f = target.is_dir()
    pair_list, refusal_list = [], []
    if not target_dir_f and len(source_word_list) > 1:
        return [], ["several sources want a test directory as target, "
                    "not '%s'" % target_word]
    for word in source_word_list:
        source = Path(word)
        if source.is_dir():
            if not target_dir_f:
                refusal_list.append("a directory '%s' links into a test "
                                    "directory, not '%s'" % (word, target_word))
                continue
            text_tuple = text_tuple_of(source)
            if not text_tuple:
                refusal_list.append("'%s' holds no '.txt' in its GOOD/" % word)
            pair_list.extend((text, good_directory_of(target)
                                    / link_name_of(text.name))
                             for text in text_tuple)
            continue
        if not source.is_file():
            refusal_list.append("'%s': no such file or directory" % word)
            continue
        if not in_good_f(source) or source.suffix != ".txt":
            refusal_list.append(source_refusal(source))
            continue
        if target_dir_f:
            pair_list.append((source, good_directory_of(target)
                                      / link_name_of(source.name)))
        elif not in_good_f(target) or target.suffix not in (".txt", ".link"):
            refusal_list.append("'%s' names no case: a target is a GOOD "
                                "file ('<dir>/GOOD/<test>--<choice>.txt') or "
                                "a test directory" % target_word)
        else:
            pair_list.append((source, target.parent / link_name_of(target.name)))
    return pair_list, refusal_list


def source_refusal(source):
    """RETURN: str, why the file 'source' cannot be linked."""
    if source.suffix == ".link":
        from ._good import link_text_of
        return ("'%s' is a link -- a link names a '.txt': link the text it "
                "names, %s" % (shown(source), link_text_of(source)))
    return "'%s' is no '.txt' in a GOOD/" % shown(source)


def refusal_of(source, link):
    """
    RETURN: str, why 'link' may not name 'source', by the rule broken;
            None, where it may.
    """
    test_directory = link.parent.parent
    parts = key_parts_of(link.name)
    if parts is None or not (test_directory / parts[0]).is_file():
        return "'%s': no test '%s' stands in '%s'" \
               % (shown(link), parts[0] if parts else link.name,
                  shown(test_directory))
    if os.path.abspath(str(text_path_of(link))) == os.path.abspath(str(source)):
        return "'%s' would link its own case" % shown(link)
    fault = boundary_fault(test_directory, source.parent)
    if fault:
        return "'%s' -> '%s': %s" % (shown(link), shown(source), fault)
    return None


if __name__ == "__main__":
    from ..._exit import guarded
    sys.exit(guarded(FACE, main))
