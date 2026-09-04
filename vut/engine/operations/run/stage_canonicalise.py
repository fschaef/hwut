"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       THE CANONICALISE STAGE -- the subject comes to exist.

DESCRIPTION
       One stage of provision (see provision/core.py): each raw stream
       rewritten by its declared pype, comparable after. A stream with
       no canonicaliser declared is comparable raw -- raw IS canonical
       for it.
______________________________________________________________________________
"""
import asyncio

from   ..result                   import E_TestRunResult
from   ...procsitter.api   import Procsitter, E_Containment
from   ...procsitter.api import Link, chain
from   ..nominal                  import BytesNominal
from   .core                      import Supply, read_all
from   .provider                  import I_CanonicaliseProvider
from   ..configuration            import caps_of


#  THE PYPE CALL IS FORMED HERE, and nowhere else (E-28). A stated
#  canonicaliser whose first word is a '.pype' script is run by THE
#  INTERPRETER -- this Python, 'hwut_pype.py' -- with the script as its
#  first argument. The script's she-bang line and execute bit are for
#  a shell and a person; inside the framework neither decides whether a
#  test's stream can be canonicalised. A first word that is not a
#  '.pype' script is a command of the author's own and runs as stated.
def pype_call(stated_argv):
    """
    RETURN: list[str], the argv the procsitter runs for a stated
            canonicaliser: '[python, hwut_pype.py, <script>, ...]'
            where the first word names a '.pype' script; the argv
            unchanged otherwise.
    """
    import sys
    from ....test_writing_support.hwut_pype import hwut_pype
    argv = list(stated_argv)
    if argv and argv[0].endswith(".pype"):
        return [sys.executable, hwut_pype.__file__] + argv
    return argv


async def canonicalise(text, pype_argv, procsitter):
    """
    RETURN: [0] str                the canonicalised text; the text
                                   UNCHANGED where the call failed
            [1] E_TestRunResult    the report of the call
            [2] ProcsitterResult   its attribution -- the record of the
                                   process that produced the result is
                                   part of that result, in every mode

    The canonicaliser is a supervised call like any other: its own caps,
    its own attribution -- and its call is 'pype_call''s, so a '.pype'
    script runs by the interpreter whatever its she-bang says. A canonicaliser that fails leaves the text
    UNCHANGED and says so -- it never silently returns half a stream,
    which would be compared and called a difference in the subject.
    """
    source = Link()
    await source.feed(text.encode("utf-8"))
    source.close()

    c      = chain([(procsitter, pype_call(pype_argv))],
                   stdin_reader=source.reader)
    record = (await asyncio.gather(*c.task_tuple))[0]
    result = await read_all(c.tail.reader)

    if record.containment is E_Containment.FAIL_LAUNCH:
        return text, E_TestRunResult.PYPE_INTERPRETER_NOT_FOUND, record
    if record.containment is E_Containment.FAIL_COMPLETED:
        return text, E_TestRunResult.PYPE_FAILED, record
    if record.containment is not E_Containment.OK_COMPLETED:
        return text, E_TestRunResult.PYPE_CONTAINED, record
    return result, E_TestRunResult.OK, record


class StageCanonicalise(I_CanonicaliseProvider):
    """THE SUBJECT comes to exist: each raw stream rewritten by its
    declared pype, comparable after. A stream with no canonicaliser
    declared is comparable raw -- raw IS canonical for it.

    Reads the canonicaliser and caps keys of the configuration.
    """

    def __init__(self, configuration, choice_name=None):
        self.configuration = configuration
        self.choice_name   = choice_name

    async def supply(self, raw_db, stop_event=None):
        """
        RETURN: Supply, product = readers by subject name; report = the
                FIRST canonicaliser failure, or OK; record_list = the
                attribution of every canonicaliser call it made. This
                stage answers
                for ITSELF only -- which reason speaks among the
                stages' is the orchestrator's merge, not a stage's
                knowledge of its upstream.

        A FAILING CANONICALISER ENDS PROVISION: 'product' is None,
        and the stages beyond never run -- the one rule this shape
        already has.

        IT MUST. A canonicaliser exists because the raw stream is not
        comparable -- a timestamp, a pid, an address that differs
        every run. Delivering the RAW text when the filter did not run
        does not deliver 'almost the subject'; it delivers a stream
        NOBODY EVER MEANT TO COMPARE, and the comparison that follows
        answers a question nobody asked. Where the nominal happens to
        have been blessed from an equally unfiltered run, THE TEST
        PASSES FOR THE WRONG REASON and nothing says so.

        THE PYPE IS PART OF THE TEST APPLICATION and may contain
        errors (adm/WORK/gathered/06-todo-2-pype-is-part-of-the-oracle.txt):
        a missing shebang, a
        syntax error, a file that is not there. Each is a defect in
        the TEST, and a defect in a test is a result -- stated, not
        swallowed.
        """
        configuration = self.configuration
        #  THE CASE'S CAPS (O-20): a pype is the choice's filter and
        #  runs under the choice's cap, as its application does.
        procsitter = Procsitter(caps_of(configuration, self.choice_name),
                                work_dir=str(configuration.test_directory))
        reader_db   = {}
        report      = E_TestRunResult.OK
        record_list = []
        entry     = configuration.choice_configuration(self.choice_name)
        for name, text in raw_db.items():
            pype_argv = entry.canonicalisers.get(name)
            if pype_argv is not None:
                text, pype_report, record = await canonicalise(
                                                text, pype_argv, procsitter)
                record_list.append(record)
                if pype_report is not E_TestRunResult.OK:
                    #  NO PRODUCT: provision ends here, and the test
                    #  is aborted with this stage's token. The stages
                    #  beyond never run, and no comparison is made
                    #  against a stream the filter never touched.
                    return Supply(product=None, report=pype_report,
                                  record_list=tuple(record_list))
            reader_db[name] = BytesNominal(text, name=name)
        return Supply(product=reader_db, report=report,
                      record_list=tuple(record_list))
