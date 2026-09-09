"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE EXIT STATUS LAW (E-1) -- one enum, every service face
         relates. What the shell, a Makefile and a CI step read as the
         whole verdict where nothing else is captured.

    OK        nothing refused, nothing failed
    FAULT     a fault was met, or a test failed; the face still
              printed what stands
    REFUSED   the command line cannot be READ: an unknown option, a
              malformed wish, a directory that does not exist --
              refused at the door, by name, with the usage line
    EMPTY     the command line reads, and asks for NOTHING: a wish
              that selects no test, a directory holding no test
              application
    SIGPIPE   the unix convention 128+13: the reader hung up; the face
              went quiet instead of crashing
    SIGINT    the unix convention 128+2: the person pressed Ctrl-C
    SIGTERM   the unix convention 128+15: something asked the face to
              stop

A SIGNAL IS AN ENDING, NOT A CRASH (E-55). 'guarded()' wraps a face's
'main': a terminal signal leaves ONE LINE on stderr --

    hwut.run ended forcefully.

-- and the shell's own code. No traceback of any kind reaches the
person: what the interpreter would print is the face's INNARDS, and
the person did not ask to read them; they asked it to stop.

'IntEnum': 'sys.exit()' takes a member unchanged, and a standing
suite's 'status == 2' keeps holding while the faces migrate.
______________________________________________________________________________
"""
from enum import IntEnum


class E_ExitCode(IntEnum):
    OK      = 0
    FAULT   = 1
    REFUSED = 2
    EMPTY   = 3
    SIGPIPE = 141
    SIGINT  = 130
    SIGTERM = 143


def guarded(name, main_f, *argument_tuple, **argument_db):
    """
    RETURN: int, what 'main_f' returns -- or the ending's own code
            where a terminal signal or a hung-up reader stopped it:
            SIGINT (Ctrl-C), SIGTERM, SIGPIPE.

    ONE LINE ON STDERR AND NOTHING ELSE where an ending stops the
    face -- the interpreter's own teardown noise included: '<name> ended forcefully.'. SIGTERM is turned into the same
    ending as Ctrl-C by a handler installed for the face's duration
    and RESTORED after it -- a face never leaves a handler behind for
    whatever runs next in the process.
    """
    import os
    import signal
    import sys

    ending = {"code": E_ExitCode.SIGINT}

    def stop(signal_n, frame):
        """RETURN: never. The signal becomes the ending Ctrl-C is, and
        names itself: the shell reads 128 + the signal's own number."""
        ending["code"] = 128 + signal_n
        raise KeyboardInterrupt

    previous = None
    try:
        previous = signal.signal(signal.SIGTERM, stop)
    except (ValueError, OSError, AttributeError):
        pass                       # not the main thread, or no SIGTERM
    try:
        return main_f(*argument_tuple, **argument_db)
    except KeyboardInterrupt:
        sys.stderr.write("%s ended forcefully.\n" % name)
        #  AND NOTHING AFTER IT EITHER: a loop torn down mid-flight
        #  leaves objects whose '__del__' raises while the interpreter
        #  shuts down, and Python prints those as 'Exception ignored
        #  in: ...' with a traceback -- after this line, where nobody
        #  can act on them. The unraisable hook is silenced for the
        #  remainder of a process that is already ending.
        sys.unraisablehook = lambda unraisable: None
        return ending["code"]
    except BrokenPipeError:
        #  THE READER HUNG UP ('hwut.diff ... | head'): an ordinary
        #  ending. stdout is pointed at the void so the interpreter's
        #  own flush at exit cannot raise a second time.
        try:
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        except OSError:
            pass
        return E_ExitCode.SIGPIPE
    finally:
        if previous is not None:
            try:               signal.signal(signal.SIGTERM, previous)
            except Exception:  pass
