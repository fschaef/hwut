"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.support' COMMAND LINE -- the test writing support of one
         language and its demonstration, written where the person says,
         from any installed form (services E-217).

    hwut.support <language> <dir>

<language> is one of 'support/test_writing/LANGUAGES.conf': python, perl,
c, cpp, java, rust, go, node, verilog, vhdl, bash, powershell, erlang,
guile, haskell, prolog, fortran.

<dir> receives

    hwut-root.conf      the template a new root receives
    <language>/         the language's test writing support
    <required>/         each port it stands on ('requires' in LANGUAGES.conf,
                        e.g. 'c' below 'cpp')
    TEST/               the demonstration in that language: its tests and
                        GOOD files ('.link's resolved into the files they
                        name)

and the face ends with MAKE IT IMPORTABLE: the lines that make the support
in '<dir>/<language>' reach a test of the person's own, and the line such a
test then writes. Then

    cd <dir>/TEST && hwut --plain

runs green. Nothing outside <dir> is written.

THE SOURCE is 'support/' where it stands (a clone), else the archive
'support.tar.xz' an installed hwut carries beside this module. The
demonstration names the support's place on ONE line, marked 'HWUT-SUPPORT-PATH', by the literal
'../../../test_writing/<language>'; written out it reads '../<language>',
the copy beside it.

REFUSED where <dir> stands and is not empty: the support lands in a place of
its own, never over what stands.

EXIT STATUS (E-1, services/_exit.py):
    0  OK       the tree written
    2  REFUSED  no such language, <dir> not empty or not writable, the
                language not carried, or the command line cannot be read
______________________________________________________________________________
"""
import os
import re
import shutil
import sys
import tarfile
import tempfile

from ..cmdline import face_parser, parse_or_refuse, usage_of
from ..._exit  import E_ExitCode

HWUT          = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(
                    __file__)), "..", "..", ".."))
SUPPORT       = os.path.join(HWUT, "support")
#  An installed hwut carries 'support/' as this archive, beside the face.
ARCHIVE       = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "support.tar.xz")
LANGUAGE_FILE = os.path.join("support", "test_writing", "LANGUAGES.conf")
MARK          = "HWUT-SUPPORT-PATH"
#  What a run or a build left in the source tree is no part of what is
#  written; nor is the port's own TEST -- the demonstration is the one.
LEFT_BEHIND   = ("OUT", "TMP", "__pycache__", "hwut-traces*", "hwut.log",
                 ".coverage", "node_modules",
                 #  ... and what a build left: executables, objects,
                 #  libraries, per-target build directories.
                 "*.exe", "*.o", "*.hi", "*.dyn_hi", "*.dyn_o", "*.so",
                 "*.rlib", "*.beam", "*.class", "*.work", "*.classes",
                 "*.o.d", "*.obj", "build-*", ".gowork", "hwut_vterm_server", "ebin",
                 "hwut_vterm_port")
#  Fortran's module files are products, Go's 'go.mod' is a source.
MODULE_PRODUCT = "*.mod"
KEPT_NAME_SET  = {"go.mod"}
LINK_SUFFIX   = ".link"


def fallback_literal(language):
    """
    RETURN: str, the literal by which a demonstration in the source tree
            names its port: '../../../test_writing/<language>'.
    """
    return "../../../test_writing/%s" % language


def source_root(language, temp_dir):
    """
    RETURN: str, a directory holding 'support/test_writing/<language>' and
                 'support/demo/<language>/TEST' (and the Python demo the
                 links name) -- 'HWUT' itself in a clone, else 'temp_dir'
                 with the archive's members for the language extracted.
            None, where neither carries the language.
    """
    if os.path.isdir(os.path.join(SUPPORT, "demo", language, "TEST")) \
       and os.path.isdir(os.path.join(SUPPORT, "test_writing", language)):
        return HWUT
    if not os.path.isfile(ARCHIVE): return None
    prefix_tuple = ("support/test_writing/",
                    "support/demo/%s/" % language,
                    "support/demo/python/TEST/GOOD/")
    with tarfile.open(ARCHIVE, "r:xz") as archive:
        member_list = [m for m in archive.getmembers()
                       if m.name.startswith(prefix_tuple)]
        if not any(m.name.startswith(prefix_tuple[1]) for m in member_list):
            return None
        try:
            archive.extractall(temp_dir, members=member_list, filter="data")
        except TypeError:       # a Python before extraction filters
            archive.extractall(temp_dir, members=member_list)
    return temp_dir


def language_db(root):
    """
    RETURN: dict, language -> dict of its 'LANGUAGES.conf' entry: 'home',
            'use' (list[str], the MAKE IT IMPORTABLE lines, '<dir>' standing
            for where the support is written), 'test' (str, the line a test
            writes, or list[str], its lines), 'note' (str or None) and 'requires' (list[str], the
            ports it stands on); {} where the file is absent.
    """
    from ....support.test_writing.python import hwut_hocon
    path = os.path.join(root, LANGUAGE_FILE)
    if not os.path.isfile(path): return {}
    with open(path, encoding="utf-8") as fh:
        line_list = [hwut_hocon.SourceLine(text, i + 1, 0)
                     for i, text in enumerate(fh.read().split("\n"))]
    document, _ = hwut_hocon.parse(line_list, path)
    result = {}
    for entry in document.entry_list:
        node = entry.node
        def value(key, default=None):
            """RETURN: the plain value of 'key' in the entry; 'default', else."""
            item = node.get(key) if hasattr(node, "get") else None
            if item is None: return default
            if hasattr(item.node, "item_list"):
                return [x.value for x in item.node.item_list]
            return item.node.value
        result[entry.key] = {"home": value("home"),
                             "use":  value("use", []),
                             "test": value("test", ""),
                             "note": value("note"),
                             "requires": value("requires", []),
                             "title": value("title")}
    return result


def _ignored(directory, name_list, extra=()):
    """
    RETURN: set[str], the names in 'name_list' (below 'directory') that are
            not written: what a run or a build left, and 'extra'.
    """
    import fnmatch
    out = set(shutil.ignore_patterns(*(LEFT_BEHIND + tuple(extra)))(
              directory, name_list))
    out |= {n for n in name_list if fnmatch.fnmatch(n, MODULE_PRODUCT)
            and n not in KEPT_NAME_SET}
    return out


def _copied(source, target):
    """
    RETURN: None. 'source' is copied to 'target', what a run left behind
            excepted; a file opening with '#!' is made executable again (a
            wheel carries no mode bits).
    """
    shutil.copytree(source, target, ignore=_ignored)
    for directory, _, name_list in os.walk(target):
        for name in name_list:
            path = os.path.join(directory, name)
            with open(path, "rb") as fh: head = fh.read(2)
            if head == b"#!":
                os.chmod(path, os.stat(path).st_mode | 0o111)


def _port_written(root, language, target):
    """
    RETURN: str, '<target>/<language>', the language's support written:
            its modules and documents, its own TEST left out.
    """
    port = os.path.join(target, language)
    if os.path.isdir(port): return port            # required twice
    shutil.copytree(os.path.join(root, "support", "test_writing", language),
                    port, ignore=lambda d, n: _ignored(d, n, ("TEST",)))
    return port


def _links_resolved(test_dir, source_test_dir):
    """
    RETURN: int, the number of '.link's in 'test_dir/GOOD' replaced by the
            '.txt' nominal they name -- read from where the link stood in
            'source_test_dir'.
    """
    good, count = os.path.join(test_dir, "GOOD"), 0
    if not os.path.isdir(good): return 0
    for name in sorted(os.listdir(good)):
        if not name.endswith(LINK_SUFFIX): continue
        link = os.path.join(good, name)
        with open(link, encoding="utf-8") as fh: target = fh.read().strip()
        named = os.path.normpath(os.path.join(source_test_dir, "GOOD", target))
        shutil.copyfile(named, link[:-len(LINK_SUFFIX)] + ".txt")
        os.remove(link)
        count += 1
    return count


def _marked_line_set(test_dir, language, replacement):
    """
    RETURN: int, the number of files in 'test_dir' whose marked line now
            names the port by 'replacement' instead of the source tree's
            literal.
    """
    literal, count = fallback_literal(language), 0
    for directory, _, name_list in os.walk(test_dir):
        for name in name_list:
            path = os.path.join(directory, name)
            try:
                with open(path, encoding="utf-8") as fh: text = fh.read()
            except (UnicodeDecodeError, OSError):
                continue
            if literal not in text: continue
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text.replace(literal, replacement))
            count += 1
    return count


def _documents_repointed(path, source_test_dir, language, target):
    """
    RETURN: int, the number of document paths rewritten in the feature file
            'path': each relative one, as it resolved from the demonstration
            in hwut's own layout, made to point at its copy in 'target'
            (the support, the demonstration) or, where nothing was copied,
            absolute into hwut; 0 where the file does not stand.

    A COPY KEEPS ITS REFERENCES (ND1).
    """
    if not os.path.isfile(path): return 0
    home_test = os.path.join(SUPPORT, "demo", language, "TEST")
    home_port = os.path.join(SUPPORT, "test_writing", language)
    with open(path, encoding="utf-8") as fh: text = fh.read()
    count = [0]
    def repointed(match):
        """RETURN: str, the quoted path, valid from 'target'."""
        count[0] += 1
        resolved = os.path.normpath(os.path.join(home_test, match.group(1)))
        for home, copy in ((home_test, os.path.join(target, "TEST")),
                           (home_port, os.path.join(target, language))):
            if resolved == home or resolved.startswith(home + os.sep):
                return '"%s"' % os.path.relpath(
                    os.path.join(copy, os.path.relpath(resolved, home)),
                    os.path.join(target, "TEST"))
        return '"%s"' % resolved
    text = re.sub(r'"((?:\.\./)+[^"]*)"', repointed, text)
    with open(path, "w", encoding="utf-8") as fh: fh.write(text)
    return count[0]


def written(language, target, replacement=None):
    """
    RETURN: [0] str, the 'TEST' directory written below 'target'.
            [1] dict, the language's 'LANGUAGES.conf' entry (language_db).
            None, where this installation carries no such language.
    Raises OSError where 'target' cannot be written.

    'replacement' takes the place of the source literal on the marked line;
    by default '../<language>', the copy written beside TEST.
    """
    temp_dir = tempfile.mkdtemp(prefix="hwut_support_")
    try:
        root = source_root(language, temp_dir)
        if root is None: return None
        entry = language_db(root).get(language)
        if entry is None: return None
        source_test = os.path.join(root, "support", "demo", language, "TEST")
        os.makedirs(target, exist_ok=True)
        for port in [language] + list(entry["requires"]):
            _port_written(root, port, target)
        test = os.path.join(target, "TEST")
        _copied(source_test, test)
        _links_resolved(test, source_test)
        _marked_line_set(test, language,
                         replacement or "../%s" % language)
        _documents_repointed(os.path.join(test, "hwut-features.conf"),
                             source_test, language, target)
        #  THE ROOT IS THE TEMPLATE (services E-25, D-43).
        from ..._boundary import written as root_written
        root_written(target)
        return test, entry
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def importable_lines(entry, target):
    """
    RETURN: list[str], the MAKE IT IMPORTABLE block for 'entry' with
            '<dir>' replaced by the absolute 'target'.
    """
    where = os.path.abspath(target)
    line_list = ["MAKE IT IMPORTABLE -- for a test of your own:"]
    line_list += ["    %s" % line.replace("<dir>", where)
                  for line in entry["use"]]
    test = entry["test"]
    for i, line in enumerate([test] if isinstance(test, str) else test):
        if not line: continue
        if i == 0: line_list.append("A TEST THEN WRITES:")
        line_list.append("    %s" % line.replace("<dir>", where))
    if entry["note"]:
        line_list.append("NOTE:    %s" % entry["note"].replace("<dir>", where))
    return line_list


NAME   = "hwut.support"
PARSER = face_parser(NAME, "Write the test writing support of a language "
                     "and its demonstration.", wish_f=False,
                     word_help="the language, then the directory to write",
                     word_metavar="<language> <dir>")
USAGE  = usage_of(PARSER, {"word": True})
HELP   = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip() \
         + "\n" + USAGE


def main(argv=None, write=None):
    """
    RETURN: E_ExitCode, the exit status (see the module purpose).
    """
    write = write or print
    argv  = sys.argv[1:] if argv is None else list(argv)
    if "--help" in argv:
        from ..._core import man_page
        write(man_page(NAME, HELP))
        return E_ExitCode.OK
    arguments, completion_f = parse_or_refuse(PARSER, argv, write)
    if completion_f: return E_ExitCode.OK
    db = language_db(HWUT)
    known = ", ".join(db)
    if arguments is None or len(arguments.word) != 2:
        if arguments is not None:
            write("REFUSED: '%s' takes two words, a language and the "
                  "directory to write -- the languages: %s" % (NAME, known))
        write(USAGE)
        return E_ExitCode.REFUSED
    language, target = arguments.word
    if language not in db:
        write("REFUSED: '%s' is no language of the test writing support "
              "-- the languages: %s" % (language, known))
        return E_ExitCode.REFUSED
    title = db[language]["title"] or language
    if os.path.isdir(target) and os.listdir(target):
        write("REFUSED: '%s' is not empty -- name a new directory" % target)
        return E_ExitCode.REFUSED
    if os.path.exists(target) and not os.path.isdir(target):
        write("REFUSED: '%s' stands and is no directory" % target)
        return E_ExitCode.REFUSED
    try:
        result = written(language, target)
    except OSError as error:
        write("REFUSED: '%s' cannot be written: %s" % (target, error))
        return E_ExitCode.REFUSED
    if result is None:
        write("REFUSED: this installation carries no test writing support "
              "in %s (neither 'support/' nor 'support.tar.xz')" % title)
        return E_ExitCode.REFUSED
    test, entry = result
    write("WRITTEN: %s -- the test writing support in %s, and its "
          "demonstration" % (target, title))
    write("    %s" % os.path.join(target, language))
    for port in entry["requires"]:
        write("    %s   (the %s support stands on it)"
              % (os.path.join(target, port), title))
    write("    %s" % test)
    write("NEXT:    cd %s && hwut --plain" % test)
    for line in importable_lines(entry, target):
        write(line)
    return E_ExitCode.OK


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from ..._exit import guarded
    sys.exit(guarded(NAME, main))
