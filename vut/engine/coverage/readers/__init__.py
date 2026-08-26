"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE READERS -- one module per artifact FORMAT, and the table
         that says which tool speaks which.

DESCRIPTION
       IMPORTING THIS PACKAGE REGISTERS EVERY READER; that is its whole
       purpose, and 'reader.reader_of' imports it on its first miss so
       that a caller who elects no tool pays for none of them.

       A FORMAT, NOT A TOOL, IS WHAT A READER KNOWS. The LCOV tracefile
       is written by 'lcov', 'gcovr' and 'grcov' alike, so ONE
       reader stands for them all: the alias table below is how a tool
       name reaches the reader of the format it speaks. Admitting a
       fifth tool that speaks LCOV is one line here and nothing else.

           coverage             coverage.py json       python
           lcov                 lcov tracefile         lingua franca
           gcovr                -> lcov
           grcov                -> lcov
           llvm-cov             -> lcov
           cargo-llvm-cov       -> lcov
           verilator_coverage   -> lcov                verilog
           gcov                 gcov annotated source  c, c++, fortran,
                                                       ada, vhdl (ghdl)
           cobertura            cobertura xml          the SECOND lingua
                                                       franca: java, .NET,
                                                       python, php, ruby,
                                                       javascript
           go                   go cover profile       go -- BLOCKS, not
                                                       lines
           luacov               luacov report          lua
           jacoco               jacoco xml             java, kotlin,
                                                       scala, groovy
           kcov                 -> cobertura           bash; witnessed
           verilator            verilator native .dat  verilog: line,
                                                       branch arms,
                                                       toggle, cover
           ghdl                 ghdl psl-report json   vhdl 'cover'
                                                       directives
           simplecov            simplecov resultset    ruby's own
           ucis                 ucis xml (Accellera)   line, branch,
                                                       toggle; fsm,
                                                       assertion and
                                                       covergroup bins
                                                       are LINE-LESS BY
                                                       THE STANDARD'S
                                                       OWN DEFINITION
                                                       (disc-9(b))

       WHAT IS OWED (DISCUSSIONS todo-2), in the order it is worth
       building:

           julia-cov       annotated source, the gcov family with other
                           markers ('0' rather than '#####') -- possibly
                           one parameterised reader rather than two.

       A TOOL WITH NO READER IS STILL A CANDIDATE. 'trace', 'vcover'
       and the rest stand in the default table so that a machine
       refuses BY NAME -- 'no reader for X; this build reads ...' --
       rather than reporting no coverage at all.
______________________________________________________________________________
"""
from ..reader import register, CCoverageFramework, _FRAMEWORK_DB

from . import python_coverage      # noqa: F401
from . import lcov                 # noqa: F401
from . import gcov                 # noqa: F401
from . import cobertura            # noqa: F401
from . import go                   # noqa: F401
from . import luacov               # noqa: F401
from . import jacoco               # noqa: F401
from . import verilator            # noqa: F401
from . import ghdl_psl             # noqa: F401
from . import simplecov            # noqa: F401
from . import ucis                 # noqa: F401


#  TOOLS THAT SPEAK A FORMAT SOMEBODY ELSE'S READER ALREADY READS.
#  An alias is not a second reader: it is the SAME object under a second
#  name, so 'reader_of' answers one truth however the tool was spelled.
#  AN ALIAS CLAIMS THE FORMAT AND NOTHING ELSE. It says 'this tool
#  leaves a tracefile in OUT/COVERAGE'; it does NOT claim to know how to
#  drive the tool. Where a tool needs its own wrapping or its own second
#  call, it deserves a module, not a line here -- and until it has one,
#  the alias simply finds no artifact and reports ABSENT, which is true.
ALIAS_DB = {
    "gcovr":              "lcov",   # gcov -> tracefile
    "grcov":              "lcov",   # rust
    "llvm-cov":           "lcov",   # 'llvm-cov export --format=lcov'
    "cargo-llvm-cov":     "lcov",   # the same, wrapped for cargo
    "verilator_coverage": "lcov",   # '--write-info': VERILOG, read today
    "node":               "lcov",   # node's own test runner, witnessed
    "c8":                 "lcov",   # v8 coverage -> lcov, witnessed
    "coverlet":           "cobertura",  # .NET's usual CI output
    "scoverage":          "cobertura",  # scala, via its xml report
    #  kcov stood among the tracefile speakers until it was WITNESSED
    #  (2026-08-24): its output holds cobertura, codecov and sonarqube
    #  documents and NO tracefile -- not one 'end_of_record' anywhere.
    #  Its own helper scripts ('bash-helper*.sh') appear as 0% classes
    #  and belong to the omit globs.
    "kcov":               "cobertura",
}


class _SharedFormatFramework(CCoverageFramework):
    """One tool's name over another framework's format and invocation.

    'name' is THIS tool; the format is the one it writes, shared with
    the framework it reads through, so the record's provenance names
    the TOOL that ran and the FORMAT it wrote -- different facts, both
    wanted (D-7). Invocation is delegated too: the tools behind one
    format are invoked alike or not at all.
    """
    def __init__(self, name, through):
        """RETURN: framework standing for 'name', reading and invoking
        through 'through'."""
        self.name    = name
        self.through = through
        self.format  = through.format

    def wrap(self, argv, config, work_dir):
        """RETURN: list[str], what the underlying framework would run."""
        return self.through.wrap(argv, config, work_dir)

    def report_argv(self, config, work_dir):
        """RETURN: list[str] | None, the underlying framework's second
        call."""
        return self.through.report_argv(config, work_dir)


for _name, _target in sorted(ALIAS_DB.items()):
    register(_SharedFormatFramework(_name, _FRAMEWORK_DB[_target]))
