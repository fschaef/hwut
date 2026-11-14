"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE EXIT STATUS LAW (E-1) -- one enum, every service face
         relates. What the shell, a Makefile and a CI step read as the
         whole verdict where nothing else is captured.

    OK        nothing refused, nothing failed
    FAULT     a fault was met, or a test failed; the face still
              printed what stands
    REFUSED   the command line cannot be READ: an unknown option, a
              malformed wish, a directory that does not exist --
              refused at the door, by name, with the usage line;
              or A CASE MAY NOT RUN: a cap in force for it cannot be
              enforced here and the root conf does not acknowledge it
              (E-135) -- whatever else passed
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


DEBUG_KEYWORD = "--debug-exception"


def _debug_wanted_f(argument_tuple):
    """
    RETURN: bool, True where the guard is to stand aside -- the keyword
            stood in the command line, or 'VUT_DEBUG_EXCEPTION' says so.

            The keyword is CONSUMED where it stood: it is the GUARD'S
            word, not any face's, so no face declares it and none sees
            it. That is why it works everywhere at once, and why a face
            that knows nothing of it cannot refuse it.
    """
    import os
    import sys

    found_f = False
    for word_list in (sys.argv,) + tuple(each for each in argument_tuple
                                         if isinstance(each, list)):
        while DEBUG_KEYWORD in word_list:
            word_list.remove(DEBUG_KEYWORD)
            found_f = True
    if found_f: return True
    return os.environ.get("VUT_DEBUG_EXCEPTION") not in (None, "", "0")


def unraisable_file_name():
    """
    RETURN: str, the file where the teardown's unraisables are recorded:
            'hwut-unraisable-<user>.txt' in the temporary directory --
            outside every tree, one per person, so no run leaves a
            file in a tree and no person writes over another's.
    """
    import getpass
    import os
    import tempfile
    try:
        user = getpass.getuser()
    except Exception:
        user = str(os.getuid()) if hasattr(os, "getuid") else "user"
    return os.path.join(tempfile.gettempdir(), "hwut-unraisable-%s.txt" % user)


def unraisable_to_file(name):
    """
    RETURN: None. 'sys.unraisablehook' set so that what Python cannot
            raise -- a '__del__' failing, mostly in the teardown -- is
            APPENDED to 'unraisable_file_name()' with its traceback, and
            the first one of this process says so on stderr in one line:

                NOTE: <name>: an object failed to close at exit => "<file>"

    THE TRACEBACK IS EVIDENCE, NOT TALK (E-225): it is kept, but not on
    the person's command line, after the face's last line, where nobody
    can act on it. Where the file cannot be written, the line says so
    instead of naming it. The hook itself never raises.
    """
    import os
    import sys
    import traceback

    said = {"f": False}

    def hook(unraisable):
        """RETURN: None. One unraisable recorded; the NOTE said once."""
        try:
            file_name = unraisable_file_name()
            message   = unraisable.err_msg or "Exception ignored in"
            text_list = ["=== %s (pid %d): %s: %r\n"
                         % (name, os.getpid(), message, unraisable.object)]
            if unraisable.exc_type is not None:
                text_list.extend(traceback.format_exception(
                    unraisable.exc_type, unraisable.exc_value,
                    unraisable.exc_traceback))
            try:
                with open(file_name, "a", encoding="utf-8") as fh:
                    fh.write("".join(text_list))
                where = '=> "%s"' % file_name
            except OSError as error:
                where = "(not recorded: %s)" % error.strerror
            if not said["f"]:
                said["f"] = True
                sys.stderr.write("NOTE: %s: an object failed to close at "
                                 "exit %s\n" % (name, where))
                sys.stderr.flush()
        except Exception:  # noqa: S110 -- a hook that raised would print the traceback it exists to keep off the line
            pass

    sys.unraisablehook = hook


def guarded(name, main_f, *argument_tuple, **argument_db):
    """
    RETURN: int, what 'main_f' returns -- or the ending's own code
            where a terminal signal or a hung-up reader stopped it:
            SIGINT (Ctrl-C), SIGTERM, SIGPIPE.

    ONE LINE ON STDERR AND NOTHING ELSE where an ending stops the
    face -- the interpreter's own teardown noise included: '<name> ended forcefully.'.
    On every other ending the teardown's unraisables go to a file, said
    in one NOTE line ('unraisable_to_file', E-225). SIGTERM is turned into the same
    ending as Ctrl-C by a handler installed for the face's duration
    and RESTORED after it -- a face never leaves a handler behind for
    whatever runs next in the process.
    """
    import os
    import signal
    import sys

    #  '--debug-exception' (or VUT_DEBUG_EXCEPTION=1) STANDS THE GUARD
    #  ASIDE. E-55 turns a terminal signal into one quiet line, which is
    #  right for a person ending a face on purpose and WRONG for anybody
    #  trying to find out where a face is stuck: the KeyboardInterrupt
    #  is swallowed here, so 'PYTHONFAULTHANDLER' never fires and a hang
    #  cannot be inspected at all. With this said, the signal and its
    #  traceback go through untouched.
    debug_f = _debug_wanted_f(argument_tuple)
    if debug_f:
        #  ARMED FOR A FATAL SIGNAL TOO, so that a face wedged in C code
        #  -- a terminal read, a lock -- names its line as well.
        __import__("faulthandler").enable()
        return main_f(*argument_tuple, **argument_db)

    #  EVERY ENDING, NOT ONLY A FORCED ONE (E-225): a face that ends
    #  well still tears down its loop, and a transport outliving it
    #  printed 'Exception ignored in: ...' under 'RESULTS'. Installed
    #  here and left in place: the teardown comes after 'guarded'.
    unraisable_to_file(name)

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
            #  A 'finally' must not raise over what it closes: restoring
            #  can fail only as 'signal.signal' fails -- ValueError, off
            #  the main thread -- and then nothing was installed either.
            try:                signal.signal(signal.SIGTERM, previous)
            except ValueError:  pass
