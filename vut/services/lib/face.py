"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE FACE CONTRACT (services E-101) -- what a face is asked, what
         it answers, and how it refuses, as DATA.

DESCRIPTION
       A face has three parts, in this order of dependency:

           Request    a frozen record of what was asked -- no argv, no
                      strings left to parse
           do()       Request -> Result; raises Refused or Empty; it
                      NEVER prints, never reads stdin, never exits
           Result     a frozen record of what happened -- the data a
                      printer needs, and nothing pre-formatted

       'main(argv, write)' stays what it was: it reads the line into a
       Request, calls 'do', and hands the Result to the face's printer,
       which keeps its sentences. THE RECORDED PAGES DO NOT MOVE -- that
       is the proof of every step: the same page, out of a record.

       WHY. The answer used to exist for one instant inside 'main' and
       was spent on printing; nobody else could have it. Named, it is
       reusable: a Python caller, a test, a server, a GUI call 'do'. And
       'Request'/'Result' ARE the interface -- one definition a REST
       layer, a schema and (if wanted) the command line can be derived
       from.

       PLAIN FIELDS ONLY. A record holds str, int, float, bool, None,
       tuples of those, and other records. NO engine object, no Path, no
       enum instance, no Wish: what a caller needs is copied out. That
       one rule is what keeps a later server thin and 'do' honest about
       what it promises -- 'record_check' asserts it, and every face's
       suite asks it once.

       REFUSAL IS AN OUTCOME, NOT A PRINTOUT. 'Refused' carries the
       sentence the face has always printed and the exit code it has
       always returned; 'Empty' says the wish selected nothing. A caller
       that is not a command line catches them; 'main' prints them.
______________________________________________________________________________
"""
from dataclasses import fields, is_dataclass

from vut.services._exit import E_ExitCode

PLAIN_TYPE_TUPLE = (str, int, float, bool, type(None))


class FaceError(Exception):
    """What a face answers instead of a Result."""

    def __init__(self, said, code):
        """RETURN: FaceError, 'said' the sentence a printer writes,
                   'code' the exit status it becomes."""
        super().__init__(said)
        self.said, self.code = said, code


class Refused(FaceError):
    """The request cannot be honoured, and why -- the face's own words."""

    def __init__(self, said, code=E_ExitCode.REFUSED):
        super().__init__(said, code)


class Empty(FaceError):
    """The request is good and selects nothing."""

    def __init__(self, said=""):
        super().__init__(said, E_ExitCode.EMPTY)


class Fault(FaceError):
    """The request is good and the ground under it is not."""

    def __init__(self, said):
        super().__init__(said, E_ExitCode.FAULT)


def record_check(record, where=""):
    """
    RETURN: list[str], every field of 'record' that is not plain -- its
            path and what stands there. Empty where the record is plain
            through and through.

    A record is plain where every leaf is str, int, float, bool or None,
    and every branch a tuple, a frozenset or another record. A dict, a
    Path, an enum, a Wish, a Case: not plain, and named here.
    """
    result = []
    if not is_dataclass(record):
        return ["%s: not a record (%s)" % (where or "value",
                                           type(record).__name__)]
    for field in fields(record):
        value = getattr(record, field.name)
        result.extend(_leaf_check(value, "%s.%s" % (where or type(record).__name__,
                                                    field.name)))
    return result


def _leaf_check(value, where):
    """RETURN: list[str], what is not plain at or below 'value'."""
    if isinstance(value, PLAIN_TYPE_TUPLE):        return []
    if is_dataclass(value):                        return record_check(value, where)
    if isinstance(value, (tuple, frozenset)):
        result = []
        for i, each in enumerate(sorted(value, key=str)
                                 if isinstance(value, frozenset) else value):
            result.extend(_leaf_check(each, "%s[%i]" % (where, i)))
        return result
    return ["%s: %s" % (where, type(value).__name__)]


#  A STREAMING FACE (E-102). Where the product IS a sequence -- the
#  run's events, the report's directory blocks -- 'do' takes a SINK
#  beside the request and feeds it each item AS IT HAPPENS; what it
#  RETURNS is the tally, a record like any other. The command line's
#  sink is the display; a server's is a socket; a caller that wants
#  the whole sequence hands in a list's 'append'.
#
#  THE SINK IS NOT A PRINTER: it takes items, never lines. A face that
#  writes lines into a sink has not been cut, only moved.


def collected(do_f, request):
    """
    RETURN: (Result, list), what a streaming 'do_f' answers and every
            item it handed its sink -- the batch reading of a streaming
            face, for a caller that wants the whole before it acts.
    """
    item_list = []
    return do_f(request, item_list.append), item_list


def answered(do_f, request, write, printer, usage=""):
    """
    RETURN: E_ExitCode, the face's status: 'do_f(request)' handed to
            'printer(result, write)' where it answers, and the
            refusal's own sentence written where it raises.

    THE ONE PLACE a face turns an outcome into a page, so that every
    face refuses in one shape and no 'main' repeats it.
    """
    try:
        result = do_f(request)
    except FaceError as error:
        if error.said: write(error.said)
        if usage and isinstance(error, Refused): write(usage)
        return error.code
    return printer(result, write)
