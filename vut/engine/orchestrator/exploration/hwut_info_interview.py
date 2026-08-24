"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE THIRD CARRIER (R-44). A file that carries no 'hwut' trigger and
         stands under no 'apps' entry may still be an hwut 1.0 test
         application. It is INTERVIEWED:

             app --hwut-info

and its answer is read as a specification.

THE BLOCK, as 'HwutRunner' emits it:

    <title>;
    CHOICES: <name>, <name>, ...;         (absent for a choice-less app)
    HAPPY: <pattern>;                     (zero or more)
    SAME;                                 (if same_f)
    INTERACTIVE;                          (always, for a HwutRunner front end)

Only these lines are looked for. A line beyond them is passed over in
silence: this is a migration path, and an old application owes us nothing.

The interview RUNS A PROGRAM. It runs under procsitter, with caps: an old
application that hangs must not hang exploration. Every way of failing to be
a test application -- no answer, unreadable answer, non-zero exit, timeout --
yields 'None', which is not a fault (R-2).
______________________________________________________________________________
"""
import os

from .configuration_tree import (TestParameters, TestAppSpec, Caps, E_Origin)
from .fault         import Position

#  Caps of the interview itself. An interview is a question, not a test:
#  it may not spend, and it may not reach.
INTERVIEW_CAPS = Caps(timeout_sec         = 10.0,
                      network             = False,
                      child_process_max_n = 1)


def interview(directory, name, runner=None):
    """
    RETURN: TestAppSpec, the configuration the test application states
            through '--hwut-info', with origin 'E_Origin.INTERVIEW'.
            None, the file is not a test application -- it did not answer,
            answered unreadably, exited non-zero, or was capped.

    'runner' calls the application and returns its answer; the default
    runs it under procsitter. It is a parameter so that the reading of a
    block can be exercised without a process.
    """
    if runner is None: runner = _procsitter_runner
    text = runner(os.path.join(directory, name), INTERVIEW_CAPS)
    if text is None: return None
    return specification_of(text, name)


def specification_of(text, name):
    """
    RETURN: TestAppSpec, what the info block states.
            None, the text is no info block -- it carries no title line.

    The title is the FIRST line, ending in a semicolon, that is none of
    the keyword lines. A block without one is not an answer we can read.
    """
    title       = None
    choice_list = None
    happy_list  = []
    same_f      = False
    interactive_f = False

    for line in text.splitlines():
        line = line.strip()
        if not line:                    continue
        body = line[:-1].strip() if line.endswith(";") else line

        if   line == "SAME;":           same_f        = True
        elif line == "INTERACTIVE;":    interactive_f = True
        elif body.startswith("CHOICES:"):
            choice_list = [word.strip()
                           for word in body[len("CHOICES:"):].split(",")
                           if word.strip()]
        elif body.startswith("HAPPY:"):
            happy_list.append(body[len("HAPPY:"):].strip())
        elif title is None and line.endswith(";"):
            title = body

    if title is None: return None

    root = TestParameters(
        eq_pattern  = tuple(happy_list) if happy_list else None,
        same        = True if same_f        else None,
        interactive = True if interactive_f else None)

    if choice_list:
        choice_db = {choice: TestParameters() for choice in choice_list}
    else:
        choice_db = {None: TestParameters()}

    return TestAppSpec(source_file     = name,
                       title           = title,
                       language        = None,
                       root_parameters = root,
                       choice_db       = choice_db,
                       origin          = E_Origin.INTERVIEW,
                       position        = Position(1, 1))


def _procsitter_runner(path, caps):
    """
    RETURN: str, what the application wrote when asked '--hwut-info'.
            None, it did not answer, or exited non-zero, or was capped.

    The call runs under procsitter, which enforces 'caps'. A cap
    procsitter cannot enforce refuses the interview (R-48): an
    unconfined question is not asked.
    """
    from ...procsitter import chain                      # noqa: F401  (lazy)

    raise NotImplementedError(
        "the interview's procsitter call is owed at integration; see "
        "DISCUSSIONS/todo-3-hwut-info-hints.txt")
