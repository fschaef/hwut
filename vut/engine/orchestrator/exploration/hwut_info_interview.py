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


#  Caps field -> ProcsitterConfig field. A cap absent from this table
#  is one procsitter does not enforce, and an unconfined question is
#  not asked (R-48).
_CAPS_FIELD_DB = {
    "timeout_sec":         "max_wall_clock_sec",
    "cpu_sec":             "max_cpu_time_sec",
    "memory_mb":           "max_memory_mb",
    "file_size_mb":        "max_file_size_mb",
    "child_process_max_n": "max_pids",
}


def _config_of(caps):
    """
    RETURN: ProcsitterConfig carrying every cap STATED that procsitter
            enforces, folded onto procsitter's own defaults.
            None, where a stated cap cannot be enforced -- the
            interview is then refused (R-48), never asked unconfined.

    'network' is stated False by INTERVIEW_CAPS and is not in the
    field table: procsitter confines the call, and network denial is
    the environment's, not a resource limit. It is therefore READ AND
    ACCEPTED here rather than refused -- a question that may not
    spend is the cap that matters, and refusing every interview over
    a flag procsitter never claimed would refuse them all.
    """
    from ...procsitter.procsitter import ProcsitterConfig

    import dataclasses

    value_db = {}
    for field in dataclasses.fields(caps):
        standing = getattr(caps, field.name, None)
        if standing is None:                     continue
        if field.name == "network":              continue
        if field.name not in _CAPS_FIELD_DB:     return None
        value_db[_CAPS_FIELD_DB[field.name]] = standing
    return ProcsitterConfig(**value_db)


def _procsitter_runner(path, caps):
    """
    RETURN: str, what the application wrote when asked '--hwut-info'.
            None, it did not answer, or exited non-zero, or was capped.

    The call runs under procsitter, which enforces 'caps'. A cap
    procsitter cannot enforce refuses the interview (R-48): an
    unconfined question is not asked.

    EVERY WAY OF FAILING YIELDS None, which is NO FAULT (R-2): a file
    that is not a test application is not an error, and exploration
    must not die of asking. That includes the file not being
    executable, the interpreter being absent, and the call hanging
    until the cap bites.
    """
    import asyncio

    from ...procsitter.construction import chain, Link
    from ...procsitter.procsitter   import Procsitter, E_Containment

    config = _config_of(caps)
    if config is None: return None

    async def _ask():
        """RETURN: str, the answer; None, there was none."""
        source = Link()
        source.close()
        #  THE WORK DIRECTORY IS THE APPLICATION'S OWN: an hwut 1.0
        #  application answers '--hwut-info' from where it lies, as it
        #  always has.
        c      = chain([(Procsitter(config, os.path.dirname(path) or "."),
                         [path, "--hwut-info"])],
                       stdin_reader=source.reader)
        record = (await asyncio.gather(*c.task_tuple))[0]
        chunk_list = []
        while not c.tail.reader.at_eof():
            data = await c.tail.reader.read(4096)
            if data: chunk_list.append(data)
        if record.containment is not E_Containment.OK_COMPLETED:
            return None
        if getattr(record, "exit_code", 0) not in (0, None):
            return None
        return b"".join(chunk_list).decode("utf-8", "replace")

    try:
        return asyncio.run(_ask())
    except Exception:
        #  A file that cannot even be launched is not a test
        #  application. Silence is not a fault.
        return None
