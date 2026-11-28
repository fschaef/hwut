"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE READERS -- one module per artifact FORMAT, and the table
         that says which tool speaks which.

DESCRIPTION
       IMPORTING THIS PACKAGE REGISTERS EVERY READER -- and it always
       runs before 'reader.py' is reachable, by the ordinary rule that
       a submodule cannot be imported ahead of its own package's
       '__init__.py'. Before the component split (session 2026-09-04)
       'reader.py' stood OUTSIDE this package and deferred importing
       it until 'framework_of' was actually called, so a caller who
       resolved no tool paid for none of them; that deferral is no
       longer reachable now that 'reader.py' lives inside the package
       whose loading it used to defer ('reader._load' says so at its
       own definition).

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
           kcov                 cobertura xml          bash; DRIVEN, its
                                                       own call (kcov.py)
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
from .reader import register, CCoverageFramework, _FRAMEWORK_DB

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
from . import kcov                 # noqa: F401


#  TOOLS THAT SPEAK A FORMAT SOMEBODY ELSE'S READER ALREADY READS.
#  An alias is not a second reader: it is the SAME format under a second
#  tool name, so a record names the tool that ran and the format it wrote.
#  AN ALIAS CLAIMS THE FORMAT AND NOTHING ELSE (D-46): it is never called,
#  offers no format, and no language may name it as its 'coverage'. A tool
#  hwut is to drive deserves a module with its own call scheme.
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
    #  kcov is no alias since 2026-11-26: hwut drives it ('kcov.py',
    #  coverage D-46). Its output holds cobertura, codecov and sonarqube
    #  documents and NO tracefile (witnessed 2026-08-24).
}


class _SharedFormatFramework(CCoverageFramework):
    """One tool's name over another framework's FORMAT -- read only.

    'name' is THIS tool; the format is the one it writes, shared with
    the framework it reads through, so the record's provenance names
    the TOOL and the FORMAT -- different facts, both wanted (D-7). The
    invocation is NOT shared (D-46): the alias has no call scheme, no
    second call and offers no format, so no language may name it.
    """
    def __init__(self, name, through):
        """RETURN: framework standing for 'name', reading through
        'through'."""
        self.name    = name
        self.through = through
        self.format  = through.format


for _name, _target in sorted(ALIAS_DB.items()):
    register(_SharedFormatFramework(_name, _FRAMEWORK_DB[_target]))
