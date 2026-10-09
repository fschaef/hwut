"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       THE TELL SERVICE -- 'hwut.report.details': ONE test, packed whole.

DESCRIPTION
       Everything a conversation about one test needs, in one dump on
       stdout: the METADATA, the SOURCE of the test application, the
       accepted GOOD, the produced OUT -- and the CADENCE, when the
       store recorded it. Made for handing a test to another pair of
       eyes, human or AI, without them asking for file after file.

           hwut.report.details [<wish>] [TEST-APP [CHOICE]]
                                                the pack of every case
                                                the wish selects (E-52);
                                                when a cadence
                                                sidecar exists, each
                                                line of its stream is
                                                prefixed '<delta-t>:'
           hwut.report.details TEST-APP [CHOICE] -r     the files VERBATIM
                                                ('--raw'): no cadence
                                                prefixes, raw sidecars
                                                and timing sections
                                                included
           hwut.report.details TEST-APP [CHOICE] --cov-dir <directory>
                                                READ COVERAGE from that
                                                output directory of
                                                'hwut.cov.run' (coverage
                                                D-42). Without it the
                                                nearest 'hwut.coverage/'
                                                from the test directory
                                                upward is read; where
                                                none stands, no coverage
                                                is shown
           hwut.report.details TEST-APP [CHOICE] --no-coverage
                                                LEAVE OUT the coverage
                                                section. It stands BY
                                                DEFAULT where a coverage
                                                directory names the
                                                test run: a report
                                                says WHAT broke, and
                                                coverage says WHICH
                                                LINES the run actually
                                                executed -- together
                                                they narrow a search
                                                from a repository to a
                                                few hundred lines
                                                (coverage D-24)

       THE BOOKKEEPER OWNS THE NAMING. This face resolves NOTHING by
       hand: 'nominal_path', 'candidate_path', 'raw_path' and
       'timing_path' answer where every record of a key lives, and the
       key is (test, choice, subject) with 'test' the source file's
       STEM -- what RECORDING uses ('operations/session.py':
       configuration.stem). A second spelling of that law here would
       be a second law; there is one.

       Whatever exists is packed; what does not is SAID in the
       metadata -- absence reported, never guessed (the house law).

       THE HEAD IS A FORMAL INPUT. It names WHERE the test stands --
       the directory relative to 'hwut-root.conf', the one ground
       every reader shares -- WHAT ran, and BOTH readings, which are
       two questions and get two fields:

           verdict:        what the COMPARISON found, or that none
                           could be made
           status report:  what the RECORDS say -- which of OUT and
                           GOOD stand

       ONE FIELD ANSWERING BOTH is how a test that never ran comes to
       be read as a test that failed. A missing provision is a RESULT,
       and it is stated as one.

       MACHINE-FREE: relative names and byte counts only -- no absolute
       paths, no dates -- so a pack can be compared, stored, or pasted
       without freezing one machine into it.

       THE WORDS ARE EVERY STORE-READING FACE'S ('services/_cases.py'):
       a test, a test and a choice, a path that enters its directory
       (E-47), '--glob', '--label', '--fail', '--directory' for one
       directory, the tree below the cwd otherwise. Several cases:
       several packs, one after the other, walk order.

       Rendering goes to STDOUT; exit 0 with a pack, 3 where nothing is
       selected, 2 on an unusable request.
______________________________________________________________________________
"""
import io
import os
import sys
import json
import argparse
from pathlib import Path


#  THE IMPORT CALL -- see 'services/_config.py': it does the walk-up;
#  the face adopts its package (PEP 366). Dead under '-m', which is
#  how the launcher runs it. A DOTTED FACE LIVES TWO LEVELS DOWN
#  ('services/lib/report/'), so the package it adopts says so.
if __package__ in (None, ""):
    import _config
    __package__ = _config.PACKAGE + ".lib.report"
from ..._exit import E_ExitCode  # delayed past _config adoption


def bookkeeper_of(directory):
    """
    RETURN: Bookkeeper, the one that owns naming in that directory.

    Imported here, not at module scope: the face runs by path as well
    as by module, and the import must follow the '_config' adoption.
    """
    from vut.engine.bookkeeper.api import Bookkeeper
    #  TOLD WHICH TESTS SHARE A NOMINAL (bookkeeper B-30), from the
    #  directory's own applications; untold where it cannot be read.
    try:
        from vut.engine.orchestrator.exploration import selection
        from vut.engine.orchestrator.exploration.explorer import explore
        from vut.engine.orchestrator.exploration.tree_explorer import \
                                                             ascended_spec
        inherited, _ = ascended_spec(directory)
        return Bookkeeper(directory, selection.naming_of(
                   explore(directory, inherited=inherited).app_set))
    except Exception:                                      # noqa: BLE001
        return Bookkeeper(directory)


def subject_tuple_of(bookkeeper, test, choice):
    """
    RETURN: tuple, the subjects recorded for that key, sorted -- the
            names under the candidate's stem with the sidecars
            ('.raw', '.times', '.when') left out; empty where the run
            recorded nothing.
    """
    from vut.engine.bookkeeper.api import SUBJECT_BY_SUFFIX_DB
    probe     = bookkeeper.candidate_path(test, choice, "s")
    base      = probe.parent
    stem      = probe.name[:-1]
    if not base.is_dir(): return ()
    name_list = []
    for path in base.iterdir():
        name = path.name
        if not name.startswith(stem):                          continue
        #  '.cover' is the coverage record, BINARY (coverage D-20): it
        #  is not a subject, and its presentation is the COVERAGE
        #  section. Packing the bytes would put a blob in a pack meant
        #  to be read.
        if name.endswith((".raw", ".times", ".when", ".cover")): continue
        #  THE FILE WEARS A SUFFIX; THE SUBJECT HAS A NAME. 'x--c.txt'
        #  is the STDOUT subject, not a 'txt' one -- the bookkeeper
        #  holds the table, and it is read here in reverse.
        suffix = name[len(stem):]
        name_list.append(SUBJECT_BY_SUFFIX_DB.get(suffix, suffix))
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
    test       = os.path.basename(application)
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

    #  THE ERROR WITNESS. 'OUT/' witnesses the LAST RUN, and where that
    #  run wrote to stderr it left '<key>.err' there -- cleared before
    #  every execution, written only on occurrence, so its PRESENCE is
    #  the statement. Never a subject (E-5): not compared, not a
    #  nominal, not named in 'output'. Asked for by name, because
    #  nothing discovers it.
    take("err", bookkeeper.error_witness_path(os.path.splitext(test)[0],
                                              choice))
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


def coverage_directory_of(directory, stated=None):
    """
    RETURN: str, the coverage output directory this report reads
            (coverage D-42): the one 'stated' ('--cov-dir'); else the
            nearest 'hwut.coverage/' found from 'directory' upward.
            None, where none is stated and none is found.
    """
    from vut.engine.coverage.api import DEFAULT_DIRECTORY_NAME
    if stated: return os.path.abspath(stated)
    here = os.path.abspath(directory)
    while True:
        candidate = os.path.join(here, DEFAULT_DIRECTORY_NAME)
        if os.path.isdir(candidate): return candidate
        above = os.path.dirname(here)
        if above == here: return None
        here = above


def coverage_section_text(directory, application, choice, cov_dir=None):
    """
    RETURN: str, the coverage of that test run, read from the coverage
            output directory (coverage D-42): its test run id, then per
            source file it reached what it did NOT execute -- what a
            failing run did not reach is what a reader is looking for
            -- and what it executed.
            None, where no coverage directory is stated or found, or
            the one found names no such test run: absence is not
            reported as an empty measurement.

    'cov_dir' is '--cov-dir'; None searches 'hwut.coverage/' from the
    test directory upward.
    """
    from vut.engine.coverage.api import Output, OutputRefused, root_of

    output_directory = coverage_directory_of(directory, cov_dir)
    if output_directory is None: return None
    root = root_of(output_directory)
    if root is None: return None
    relative = os.path.relpath(os.path.abspath(directory), root) \
                 .replace(os.sep, "/")
    try:
        output = Output(output_directory)
        found  = output.of_run(relative, application, choice)
    except OutputRefused as refusal:
        return "test run: <unread>\n%s" % refusal
    if found is None: return None

    def spans(range_tuple):
        """RETURN: str, the ranges as 'first..last', ',' between."""
        return ", ".join("%i..%i" % (b, e - 1) if e - b > 1 else "%i" % b
                         for b, e in range_tuple) or "-"

    run_id    = output.run_db[(relative, application, choice or None)]
    line_list = ["test run: %s" % run_id, ""]
    if not found:
        line_list.append("this run executed no line of any gathered "
                         "source")
        return "\n".join(line_list)
    line_list.append("NOT EXECUTED by this run:")
    for source, _, not_executed in found:
        line_list.append("  %-44s %s" % (source, spans(not_executed)))
    line_list.append("")
    line_list.append("EXECUTED by this run:")
    for source, reached, _ in found:
        line_list.append("  %-44s %s" % (source, spans(reached)))
    return "\n".join(line_list)


def _subject_db(record_db, prefix):
    """
    RETURN: dict, SUBJECT NAME -> relative path, for every record of
            this kind that is a stream in its own right -- the raw
            sidecars and the timing sections are not, AND STDERR IS
            NOT (E-5: never a nominal, never compared). stderr is
            SHOWN by 'find_records' and must not reach the verdict or
            the status line, which speak about SUBJECTS.

    The section names read '<kind> <subject>', so the subject is what
    stands after the kind: 'good stdout' -> 'stdout'.
    """
    return {key[len(prefix):]: path
            for key, path in record_db.items()
            if key.startswith(prefix)
            and " raw " not in key and " timing " not in key
            and key != "err"}


def _both_text(good_db, out_db):
    """
    RETURN: str, which subjects stand on both sides and which on one
            -- a pack states what it has, and a subject recorded but
            never accepted is a fact a bug hunter wants at the head,
            not left to be inferred from the file list.
    """
    shared = sorted(set(good_db) & set(out_db))
    lonely = sorted(set(good_db) ^ set(out_db))
    text   = ", ".join(shared) if shared else "no shared subject"
    if lonely: text += "; one side only: %s" % ", ".join(lonely)
    return text


def _place(directory):
    """
    RETURN: str, where this test stands, RELATIVE TO THE TREE'S
            BOUNDARY -- the directory holding 'hwut-root.conf', which
            is the one place every reader of a pack shares. '.' where
            the test sits at the boundary itself.
            "<no 'hwut-root.conf' above>" where the directory stands
            in no tree: said, never guessed at, and never an absolute
            path -- a pack is MACHINE-FREE.
    """
    import os.path as _p
    from vut.engine.orchestrator.exploration.tree_explorer \
        import RootConfMissing, root_conf_directory
    try:
        boundary = root_conf_directory(directory)
    except RootConfMissing:
        return "<no 'hwut-root.conf' above>"
    relative = _p.relpath(_p.abspath(directory), boundary)
    return relative.replace(os.sep, "/")


def refresh(directory, application, choice):
    """
    RETURN: str, one line for the pack's header saying what provision
            did before the pack was read -- 'ran: (A.1) ...' where the
            recording was stale and the test was run, 'current: (A.2)
            ...' where it stood; None where the channel could not be
            asked (no tree, no such test), and the pack shows what
            stands, as it always did.

    THROUGH THE ONE CHANNEL (operations disc-2, E-40): a face that
    OBTAINS A SUBJECT AND DOES SOMETHING WITH IT holds a CURRENT one.
    'tell' presents; so it REFRESHES -- 'provider_of(refresh=True)':
    PROVIDE where the recording is older than what it was recorded
    from, RECORDED where it is not. Where it must run, it runs through
    the session, held, recorded and booked as 'hwut.run' books it.
    """
    from vut.engine.orchestrator.exploration            import selection
    from vut.engine.orchestrator.exploration.task_list   import SelectionError
    from vut.engine.orchestrator.plan.wish              import (parse_wish,
                                                                with_targets,
                                                                WishError)
    from vut.engine.operations                          import subject_provision
    from vut.engine.operations.session                  import run_test, Request
    from vut.engine.orchestrator.run.adapter            import test_configuration_of
    from vut.engine.bookkeeper.api                      import Store
    from vut.auxiliary.directory_mutex                  import DirectoryBusy
    import asyncio
    try:
        wish, _ = parse_wish([])
        wish    = with_targets(wish, [application] if choice is None
                                     else [application, choice])
        found   = selection.of_directory(directory, wish, None, base_f=True)
    except (SelectionError, WishError, OSError):
        return None
    result     = found.result_db.get(".")
    bookkeeper = found.bookkeeper_db.get(".")
    if result is None or bookkeeper is None: return None
    if application not in result.app_set.app_db: return None
    store          = Store(bookkeeper)
    language_setup = result.app_set.directory_spec.language_setup
    configuration  = test_configuration_of(result.app_set.app_db[application],
                                           directory,
                                           language_setup=language_setup)
    said = []
    for entry in found.case_list:
        case = entry.case
        if case.source_file != application: continue
        if choice is not None and case.choice != choice: continue
        _, decision = subject_provision.provider_of(configuration, store,
                                                    case.choice, refresh=True)
        #  A PACK IS MACHINE-FREE: the decision names the file it
        #  compared by its anchored path; the pack says it relative
        #  to the test directory.
        because = decision.because.replace(
                      os.path.abspath(directory) + os.sep, "")
        word = decision.what
        #  AN UNENFORCEABLE CAP REFUSES THE RUN (exploration R-80).
        from vut.engine.orchestrator.plan import confinement
        reason = confinement.refusal_of(result.app_set, application,
                                        case.choice)
        if word is subject_provision.E_Decision.PROVIDE \
           and reason is not None:
            said.append("not run -- %s" % reason.split(" => ")[0])
        elif word is subject_provision.E_Decision.PROVIDE:
            try:
                asyncio.run(run_test(configuration,
                                     Request(choice=case.choice, record=True),
                                     bookkeeper=bookkeeper))
                said.append("ran %s" % because)
            except DirectoryBusy as error:
                said.append("could not run -- %s" % error)
        else:
            said.append("current %s" % because)
    return "; ".join(said) if said else None


def build_pack(directory, application, choice, raw_f,
               coverage_f=True, provision_line=None, cov_dir=None):
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
    #  THE HEAD NAMES THE PLACE, THE SUBJECT AND BOTH READINGS. A pack
    #  is a FORMAL INPUT: a bug hunter reading it must be able to say
    #  WHERE this ran, WHAT ran, and -- separately -- what the
    #  comparison found and what the records say. The two are not one
    #  question, and one field answering both is how a test that never
    #  ran gets read as a test that failed.
    good_db = _subject_db(record_db, "good ")
    out_db  = _subject_db(record_db, "out ")

    #  THE VERDICT is what a COMPARISON found -- and a comparison is
    #  BETWEEN ONE SUBJECT AND ITS OWN NOMINAL. Pairing whichever
    #  'out' key came first against whichever 'good' key came first
    #  compares stderr against stdout and calls two identical streams
    #  different. Where no subject stands on both sides, no comparison
    #  was possible, and the verdict says so rather than borrowing the
    #  status report's words.
    shared_tuple = tuple(sorted(set(good_db) & set(out_db)))
    if not shared_tuple:
        verdict = "none -- no comparison was possible"
    else:
        differing = tuple(name for name in shared_tuple
                          if read(good_db[name]) != read(out_db[name]))
        if not differing:
            verdict = "OUT == GOOD (byte-identical): %s" \
                      % ", ".join(shared_tuple)
        else:
            verdict = "OUT differs from GOOD: %s" % ", ".join(differing)

    #  THE STATUS REPORT is what the RECORDS say: which streams stand.
    #  A missing provision is a RESULT, stated as one.
    if good_db and out_db:
        status = "run and accepted -- both records stand (%s)" \
                 % _both_text(good_db, out_db)
    elif out_db:
        status = "never accepted -- the OUT stands, no GOOD (%s)" \
                 % ", ".join(sorted(out_db))
    elif good_db:
        status = "not run here -- the GOOD stands, no OUT (%s)" \
                 % ", ".join(sorted(good_db))
    else:
        status = "nothing recorded -- neither OUT nor GOOD"

    line_list = ["==[ HWUT TEST REPORT ]%s" % ("=" * 56),
                 "directory:     %s" % _place(directory),
                 "test:          %s" % application,
                 "choice:        %s"
                 % (choice if choice is not None else "<none>"),
                 "verdict:       %s" % verdict,
                 "status report: %s" % status]
    if provision_line is not None:
        line_list.append("provision:     %s" % provision_line)
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
    coverage_text = coverage_section_text(directory, application, choice,
                                          cov_dir) \
                    if coverage_f else None
    line_list.append("coverage: %s"
                     % ("left out ('--no-coverage')" if not coverage_f
                        else coverage_text.splitlines()[0].replace(": ", " ", 1)
                             if coverage_text else "none recorded"))
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

    if coverage_text is not None:
        section("COVERAGE", coverage_text)

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
        #  THE ERROR WITNESS CARRIES NO PATH IN ITS TITLE, as COVERAGE
        #  does not: the file listing above states every path once, and
        #  once is where a path belongs.
        section("ERR" if key == "err"
                else "%s: %s" % (key.upper(), relative_path), text)

    return "\n".join(line_list) + "\n"


def main(argv=None):
    """
    RETURN: int, the exit code -- 0 a pack was written; 141 the reader
            left early; 2 unusable request.

    The pack goes to stdout ('hwut.report.details x.py c > pack.txt' or straight
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
    RETURN: int, the exit code -- 'main' without the pipe guard: OK
            with at least one pack, EMPTY where the wish selects no
            case, REFUSED where the words cannot be read.

    THE WISH (E-52): the words are every store-reading face's --
    'hwut.report.details demo.py basic', 'hwut.report.details a/TEST/demo.py' (entered,
    E-47), '--glob', '--label', '--fail', '--directory' -- and every
    selected case is packed in turn, walk order, each pack whole.
    """
    from vut.engine.orchestrator.plan.wish import parse_wish, WishError
    from ..._cases                        import select
    if argv is None: argv = sys.argv[1:]
    err = lambda t: sys.stderr.write(t + "\n")
    try:
        wish, rest_list = parse_wish(list(argv))
    except WishError as error:
        err("REFUSED: %s" % error)
        return E_ExitCode.REFUSED
    parser = argparse.ArgumentParser(
        prog="hwut.report.details",
        description="Pack a test whole -- metadata, source, GOOD, OUT "
                    "and cadence -- for handing to another pair of "
                    "eyes, human or AI. Every case the wish selects, "
                    "one pack each.")
    parser.add_argument("word", nargs="*",
                        help="a test application, a test and a choice, "
                             "any wish word; a path enters its directory")
    parser.add_argument("--directory", default=None,
                        help="ONE test directory (default: the tree "
                             "below the cwd)")
    parser.add_argument("-r", "--raw", action="store_true",
                        help="files verbatim: no cadence prefixes, raw "
                             "sidecars and timing sections included")
    parser.add_argument("--no-coverage", action="store_true",
                        help="leave out the coverage section; it stands "
                             "by default where a coverage directory "
                             "names the test run")
    parser.add_argument("--cov-dir", default=None, metavar="directory",
                        help="the coverage output directory of "
                             "'hwut.cov.run' (default: the nearest "
                             "'hwut.coverage/' from the test directory "
                             "upward)")
    if "--help" in argv or "-h" in argv:
        from vut.services._core import man_page
        print(man_page(parser.prog, parser.format_help(), usage=USAGE))
        return E_ExitCode.OK
    arguments = parser.parse_args(rest_list)

    selected, code = select(wish, arguments.word,
                            arguments.directory or ".",
                            arguments.directory is not None, err, USAGE)
    if selected is None: return code
    if not selected.where_list:
        err("EMPTY: the wish selects no case")
        return E_ExitCode.EMPTY
    for where in selected.where_list:
        whole = selected.whole(where)
        for case in selected.case_db[where]:
            application = case.source_file
            provision_line = refresh(whole, application, case.choice)
            sys.stdout.write(build_pack(whole, application, case.choice,
                                        arguments.raw,
                                        not arguments.no_coverage,
                                        provision_line=provision_line,
                                        cov_dir=arguments.cov_dir))
    return E_ExitCode.OK


USAGE = ("usage: hwut.report.details [<wish>] [<test> [<choice>]] [--directory=<path>] "
         "[-r|--raw] [--no-coverage] [--cov-dir <directory>]")


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from ..._exit import guarded
    sys.exit(guarded("hwut.report.details", main))
