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
