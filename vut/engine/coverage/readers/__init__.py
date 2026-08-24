"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE READERS -- one module per artifact FORMAT, and the table
         that says which tool speaks which.

DESCRIPTION
       IMPORTING THIS PACKAGE REGISTERS EVERY READER; that is its whole
       purpose, and 'reader.reader_of' imports it on its first miss so
       that a caller who elects no tool pays for none of them.

       A FORMAT, NOT A TOOL, IS WHAT A READER KNOWS. The LCOV tracefile
       is written by 'lcov', 'gcovr', 'grcov' and 'kcov' alike, so ONE
       reader stands for all four: the alias table below is how a tool
       name reaches the reader of the format it speaks. Admitting a
       fifth tool that speaks LCOV is one line here and nothing else.

           coverage             coverage.py json       python
           lcov                 lcov tracefile         lingua franca
           gcovr                -> lcov
           grcov                -> lcov
           kcov                 -> lcov
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

       WHAT IS OWED (DISCUSSIONS todo-2), in the order it is worth
       building:

           julia-cov       annotated source, the gcov family with other
                           markers ('0' rather than '#####') -- possibly
                           one parameterised reader rather than two.

       A TOOL WITH NO READER IS STILL A CANDIDATE. 'trace', 'simplecov',
       'jacoco' and the rest stand in the default table so that a machine
       refuses BY NAME -- 'no reader for X; this build reads ...' --
       rather than reporting no coverage at all.
______________________________________________________________________________
"""
from ..reader import register, _READER_DB

from . import python_coverage      # noqa: F401
from . import lcov                 # noqa: F401
from . import gcov                 # noqa: F401
from . import cobertura            # noqa: F401
from . import go                   # noqa: F401
from . import luacov               # noqa: F401
from . import jacoco               # noqa: F401


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
    "kcov":               "lcov",   # any binary, ptrace-based
    "llvm-cov":           "lcov",   # 'llvm-cov export --format=lcov'
    "cargo-llvm-cov":     "lcov",   # the same, wrapped for cargo
    "verilator_coverage": "lcov",   # '--write-info': VERILOG, read today
    "coverlet":           "cobertura",  # .NET's usual CI output
    "scoverage":          "cobertura",  # scala, via its xml report
}


class _Alias:
    """One tool's name over another's reader.

    'name' is this tool; everything else is the reader it delegates to,
    so the record's provenance names the TOOL that ran and the FORMAT it
    wrote -- which are different facts and both are wanted (D-7).
    """
    def __init__(self, name, reader):
        """RETURN: _Alias standing for 'name', reading through 'reader'."""
        self.name          = name
        self.reader        = reader
        self.source_format = reader.source_format

    def wrap(self, argv, config, work_dir):
        """RETURN: list[str], what the underlying reader would run."""
        return self.reader.wrap(argv, config, work_dir)

    def report_argv(self, config, work_dir):
        """RETURN: list[str] | None, the underlying reader's second call."""
        return self.reader.report_argv(config, work_dir)

    def harvest(self, work_dir, source_root, config=None):
        """
        RETURN: CoverageRecord, with THIS tool's name in the header --
                the format is shared, the tool that wrote it is not.
                None, where no artifact stands.
        """
        from dataclasses import replace
        record = self.reader.harvest(work_dir, source_root, config)
        return None if record is None else replace(record, tool=self.name)


for _name, _target in sorted(ALIAS_DB.items()):
    register(_Alias(_name, _READER_DB[_target]))
