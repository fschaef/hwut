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

from .configuration_tree import (TestParameters, TestAppSpec, Caps, E_Origin,
                                 Tolerance)
from .fault         import Position

#  Caps of the interview itself. An interview is a question, not a test:
#  it may not spend, and it may not reach.
INTERVIEW_CAPS = Caps(timeout_sec         = 10.0,
                      network             = False,
                      child_process_max_n = 1)


#  THE MEMO (X-INTERVIEW): an interview is a program run, MEASURED at
#  half a second each for helpers that answer nothing -- eight seconds
#  of silence before the first line of every 'hwut.run'. Its answer is
#  remembered beside the tests, keyed by the file's mtime and size; the
#  file is asked again only once it changed. DELETABLE, so it lands
#  under 'TMP/' with every other transient (ruled: 'any deletable lands
#  in TMP'); the traces stay beside the tests because they TRAVEL.
MEMO_FILE_NAME = "hwut-interview.dat"
MEMO_DIRECTORY = "TMP"


def interview(directory, name, runner=None):
    """
    RETURN: TestAppSpec, the configuration the test application states
            through '--hwut-info', with origin 'E_Origin.INTERVIEW'.
            None, the file is not a test application -- it did not answer,
            answered unreadably, exited non-zero, or was capped.

    'runner' calls the application and returns its answer; the default
    runs it under procsitter. It is a parameter so that the reading of a
    block can be exercised without a process. The default runner's
    answer is MEMOISED per file (mtime, size); a custom runner is asked
    every time.
    """
    path = os.path.join(directory, name)
    if runner is None:
        stamp = _stamp(path)
        memo  = _memo_read(directory)
        if name in memo and memo[name][0] == stamp:
            text = memo[name][1]
        else:
            text = _procsitter_runner(path, INTERVIEW_CAPS)
            memo[name] = (stamp, text)
            _memo_write(directory, memo)
    else:
        text = runner(path, INTERVIEW_CAPS)
    if text is None: return None
    return specification_of(text, name)


def memo_path(directory):
    """RETURN: str, where the memo of 'directory' stands: 'TMP/hwut-
               interview.dat' below it."""
    return os.path.join(directory, MEMO_DIRECTORY, MEMO_FILE_NAME)


def _stamp(path):
    """RETURN: str, 'mtime:size' of the file; '' where it is gone."""
    try:    st = os.stat(path)
    except OSError: return ""
    return "%d:%d" % (int(st.st_mtime), st.st_size)


def _memo_read(directory):
    """RETURN: dict, name -> (stamp, answer text or None), from the
               memo file; empty where none stands or it cannot be read."""
    path = memo_path(directory)
    result = {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("#") or not line.strip(): continue
                name, stamp, answer = line.rstrip("\n").split("\t", 2)
                result[name] = (stamp, None if answer == "-"
                                       else answer.replace("\\n", "\n"))
    except (OSError, ValueError):
        return {}
    return result


def _memo_write(directory, memo):
    """RETURN: None. The memo written whole; a failure to write is no
               fault -- the next walk asks again."""
    path = memo_path(directory)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("#  hwut-interview.dat -- '--hwut-info' answers, by file\n")
            fh.write("#  mtime:size; '-' = not a test application. Deletable.\n")
            for name in sorted(memo):
                stamp, answer = memo[name]
                fh.write("%s\t%s\t%s\n" % (name, stamp, "-" if answer is None
                                              else answer.replace("\n", "\\n")))
    except OSError:
        pass


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

    #  'HAPPY:' NAMES AN EQUIVALENCE TOLERANCE, and every tolerance
    #  stands in the one scope (E-42).
    root = TestParameters(
        tolerance   = (Tolerance(eq_pattern=tuple(happy_list))
                       if happy_list else None),
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
    from ...procsitter.api import ProcsitterConfig

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

    from ...procsitter.api import chain, Link
    from ...procsitter.api   import Procsitter, E_Containment

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

    #  THE COROUTINE IS BUILT BEFORE THE TRY and CLOSED where the run
    #  never happens. The driving can refuse before it starts, and a
    #  coroutine dropped unawaited warns on stderr, which would put a
    #  machine-chosen path into whatever is capturing this.
    task = _ask()
    try:
        return _answer_of(task)
    except Exception:
        #  A file that cannot even be launched is not a test
        #  application. Silence is not a fault.
        task.close()
        return None


def _answer_of(coroutine):
    """
    RETURN: str, what the interview coroutine answered, run to
            completion in an event loop of its own.
            None, where it answered none.

    A LOOP MAY ALREADY BE RUNNING, and 'asyncio.run' refuses where one
    is. Exploration is reached from both sides: 'hwut.plan' determines
    synchronously, 'hwut.run' determines inside the orchestrator's own
    loop. Refused there, the interview answered 'None' and every
    application of the THIRD CARRIER (R-44) -- the hwut 1.0 ones, which
    answer '--hwut-info' rather than carry a header -- vanished from
    the run with no fault and no REFUSED line.

    A REFUSAL TO ASK IS NOT AN ANSWER. Where a loop runs, the coroutine
    is given a thread holding a loop of its own, and the question is put
    exactly as it is put anywhere else; where none runs, 'asyncio.run'
    serves as before.
    """
    import asyncio
    import concurrent.futures

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coroutine).result()
