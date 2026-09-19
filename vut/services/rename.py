"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.rename' COMMAND LINE -- a test, or one choice of it,
         RENAMED, and a test CARRIED into another directory: its
         nominals, candidates, book entry, register entry, coverage
         records and labels follow the new name.

    hwut.rename <app> -to <app'>               [--dont-ask] [--directory=<path>]
    hwut.rename <app> <choice> -to <choice'>   [--dont-ask] [--directory=<path>]
    hwut.rename <app> -to <path>/<app'>        [--dont-ask] [--directory=<path>]
    hwut.move   <app> <app'>                   == hwut.rename <app> -to <app'>
                                               [--no-warning] [--silent]

'-to' IS A KEYWORD. One word before it names an app; two name an app
and one of its choices. One word follows it: the fresh name. A fresh
name carrying '/' names a DIRECTORY and a name; a fresh name that IS
an existing directory means INTO it, the app's name unchanged. The app
word may itself be a path ('a/TEST/app.sh', E-45); '--directory'
names the source directory, and a relative app path is read against
it. A choice
never crosses a directory.

NO RECORD CONTENT IS TOUCHED, save one: a coverage record carries its
RUN ID, and ids are the DIRECTORY'S. Within the directory the register
keeps the id and the record moves untouched. ACROSS a directory the
source register RETIRES the id, the target register ISSUES a fresh
one, and the record is RE-SEATED under it -- through coverage's own
seam, not by hand; moved unchanged it would decode in the target to
another test, or to nobody.

A RENAME IS NOT A FRESH START. What the test did under its old name it
did, and the book entry moves with everything in it: the recorded runs,
the stderr note, and ANY STAIN. A test that switched results does not
launder itself by being called something else, or by moving house.
('hwut.remove' is the verb for wanting no history.)

WHAT MOVES, each step announced:

    NOMINALS     'GOOD/<key>.<subject>' per subject
    CANDIDATES   'TMP/store/<key>.<subject>' and every sidecar --
                 the freshness stamp, the raw stream, the cadence, the
                 error witness, the coverage record
    THE BOOK     the entry re-keyed; across a directory: given up by
                 the source's book, adopted by the target's
    THE REGISTER within the directory the name follows and the id
                 stands; across, retired here and issued there
    THE LABELS   the boundary records, last ('services/_follow.py')

WHAT IS NOT TOUCHED: the test application file, its '@hwut' block,
and any 'hwut.conf' 'apps' section naming it. Renaming or moving the
SOURCE is the author's act -- 'git mv' -- and this face FOLLOWS it;
it does not perform it, and it edits no declaration (E-48). It READS
them and SAYS what disagrees, telegraphically, before asking:

    NOTE  application 'test-app.sh' stands under the OLD name -- git mv
    NOTE  '@hwut' declares 'one', not 'first' -- edit the block
    NOTE  hwut.conf apps section 'test-app.sh' -- rename it

'--no-warning' drops the notes; '--silent' drops everything but a
refusal or a fault. An application standing under BOTH names is
refused: which one is the test is the author's to decide first.

IT REFUSES A COLLISION. A fresh name that already stands in the target
book would swallow another test's history; it is refused at the door,
by name, and nothing is moved.

IT ASKS FIRST, showing every move, unless '--dont-ask'.

A TEST THAT IS NOT IN THE BOOK is not an error: there is nothing to
follow, and the face says so.

EXIT STATUS (E-1, services/_exit.py):
    0  the rename was made, or there was nothing to rename
    1  something could not be moved
    2  the command line cannot be read, or a name collides
    3  the command line reads, and names nothing
______________________________________________________________________________
"""
from pathlib import Path
import sys
from typing import Callable, Optional, Union

from   vut.engine.bookkeeper.api import Bookkeeper, Store
from   vut.engine.bookkeeper.api import TestIdFault
from   vut.engine.bookkeeper.api import BOOK_FORBIDDEN_IN_NAME
from   vut.engine.coverage.api   import (pack_record, unpack_record,
                                         seated, RecordFault)
from   vut.engine.orchestrator.exploration.reader import (read_header,
                                                          read_conf)
from   ._follow                  import labels_renamed
from   ._target                  import split_words, TargetError
from   ._exit                    import E_ExitCode
from   vut.services.lib.cmdline  import face_parser, parse_or_refuse

KEYWORD = "-to"

#  THE STANDARD READER (E-84), FOR THE VOCABULARY ONLY. 'hwut.rename'
#  has a GRAMMAR -- '<words> -to <fresh>', in three forms -- which no
#  generated usage can state, so its synopsis below stays written; the
#  parser answers what is refused, what is suggested, what completes.
#  '-to' is a grammar word, not an option: taken out before the parser.
PARSER = face_parser("hwut.rename", "Rename a test application or a "
                     "choice, and everything that names it.",
                     wish_f=False, word_help="<app> [<choice>]")
PARSER.add_argument("--dont-ask", action="store_true")
PARSER.add_argument("--directory", default=None)
PARSER.add_argument("--no-warning", action="store_true")
PARSER.add_argument("--silent", action="store_true")
ARG_DB = {"--directory": True}
#  What '_read' answers where the line asked only for the completion
#  table: printed, nothing else to do.
COMPLETED = object()

USAGE = ("usage: hwut.rename <app> -to <app'>              [--dont-ask] "
         "[--directory=<path>] [--no-warning] [--silent]\n"
         "       hwut.rename <app> <choice> -to <choice'>  [--dont-ask] "
         "[--directory=<path>]\n"
         "       hwut.rename <app> -to <path>/<app'>       [--dont-ask] "
         "[--directory=<path>]\n"
         "       hwut.move   <app> <app'>                  == hwut.rename "
         "<app> -to <app'>")

#  The licence line and the rule are the FILE's, not the face's.
HELP = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip() \
       + "\n\n" + USAGE


def _shown(store: Store, path: Union[str, Path]) -> str:
    """RETURN: str, the path as it reads from the SOURCE test directory
    -- 'GOOD/x.stdout' and 'TMP/store/x.stdout' are DIFFERENT files and
    a basename alone would print them alike; a target in another
    directory reads with that directory in front."""
    try:               return str(Path(path).relative_to(store.directory))
    except ValueError: return str(path)


def _same_place(a: Union[str, Path], b: Union[str, Path]) -> bool:
    """RETURN: bool, True where the two paths name one directory."""
    return Path(a).resolve() == Path(b).resolve()


class Rename:
    """ONE rename, read off the command line: what stands where, and
    what is to stand where.

        test, choice       the source key; 'choice' None for an app
        fresh_test         the name the app is to bear
        fresh_choice       the name the choice is to bear; None for an app
        source, target     the two Stores; the SAME object within one
                           directory
        whole_test_f       True for the app form
        write              callable for logging progress and faults
    """
    __slots__ = ("test", "choice", "fresh_test", "fresh_choice",
                 "source", "target", "whole_test_f", "write")

    def __init__(self, test: str, choice: Optional[str], fresh_test: str,
                 fresh_choice: Optional[str], source: Store, target: Store,
                 whole_test_f: bool, write: Callable[[str], None]):
        self.test = test
        self.choice = choice
        self.fresh_test = fresh_test
        self.fresh_choice = fresh_choice
        self.source = source
        self.target = target
        self.whole_test_f = whole_test_f
        self.write = write

    @property
    def across_f(self) -> bool:
        """RETURN: bool, True where source and target are two
        directories."""
        return self.source is not self.target

    def text(self) -> str:
        """RETURN: str, 'app [choice] -> [dir/]app' [choice]', as
        announced."""
        head = self.test if self.choice is None \
               else f"{self.test} {self.choice}"
        if self.whole_test_f:
            tail = self.fresh_test if not self.across_f \
                   else str(Path(self.target.directory) / self.fresh_test)
        else:
            tail = f"{self.test} {self.fresh_choice}"
        return f"{head} -> {tail}"

    def move_tuple(self) -> tuple[tuple[str, str], ...]:
        """
        RETURN: tuple[(str, str)], (from, to) for every recorded artefact
                of that key that STANDS -- nominals, candidates, sidecars,
                the error witness and the coverage record; 'to' on the
                TARGET store's ground. Sorted by source, so the
                announcement is stable.

        The app form follows EVERY choice the book knows of the test.

        The subjects are read from what LIES THERE, not from what a
        configuration says: a rename must reach a subject whose
        declaration has since been edited away, or it leaves an orphan
        under the old name.
        """
        source, target = self.source, self.target
        found = []
        for old_choice, new_choice in self._choice_pair_list():
            #  THE ERROR WITNESS FOLLOWS THE NAME like the rest of the
            #  run's product; it is asked for by name, not as a subject.
            a = str(source.error_witness_path(self.test, old_choice))
            b = str(target.error_witness_path(self.fresh_test, new_choice))
            if Path(a).exists(): found.append((a, b))
            for subject in ("stdout",):
                for verb in ("candidate_path", "freshness_path", "raw_path",
                             "timing_path", "nominal_path"):
                    a = str(getattr(source, verb)(self.test, old_choice,
                                                  subject))
                    b = str(getattr(target, verb)(self.fresh_test,
                                                  new_choice, subject))
                    if Path(a).exists(): found.append((a, b))
            a = str(source.bookkeeper.coverage_path(self.test, old_choice))
            if Path(a).exists():
                found.append((a, str(target.bookkeeper.coverage_path(
                                         self.fresh_test, new_choice))))
        return tuple(sorted(set(found)))

    def _choice_pair_list(self) -> list[tuple[str, str]]:
        """RETURN: list[(choice, fresh choice)], every choice the rename
        touches: all of the test's for the app form (its choiceless key
        where the book knows none), the one for the choice form."""
        if self.whole_test_f:
            pair_list = [(c, c) for c in
                         self.source.bookkeeper.choices(self.test)]
            return pair_list or [(self.choice, self.choice)]
        return [(self.choice, self.fresh_choice)]

    def follow(self) -> bool:
        """
        RETURN: bool, True where every step succeeded; False where one
                failed -- announced by name, and the rest still attempted.

        THE ORDER: artefacts first, then the book, then the register, then
        the coverage records' seats, then the labels. A crash between
        steps leaves files under the new name and a book that still says
        the old one, which the next run reports as a missing GOOD -- loud,
        and mendable by re-running the rename.
        """
        write = self.write
        #  THE CHOICES ARE READ BEFORE THE BOOK GIVES THE ENTRY UP: after
        #  that step the source book knows none of them.
        choice_list = [c for _, c in self._choice_pair_list()]
        good_f = self._files_followed()
        if not self._book_followed(): return False
        run_db = self._register_followed(choice_list)
        if run_db is None: good_f = False
        elif self.across_f and not self._records_reseated(run_db):
            good_f = False
        #  THE BOUNDARY RECORDS FOLLOW LAST ('services/_follow.py'): a
        #  crash above leaves an entry naming the old name -- loud, and
        #  findable -- never a record silently pointing at nothing.
        if not labels_renamed(str(self.source.directory), self.test,
                              self.choice, self.fresh_test,
                              self.fresh_choice, self.whole_test_f,
                              write,
                              target_directory=str(self.target.directory)):
            good_f = False
        return good_f

    def _files_followed(self) -> bool:
        """RETURN: bool, True where every artefact moved."""
        good_f = True
        write = self.write
        for source_path, target_path in self.move_tuple():
            try:
                Path(target_path).parent.mkdir(parents=True, exist_ok=True)
                Path(source_path).rename(target_path)
                write(f"    {_shown(self.source, source_path)} -> {_shown(self.source, target_path)}")
            except OSError as error:
                write(f"    FAULT: {_shown(self.source, source_path)} -- {error}")
                good_f = False
        return good_f

    def _book_followed(self) -> bool:
        """RETURN: bool, True where the book entry re-keyed, moved, or
        never stood; False on a fault, announced."""
        book = self.source.bookkeeper
        write = self.write
        try:
            if not self.whole_test_f:
                moved = book.rename_choice(self.test, self.choice,
                                           self.fresh_choice)
            elif not self.across_f:
                moved = book.rename_test(self.test, self.fresh_test)
            else:
                entry = book.remove_test(self.test)
                moved = None
                if entry is not None:
                    try:
                        moved = self.target.bookkeeper.adopt(
                                    self.fresh_test, entry)
                    except KeyError:
                        #  THE SOURCE TAKES ITS OWN ENTRY BACK: half a
                        #  move of a history is worse than none.
                        book.adopt(self.test, entry)
                        raise
            status_msg = (
                "none stood" if moved is None
                else f"adopted by '{self.target.directory}'" if self.across_f
                else "re-keyed"
            )
            write(f"    book entry: {status_msg}")
            return True
        except KeyError as error:
            write(f"    FAULT: book -- {error}")
            return False

    def _register_followed(self, choice_list: list[str]) -> Optional[dict[str, int]]:
        """
        RETURN: dict, choice name -> TestRunId the moved run bears NOW --
                the standing id within a directory, the fresh id across
                one; empty where the test was never registered.
                None, on a register fault, announced.

        THE REGISTER MOVED IN THE BOOK'S OWN ACT (B-9): 'rename_test' and
        'rename_choice' re-keyed it, 'remove_test' retired the source's
        id, 'adopt' issued the target's. This step READS and SAYS.
        'choice_list' names the choices whose fresh ids the re-seat needs,
        read from the source book before it gave the entry up.
        """
        write = self.write
        try:
            target = self.target.bookkeeper
            if not self.whole_test_f:
                run_id = target.run_id_of(self.test, self.fresh_choice)
                if run_id is None:
                    write("    register: not registered"); return {}
                write("    register: choice name follows; the id stands")
                return {self.fresh_choice: run_id}
            if not self.across_f:
                run_id = target.run_id_of(self.fresh_test)
                if run_id is None:
                    write("    register: not registered"); return {}
                write("    register: name follows; the id stands")
                return {}
            run_db = {}
            for choice in choice_list:
                run_id = target.run_id_of(self.fresh_test, choice)
                if run_id is not None: run_db[choice] = run_id
            if not run_db:
                write("    register: not registered"); return {}
            ids_str = ", ".join(str(r) for r in sorted(run_db.values()))
            write(f"    register: retired here; issued {ids_str} there")
            return run_db
        except TestIdFault as error:
            write(f"    FAULT: register -- {error}")
            return None

    def _records_reseated(self, run_db: dict[str, int]) -> bool:
        """RETURN: bool, True where every coverage record that travelled
        now names its fresh run id; False on a fault, announced."""
        good_f = True
        write = self.write
        for choice, run_id in run_db.items():
            path = Path(self.target.bookkeeper.coverage_path(
                            self.fresh_test, choice))
            if not path.exists(): continue
            try:
                record = unpack_record(path.read_bytes())
                data = pack_record(seated(record, run_id))
                path.write_bytes(data)
                write(f"    coverage record: re-seated under {run_id}")
            except (OSError, RecordFault) as error:
                write(f"    FAULT: coverage record {_shown(self.source, path)} -- {error}")
                good_f = False
        return good_f

    def situation_notes(self) -> tuple[list[str], Optional[str]]:
        """
        RETURN: [0] list[str], telegraphic NOTE lines: the application's
                    whereabouts, the '@hwut' block's choices, any
                    'hwut.conf' apps section -- each only where it
                    DISAGREES with the rename, or where nothing could be
                    read. Empty where everything agrees.
                [1] str, a refusal where the application stands under BOTH
                    names; None otherwise.

        READ AND SAY, NEVER EDIT (E-48): the source and the declarations
        are the author's; the face names what he has to touch.
        """
        note_list = []
        src_dir, dst_dir = Path(self.source.directory), Path(self.target.directory)
        old_path = src_dir / self.test
        new_path = dst_dir / self.fresh_test
        old_f, new_f = old_path.is_file(), new_path.is_file()
        if self.whole_test_f:
            if old_f and new_f:
                return note_list, (f"application stands under BOTH names: '{_shown(self.source, old_path)}' "
                                   f"and '{_shown(self.source, new_path)}' -- decide which is the test first")
            if old_f:
                note_list.append(f"NOTE  application '{self.test}' stands under the OLD "
                                 f"name -- git mv {_shown(self.source, old_path)} "
                                 f"{_shown(self.source, new_path)} (E-16)")
            elif not new_f:
                note_list.append(f"NOTE  application stands under NEITHER name "
                                 f"-- nothing to run under '{self.fresh_test}'")
        else:
            #  A CHOICE RENAME: the file is the same; its '@hwut' block
            #  names the choices.
            path = old_path if old_f else None
            if path is None:
                note_list.append(f"NOTE  application '{self.test}' not found -- the "
                                  "'@hwut' block cannot be read")
            else:
                try:
                    spec, _ = read_header(path.read_text(encoding="utf-8"),
                                          str(path))
                except (OSError, UnicodeDecodeError):
                    spec = None
                if spec is None:
                    note_list.append(f"NOTE  no '@hwut' block read in '{self.test}'")
                elif self.fresh_choice not in spec.choice_db:
                    choices_str = ", ".join(f"'{c}'" for c in spec.choice_db if c)
                    note_list.append(f"NOTE  '@hwut' declares {choices_str} -- edit the "
                                     f"block: '{self.choice}' -> '{self.fresh_choice}'")
        #  hwut.conf 'apps' SECTIONS: the source's names the old name, the
        #  target's may name the new one already.
        for where, name, verb in ((src_dir, self.test, "rename it"),):
            conf = where / "hwut.conf"
            if not conf.is_file(): continue
            try:
                _, app_db, _ = read_conf(conf.read_text(encoding="utf-8"),
                                         str(conf))
            except (OSError, UnicodeDecodeError):
                continue
            entry = app_db.get(name)
            if entry is None: continue
            if self.whole_test_f:
                carry_msg = " / carry it" if self.across_f else ""
                note_list.append(f"NOTE  hwut.conf apps section '{name}' in {_shown(self.source, conf)} -- "
                                 f"{verb}{carry_msg}")
            elif self.choice in entry.choice_db \
                 and self.fresh_choice not in entry.choice_db:
                note_list.append(f"NOTE  hwut.conf apps section '{name}' in {_shown(self.source, conf)} "
                                 f"declares '{self.choice}' -- edit it")
        return note_list, None


def _read(argv: list[str], write: Callable[[str], None]):
    """
    RETURN: [0] Rename  what the words ask for
                None    they cannot be read -- refused aloud, with the
                        usage
                ()      they name nothing
                COMPLETED  they asked for the completion table, which
                        was printed
            [1] bool    '--dont-ask' was said
    """
    if "--yes" in argv:
        #  E-68: "yes to what?" -- on the command line, before the
        #  question exists, the word names an answer to nothing.
        #  Refused BY NAME so a script that still says it is told.
        write("REFUSED: '--yes' is gone (E-68) -- '--dont-ask' is "
              "the one word for 'do not ask'")
        return None, False
    #  THE GRAMMAR WORD IS HELD OUT, its place remembered by a stand-in
    #  the parser takes as a word.
    stand_in = "\x00to"
    arguments, completion_f = parse_or_refuse(
        PARSER, [stand_in if a == KEYWORD else a for a in argv], write, ARG_DB)
    if completion_f: return COMPLETED, False
    if arguments is None:
        write(USAGE)
        return None, False
    directory = arguments.directory or "."
    yes_f     = arguments.dont_ask
    word_list = [KEYWORD if w == stand_in else w for w in arguments.word]
    if not Path(directory).is_dir():
        write(f"REFUSED: the directory '{directory}' does not exist")
        write(USAGE)
        return None, yes_f
    if not word_list:
        write("EMPTY: 'hwut.rename' names nothing to rename")
        return (), yes_f
    if word_list.count(KEYWORD) != 1:
        write(f"REFUSED: 'hwut.rename' takes '<words> {KEYWORD} <fresh>' -- "
              f"'{KEYWORD}' must stand once")
        write(USAGE)
        return None, yes_f
    at     = word_list.index(KEYWORD)
    before = word_list[:at]
    after  = word_list[at + 1:]
    if len(before) not in (1, 2) or len(after) != 1:
        write(f"REFUSED: 'hwut.rename' takes '<app> {KEYWORD} <app'>' or "
              f"'<app> <choice> {KEYWORD} <choice'>' -- {len(before)} word(s) before, "
              f"{len(after)} after")
        write(USAGE)
        return None, yes_f
    try:
        source_dir, before = split_words(before, directory)
    except TargetError as error:
        write(f"REFUSED: {error}")
        write(USAGE)
        return None, yes_f
    test   = before[0]
    choice = before[1] if len(before) == 2 else None
    fresh  = after[0]
    whole_test_f = choice is None

    if whole_test_f:
        fresh_path = Path(fresh)
        if fresh_path.is_dir() or fresh.endswith(('/', '\\')):
            target_dir = str(fresh_path).rstrip('/\\') or '.'
            fresh_test = test
        elif '/' in fresh or '\\' in fresh:
            p = Path(fresh)
            target_dir = str(p.parent) if str(p.parent) != '' else '.'
            fresh_test = p.name
        else:
            target_dir, fresh_test = source_dir, fresh
        fresh_choice = None
        if not Path(target_dir).is_dir():
            write(f"REFUSED: the target directory '{target_dir}' does not exist")
            return None, yes_f
    else:
        if '/' in fresh or '\\' in fresh:
            write(f"REFUSED: a choice never crosses a directory -- "
                  f"'{fresh}' carries a path")
            write(USAGE)
            return None, yes_f
        target_dir, fresh_test, fresh_choice = source_dir, test, fresh
    for forbidden in BOOK_FORBIDDEN_IN_NAME:
        if forbidden in (fresh_test if whole_test_f else fresh_choice):
            write(f"REFUSED: '{forbidden}' cannot stand in a name")
            return None, yes_f

    source = Store(Bookkeeper(source_dir))
    target = source if _same_place(source_dir, target_dir) \
             else Store(Bookkeeper(target_dir))
    if target is source and fresh_test == test \
       and (whole_test_f or fresh_choice == choice):
        target_name = fresh_test if whole_test_f else fresh_choice
        write(f"REFUSED: '{target_name}' is the name it already bears")
        return None, yes_f
    return Rename(test, choice, fresh_test, fresh_choice, source, target,
                  whole_test_f, write), yes_f


def main(argv=None, write=None, read_line=None):
    """
    RETURN: E_ExitCode, the exit status (E-1): OK where the rename was
            made or there was nothing to rename, FAULT where a step
            failed, REFUSED where the command line cannot be read or a
            name collides, EMPTY where it names nothing.
    """
    if write is None:     write     = print
    if read_line is None: read_line = sys.stdin.readline
    if argv is None:      argv      = sys.argv[1:]
    if "--help" in argv:
        write(HELP)
        return E_ExitCode.OK

    warning_f = "--no-warning" not in argv and "--silent" not in argv
    if "--silent" in argv:
        loud = write
        def write(text, _loud=loud):
            """RETURN: None. Under '--silent' only a refusal or a fault
            is said."""
            if text.startswith(("REFUSED", "EMPTY")) or "FAULT" in text:
                _loud(text)
    rename, yes_f = _read(argv, write)
    if rename is COMPLETED: return E_ExitCode.OK
    if rename is None: return E_ExitCode.REFUSED
    if rename == ():   return E_ExitCode.EMPTY

    note_list, refusal = rename.situation_notes()
    if refusal is not None:
        write(f"REFUSED: {refusal}")
        return E_ExitCode.REFUSED

    #  A COLLISION IS REFUSED BEFORE ANYTHING MOVES: half a rename
    #  onto a live name is worse than none.
    if rename.whole_test_f:
        #  THE BOOK AND THE REGISTER ARE BOTH ASKED: a name standing
        #  only in the register still owns an id, and the fresh name
        #  would be issued THAT id -- another test's.
        for where, standing in (
                ("book",     set(rename.target.bookkeeper.tests())),
                ("register", set(rename.target.bookkeeper.roster()))):
            if rename.fresh_test in standing and not (
                    not rename.across_f and rename.fresh_test == rename.test):
                write(f"REFUSED: '{rename.fresh_test}' already stands in the {where} of '{rename.target.directory}' -- "
                      "a rename onto it would swallow its history")
                return E_ExitCode.REFUSED
    elif rename.fresh_choice in rename.source.bookkeeper.choices(
                                    rename.test):
        write(f"REFUSED: '{rename.fresh_choice}' already stands among the choices of '{rename.test}'")
        return E_ExitCode.REFUSED

    write(f"TO FOLLOW THE NEW NAME, in '{rename.source.directory}':")
    pair_tuple = rename.move_tuple()
    register_desc = "id, the coverage seats" if rename.across_f else "name"
    write(f"  {rename.text()} -- {len(pair_tuple)} file(s), the book entry, the register {register_desc}")
    for source_path, target_path in pair_tuple:
        write(f"      {_shown(rename.source, source_path)} -> {_shown(rename.source, target_path)}")
    if not pair_tuple:
        write("  (no recorded artefact stands; the book and the "
              "register are still asked)")
    if warning_f:
        for note in note_list: write(note)

    if not yes_f:
        write("")
        write("Proceed? [y/N] ")
        answer = (read_line() or "").strip().lower()
        if answer not in ("y", "yes"):
            write("NOTE: nothing was renamed")
            return E_ExitCode.OK

    write(f"{rename.text()}:")
    return E_ExitCode.OK if rename.follow() else E_ExitCode.FAULT


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from ._exit import guarded
    sys.exit(guarded("hwut.rename", main))
