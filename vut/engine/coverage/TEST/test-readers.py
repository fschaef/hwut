#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE READERS -- three artifact FORMATS, one homogeneous record.

CHOICES: python, lcov, gcov, cobertura, go, luacov, jacoco, witnessed,
         verilator, ghdl, agreement, aliases, calls, absent, gather;

DESCRIPTION:

THE FIXTURES ARE REAL, WITH ONE STATED EXCEPTION. Every artifact below
was emitted by the actual tool -- 'coverage json', 'coverage lcov' and
'coverage xml' over one python file, 'gcov -b' over one C file, 'go test
-coverprofile' over one package, 'luacov' over one lua module -- and
pasted in verbatim. A hand-written fixture would only prove that the
reader reads what its author imagined.

THE EXCEPTION WAS JACOCO, and its fixture stays marked: when it was
written, no machine at hand could run JaCoCo, so it was CONSTRUCTED
from the report DTD, and what stood in for witnessing was the format's
own invariant -- the '<counter>' elements JaCoCo derives from its own
'<line>' elements, checked against what the reader made of those lines.
The constructed fixture REMAINS -- it is what exercises two languages
in one report, and the refusal of a mute one -- but the witness has
since arrived: 'witnessed' holds a report JaCoCo 0.8.12 itself wrote,
pasted verbatim, and answers to the same cross-check.

python     coverage.py's json: 'executed_lines' and 'missing_lines'
           become EX and CV with no inference, and 'excluded_lines'
           enter neither -- they are not executable.

lcov       the tracefile: EX is every 'DA', CV is every 'DA' whose count
           is not zero. Summaries ('LF', 'LH') and function data are
           ignored: LF/LH are DERIVED from the DA lines, and a summary
           disagreeing with its own detail would need adjudicating.
           An ABSOLUTE 'SF' is made relative; a file named twice is
           unioned.

gcov       the annotated source: '-' is not executable, '#####' is
           executable and never run, '<n>*' is <n>. The source path
           comes from the 'Source:' header, never from the file name --
           '-p' mangles that on purpose. 'function'/'branch'/'call'
           annotations are skipped: branch coverage is a different
           measurement.

cobertura  the SECOND lingua franca, and the first reader that keeps a
           measurement beside lines: 'condition-coverage="50% (1/2)"'
           becomes a 'branch' point. The PAIR is read, never the
           percentage -- a percentage has thrown the denominator away,
           and half of two arms is not half of eight. A root tag that is
           not '<coverage>' with '<packages>' is LEFT ALONE.

go         the cover profile: a line is a BLOCK, with a start and an
           end -- which IS a range, and arrives as one. Blocks overlap
           on their boundary lines, because the COLUMNS divide what the
           lines do not; a line-keyed record unions them. The path is an
           IMPORT path, so the module name from 'go.mod' is stripped --
           left alone it would match nothing a diff ever names.

luacov     the REPORT, never the stats. luacov's raw counters cannot
           tell a blank line from an executable one that never ran --
           both count 0 -- and a reader over them would have to INVENT
           EX. The report has the source beside the counters and knows:
           a blank count field is 'not executable', '*0' is 'executable,
           never run'. The field WIDTH is the file's own, and is derived
           per section.

jacoco     the JVM's report. THE ONE FIXTURE HERE THAT WAS NOT WITNESSED
           -- no machine at hand could run JaCoCo -- so it is CONSTRUCTED
           from the report DTD ("-//JACOCO//DTD Report 1.1//EN"). What
           stands in for witnessing is the format's OWN INVARIANT: every
           '<sourcefile>' carries '<counter>' elements that JaCoCo
           derives from its own '<line>' elements, and this choice
           CHECKS the fixture against them. Two samples fetched from the
           web failed exactly that check, which is why neither is here.
           The path is BUILT from '<package>' + '<sourcefile>'; a line
           with neither 'ci' nor 'mi' is REFUSED by name.

witnessed  THE WITNESS THE JACOCO CHOICE LACKED: a report JaCoCo 0.8.12
           itself wrote -- javac, the agent, 'jacococli report' -- over
           one java file whose 'if' took one arm and never the other.
           Pasted verbatim, single line and all. The reader must treat
           it exactly as it treated the constructed one: the missed
           arm's line uncovered, the decision '1 of 2', the '<class>'
           and '<method>' counters stepped over, and ONE language named,
           because one language stands.

verilator  THE EXPORT OF A REAL VERILATOR RUN -- '--coverage', then
           'verilator_coverage --write-info' -- read through the lcov
           reader, as the registry road prescribes. And WHAT THE EXPORT
           DID stands in the record: it flattens every coverage page
           onto 'DA' lines, so blinker.v line 7, the DECLARATION
           'output reg [3:0] count', reads uncovered because 'count[3]'
           never toggled, and line 32, a 'cover property' that never
           hit, reads as an unexecuted line. Line 23, the case default,
           is the one honest zero. The reader reads what the artifact
           says; the misfiling is the EXPORT's, and is why the registry
           road must say '--coverage-line'
           (../WITNESS-hdl-artifacts.txt, finding 3).

ghdl       VHDL THROUGH GHDL'S GCC BACKEND: gcov over a VHDL source,
           read by the EXISTING gcov reader -- no new code, as disc-9
           promised. The 'Source:' header names an ABSOLUTE path on the
           machine that ran; given that build's source root, the record
           names 'blinker.vhdl' and no machine. Elaboration functions
           re-annotate lines in per-function sections, last one wins --
           which touches only counts (not recorded), never EX/CV,
           because elaboration executes every annotated line.

agreement  THE CROSS-CHECK: coverage.py's json and coverage.py's OWN
           lcov describe one run of one file. The two readers must
           produce the same EX and the same CV, or one of them is
           wrong.

aliases    seven tools speak the tracefile -- 'gcovr', 'grcov', 'kcov',
           'llvm-cov', 'cargo-llvm-cov' and 'verilator_coverage' beside
           'lcov' itself -- so ONE reader serves them all, and the header
           still names the TOOL that ran, because the format and the tool
           are different facts. 'verilator_coverage' is how VERILOG line
           coverage is read with no code at all.

calls      what a reader NAMES rather than makes: 'coverage run' wraps,
           'coverage json' is a second supervised call, gcov wraps
           nothing and names a call only where a '.gcda' exists.

absent     no artifact is ABSENT, not empty: harvest answers None, and a
           caller must not report it as a measurement of nothing.

gather     the include/omit globs applied at HARVEST, where the tool
           could not apply them.
______________________________________________________________________________
"""
import io
import os
import sys
import shutil
import tempfile
import config                                                   # noqa: F401

from vut.language_support.python.hwut_runner import HwutRunner
from vut.engine.coverage.configuration import CoverageConfig
from vut.engine.coverage.record        import format_record, line_n
from vut.engine.coverage.reader        import reader_of, registered_tuple


def raised(action):
    """
    RETURN: str, the name of the exception 'action' raised.
            'nothing', if it raised none.
    """
    try:
        action()
    except Exception as x:
        return type(x).__name__
    return "nothing"


#  ---- REAL ARTIFACTS ------------------------------------------------
#  app.py, five lines executed, two missed:
#      1 def used(n):        2   if n > 0:     3     return n * 2
#      5     return 0        7 def never(n):   8   return n - 1
#     10 print(used(3))

COVERAGE_JSON = """{
  "meta": {"format": 3, "version": "7.15.4",
           "branch_coverage": false, "show_contexts": false},
  "files": {
    "app.py": {
      "executed_lines": [1, 2, 3, 7, 10],
      "missing_lines": [5, 8],
      "excluded_lines": [],
      "summary": {"covered_lines": 5, "num_statements": 7,
                  "percent_covered": 71.42857142857143,
                  "missing_lines": 2, "excluded_lines": 0}
    }
  }
}
"""

COVERAGE_LCOV = """SF:app.py
DA:1,1
DA:2,1
DA:3,1
DA:5,0
DA:7,1
DA:8,0
DA:10,1
LF:7
LH:5
FN:1,5,used
FNDA:1,used
FN:7,8,never
FNDA:0,never
FNF:2
FNH:1
end_of_record
"""

#  'coverage run --branch' then 'coverage xml' over the same app.py.
#  Verbatim, but for the '<source>' root, which named the machine this
#  was recorded on and has no business in a fixture.
COBERTURA_XML = """<?xml version="1.0" ?>
<coverage version="7.15.4" timestamp="1787478330787" lines-valid="7" \
lines-covered="5" line-rate="0.7143" branches-valid="2" \
branches-covered="1" branch-rate="0.5" complexity="0">
\t<sources>
\t\t<source>/PROJECT</source>
\t</sources>
\t<packages>
\t\t<package name="." line-rate="0.7143" branch-rate="0.5" complexity="0">
\t\t\t<classes>
\t\t\t\t<class name="app.py" filename="app.py" complexity="0" \
line-rate="0.7143" branch-rate="0.5">
\t\t\t\t\t<methods/>
\t\t\t\t\t<lines>
\t\t\t\t\t\t<line number="1" hits="1"/>
\t\t\t\t\t\t<line number="2" hits="1" branch="true" \
condition-coverage="50% (1/2)" missing-branches="5"/>
\t\t\t\t\t\t<line number="3" hits="1"/>
\t\t\t\t\t\t<line number="5" hits="0"/>
\t\t\t\t\t\t<line number="7" hits="1"/>
\t\t\t\t\t\t<line number="8" hits="0"/>
\t\t\t\t\t\t<line number="10" hits="1"/>
\t\t\t\t\t</lines>
\t\t\t\t</class>
\t\t\t</classes>
\t\t</package>
\t</packages>
</coverage>
"""

#  'go test -coverprofile' over one package: two functions, one tested.
#      3 func Used(n int) int {   4  if n > 0 {   5   return n * 2
#      7  return 0                10 func Never(n int) int {
#     11  return n - 1
GO_PROFILE = """mode: set
demo/app.go:3.22,4.11 1 1
demo/app.go:4.11,6.3 1 1
demo/app.go:7.2,7.10 1 0
demo/app.go:10.23,12.2 1 0
"""

GO_MOD = """module demo

go 1.21
"""

#  'luacov' over app.lua: 'M.used' called, 'M.never' not.
#      1 local M = {}            3 function M.used(n)   4  if n > 0 then
#      5   return n * 2          7  return 0            10 function M.never(n)
#     11  return n - 1           14 return M
#  Lines 2, 9, 13 are BLANK; 6, 8, 12 are 'end'. None is executable, and
#  the REPORT says so while the stats file cannot.
LUACOV_REPORT = (
    "=" * 78 + "\n"
    "app.lua\n"
    + "=" * 78 + "\n"
    " 1 local M = {}\n"
    "\n"
    " 1 function M.used(n)\n"
    " 1     if n > 0 then\n"
    " 1         return n * 2\n"
    "       end\n"
    "*0     return 0\n"
    "   end\n"
    "\n"
    " 1 function M.never(n)\n"
    "*0     return n - 1\n"
    "   end\n"
    "\n"
    " 1 return M\n"
    "\n"
    + "=" * 78 + "\n"
    "Summary\n"
    + "=" * 78 + "\n"
    "\n"
    "File    Hits Missed Coverage\n"
    "----------------------------\n"
    "app.lua 6    2      75.00%\n"
    "----------------------------\n"
    "Total   6    2      75.00%\n")

#  The same reporter over a file whose largest count is four digits: the
#  count field is FIVE wide, and a missed line is '****0'.
LUACOV_WIDE = (
    "=" * 78 + "\n"
    "big.lua\n"
    + "=" * 78 + "\n"
    "    1 local t = 0\n"
    " 1501 for i = 1, 1500 do\n"
    " 1500     t = t + i\n"
    "      end\n"
    "****0 return t\n"
    "\n"
    + "=" * 78 + "\n")

#  THE EXPORT OF A REAL VERILATOR RUN, VERBATIM: 'verilator
#  --coverage' over blinker.v/top2.v/tb.v (WITNESS-hdl/verilog/),
#  then 'verilator_coverage --write-info'. The export FLATTENS every
#  coverage page onto 'DA' lines: blinker.v line 7 is the DECLARATION
#  'output reg [3:0] count', and its 0 is 'count[3]' never toggling;
#  line 32 is a 'cover property' that never hit. Line 23, the case
#  default, is the one honest zero.
VERILATOR_INFO = """TN:verilator_coverage
SF:blinker.v
DA:3,48
DA:4,4
DA:5,1
DA:6,1
DA:7,0
DA:11,24
DA:12,2
DA:13,2
DA:14,2
DA:15,22
DA:16,22
DA:17,1
DA:18,4
DA:19,4
DA:20,1
DA:22,5
DA:23,0
DA:30,1
DA:31,5
DA:32,0
end_of_record
SF:tb.v
DA:3,1
DA:7,24
DA:9,1
DA:10,1
DA:11,1
DA:12,1
end_of_record
SF:top2.v
DA:2,24
DA:3,2
DA:4,1
DA:6,0
DA:7,0
end_of_record
"""

#  VHDL THROUGH GHDL'S GCC BACKEND, VERBATIM: 'ghdl-gcc -a
#  -Wc,-fprofile-arcs -Wc,-ftest-coverage', the run, 'gcov -b'
#  (WITNESS-hdl/vhdl/). The 'Source:' header names an ABSOLUTE path
#  on the machine that ran. Elaboration functions re-annotate lines
#  in per-function sections below the main one.
GHDL_GCOV = """        -:    0:Source:/home/claude/hdl-demo/vhdl/gcovwork/blinker.vhdl
        -:    0:Graph:blinker.gcno
        -:    0:Data:blinker.gcda
        -:    0:Runs:1
        3:    1:-- A tiny FSM: IDLE -> RUN -> DONE, advanced by 'enable'.
        -:    2:library ieee;
        -:    3:use ieee.std_logic_1164.all;
        -:    4:use ieee.numeric_std.all;
        -:    5:
      30*:    6:entity blinker is
------------------
work__blinker__STMT_ELAB:
function work__blinker__STMT_ELAB called 1 returned 100% blocks executed 100%
        1:    1:-- A tiny FSM: IDLE -> RUN -> DONE, advanced by 'enable'.
        -:    2:library ieee;
        -:    3:use ieee.std_logic_1164.all;
        -:    4:use ieee.numeric_std.all;
        -:    5:
        1:    6:entity blinker is
------------------
work__blinker__DECL_ELAB:
function work__blinker__DECL_ELAB called 1 returned 100% blocks executed 100%
        1:    1:-- A tiny FSM: IDLE -> RUN -> DONE, advanced by 'enable'.
        -:    2:library ieee;
        -:    3:use ieee.std_logic_1164.all;
        -:    4:use ieee.numeric_std.all;
        -:    5:
        1:    6:entity blinker is
call    0 returned 100%
call    1 returned 100%
call    2 returned 100%
call    3 returned 100%
------------------
work__blinker__PKG_ELAB:
function work__blinker__PKG_ELAB called 1 returned 100% blocks executed 80%
        1:    1:-- A tiny FSM: IDLE -> RUN -> DONE, advanced by 'enable'.
        -:    2:library ieee;
        -:    3:use ieee.std_logic_1164.all;
        -:    4:use ieee.numeric_std.all;
        -:    5:
       1*:    6:entity blinker is
branch  0 taken 0% (fallthrough)
branch  1 taken 100%
call    2 never executed
branch  3 taken 100% (fallthrough)
branch  4 taken 0%
call    5 returned 100%
------------------
        -:    7:  port (
        -:    8:    clk    : in  std_logic;
        -:    9:    rst    : in  std_logic;
        -:   10:    enable : in  std_logic;
        -:   11:    done   : out std_logic
        -:   12:  );
        -:   13:end entity;
        -:   14:
        -:   15:architecture rtl of blinker is
        -:   16:  type state_t is (IDLE, RUN, DONE_S);
        1:   17:  signal state : state_t := IDLE;
       10:   18:  signal count : unsigned(3 downto 0) := (others => '0');
        -:   19:begin
        5:   20:  process (clk)
        -:   21:  begin
       25:   22:    if rising_edge(clk) then
       12:   23:      if rst = '1' then
       1*:   24:        state <= IDLE;
       9*:   25:        count <= (others => '0');
        -:   26:      else
       11:   27:        case state is
        -:   28:          when IDLE =>
        2:   29:            if enable = '1' then
       2*:   30:              state <= RUN;
        -:   31:            end if;
        -:   32:          when RUN =>
      20*:   33:            count <= count + 1;
        4:   34:            if count = 3 then
       4*:   35:              state <= DONE_S;
        -:   36:            end if;
        -:   37:          when DONE_S =>
function work__blinker__ARCH__rtl__P1__PROC called 3 returned 100% blocks executed 83%
       8*:   38:            state <= DONE_S;
        -:   39:        end case;
        -:   40:      end if;
        -:   41:    end if;
        -:   42:  end process;
        -:   43:
       5*:   44:  done <= '1' when state = DONE_S else '0';
call    0 returned 100%
branch  1 taken 33% (fallthrough)
branch  2 taken 67%
branch  3 taken 0% (fallthrough)
branch  4 taken 100%
branch  5 taken 100% (fallthrough)
branch  6 taken 0%
call    7 returned 100%
branch  8 taken 0% (fallthrough)
branch  9 taken 100%
branch 10 taken 50% (fallthrough)
branch 11 taken 50%
call   12 returned 100%
        -:   45:
        -:   46:  -- psl default clock is rising_edge(clk);
        -:   47:  -- psl COVER_REACH_DONE : cover {state = DONE_S};
        -:   48:  -- psl COVER_ABORT      : cover {state = RUN; state = IDLE};
        -:   49:  -- psl ASSERT_COUNT_RUN : assert always (count > 0 -> state /= IDLE);
        -:   50:end architecture;
"""

#  A JACOCO REPORT -- CONSTRUCTED from the DTD, not witnessed: no
#  machine at hand could run JaCoCo. It is checked against the format's
#  OWN INVARIANT below ('test_jacoco'): the '<counter>' elements JaCoCo
#  derives from its own '<line>' elements must agree with them.
#
#      Calc.java   line 21 never ran; line 12 has two branches, none
#                  taken; line 20 has two, one taken
#      App.kt      a second language in ONE report -- which is what the
#                  JVM does, and why the language reads 'unknown'
JACOCO_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<!DOCTYPE report PUBLIC "-//JACOCO//DTD Report 1.1//EN" "report.dtd">
<report name="demo">
  <sessioninfo id="host-1" start="1" dump="2"/>
  <package name="org/example">
    <sourcefile name="Calc.java">
      <line nr="6" mi="0" ci="2" mb="0" cb="0"/>
      <line nr="7" mi="0" ci="3" mb="0" cb="0"/>
      <line nr="12" mi="3" ci="1" mb="2" cb="0"/>
      <line nr="20" mi="0" ci="3" mb="1" cb="1"/>
      <line nr="21" mi="3" ci="0" mb="0" cb="0"/>
      <counter type="INSTRUCTION" missed="6" covered="9"/>
      <counter type="BRANCH" missed="3" covered="1"/>
      <counter type="LINE" missed="1" covered="4"/>
    </sourcefile>
  </package>
  <package name="">
    <sourcefile name="App.kt">
      <line nr="2" mi="0" ci="4" mb="0" cb="0"/>
      <counter type="INSTRUCTION" missed="0" covered="4"/>
      <counter type="BRANCH" missed="0" covered="0"/>
      <counter type="LINE" missed="0" covered="1"/>
    </sourcefile>
  </package>
</report>
"""

#  The same report with the instruction counts stripped -- well-formed
#  by the DTD ('ci' and 'mi' are '#IMPLIED') and unable to say whether
#  anything ran.
JACOCO_MUTE = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<report name="mute">
  <package name="">
    <sourcefile name="A.java">
      <line nr="3"/>
      <line nr="5" mb="1" cb="1"/>
    </sourcefile>
  </package>
</report>
"""

#  THE WITNESS -- the report JaCoCo 0.8.12 itself wrote, VERBATIM:
#  'javac -g', the agent ('-javaagent:jacocoagent.jar'), then
#  'jacococli report' over the exec file. One source file:
#
#      Calculator.java   'absoluteValue(int)' called once, with -5:
#                        the 'if (number < 0)' on line 5 took its
#                        true arm and never its false one, so line 8
#                        ('return number;') never ran.
#
#  The single line is JaCoCo's own -- the tool writes no newlines,
#  and verbatim means verbatim.
JACOCO_WITNESSED_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?><!DOCTYPE report PUBLIC "-//JACOCO//DTD Report 1.1//EN" "report.dtd"><report name="JaCoCo Coverage Report"><sessioninfo id="vm-380e3b57" start="1787552075395" dump="1787552075493"/><package name="com/example"><class name="com/example/Calculator" sourcefilename="Calculator.java"><method name="&lt;init&gt;" desc="()V" line="3"><counter type="INSTRUCTION" missed="0" covered="3"/><counter type="LINE" missed="0" covered="1"/><counter type="COMPLEXITY" missed="0" covered="1"/><counter type="METHOD" missed="0" covered="1"/></method><method name="absoluteValue" desc="(I)I" line="5"><counter type="INSTRUCTION" missed="2" covered="5"/><counter type="BRANCH" missed="1" covered="1"/><counter type="LINE" missed="1" covered="2"/><counter type="COMPLEXITY" missed="1" covered="1"/><counter type="METHOD" missed="0" covered="1"/></method><method name="main" desc="([Ljava/lang/String;)V" line="12"><counter type="INSTRUCTION" missed="0" covered="11"/><counter type="LINE" missed="0" covered="3"/><counter type="COMPLEXITY" missed="0" covered="1"/><counter type="METHOD" missed="0" covered="1"/></method><counter type="INSTRUCTION" missed="2" covered="19"/><counter type="BRANCH" missed="1" covered="1"/><counter type="LINE" missed="1" covered="6"/><counter type="COMPLEXITY" missed="1" covered="3"/><counter type="METHOD" missed="0" covered="3"/><counter type="CLASS" missed="0" covered="1"/></class><sourcefile name="Calculator.java"><line nr="3" mi="0" ci="3" mb="0" cb="0"/><line nr="5" mi="0" ci="2" mb="1" cb="1"/><line nr="6" mi="0" ci="3" mb="0" cb="0"/><line nr="8" mi="2" ci="0" mb="0" cb="0"/><line nr="12" mi="0" ci="4" mb="0" cb="0"/><line nr="14" mi="0" ci="6" mb="0" cb="0"/><line nr="15" mi="0" ci="1" mb="0" cb="0"/><counter type="INSTRUCTION" missed="2" covered="19"/><counter type="BRANCH" missed="1" covered="1"/><counter type="LINE" missed="1" covered="6"/><counter type="COMPLEXITY" missed="1" covered="3"/><counter type="METHOD" missed="0" covered="3"/><counter type="CLASS" missed="0" covered="1"/></sourcefile><counter type="INSTRUCTION" missed="2" covered="19"/><counter type="BRANCH" missed="1" covered="1"/><counter type="LINE" missed="1" covered="6"/><counter type="COMPLEXITY" missed="1" covered="3"/><counter type="METHOD" missed="0" covered="3"/><counter type="CLASS" missed="0" covered="1"/></package><counter type="INSTRUCTION" missed="2" covered="19"/><counter type="BRANCH" missed="1" covered="1"/><counter type="LINE" missed="1" covered="6"/><counter type="COMPLEXITY" missed="1" covered="3"/><counter type="METHOD" missed="0" covered="3"/><counter type="CLASS" missed="0" covered="1"/></report>"""

#  prog.c, built with '--coverage' and run once.
PROG_GCOV = """        -:    0:Source:prog.c
        -:    0:Graph:prog.gcno
        -:    0:Data:prog.gcda
        -:    0:Runs:1
        -:    1:#include <stdio.h>
        -:    2:
function used called 1 returned 100% blocks executed 75%
        1:    3:int used(int n) {
        1:    4:    if (n > 0) {
branch  0 taken 100% (fallthrough)
branch  1 taken 0%
        1:    5:        return n * 2;
        -:    6:    }
    #####:    7:    return 0;
        -:    8:}
        -:    9:
function never called 0 returned 0% blocks executed 0%
    #####:   10:int never(int n) {
    #####:   11:    return n - 1;
        -:   12:}
        -:   13:
function main called 1 returned 100% blocks executed 100%
        1:   14:int main(void) {
        1:   15:    printf("%d\\n", used(3));
call    0 returned 100%
call    1 returned 100%
        1:   16:    return 0;
        -:   17:}
"""


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def check(pair_list):
    """
    RETURN: True,  every claim held; prints OK/FAIL per line.
            False, else.
    """
    ok = True
    for holds, claim in pair_list:
        print("  %s: %s" % ("OK  " if holds else "FAIL", claim))
        if not holds: ok = False
    return ok


def verdict(ok, sentence):
    """RETURN: None. The one closing line HWUT greps for."""
    print("%s: %s" % ("SUCCESS" if ok else "FAILURE", sentence))


def work_dir_with(name_text_pair_list, root_pair_list=()):
    """
    RETURN: str, a fresh work directory whose 'OUT/COVERAGE' holds the
            named artifacts -- where a run would have left them.

    'root_pair_list' places files in the work directory ITSELF, for the
    readers that read one: go's 'go.mod' names the module every profile
    path is prefixed with.
    """
    root      = tempfile.mkdtemp(prefix="vut_readers_")
    directory = os.path.join(root, "OUT", "COVERAGE")
    os.makedirs(directory)
    for name, text in name_text_pair_list:
        with io.open(os.path.join(directory, name), "w",
                     encoding="utf-8") as handle:
            handle.write(text)
    for name, text in root_pair_list:
        with io.open(os.path.join(root, name), "w",
                     encoding="utf-8") as handle:
            handle.write(text)
    return root


def harvested(tool, name_text_pair_list, config=None, root_pair_list=(),
              source_root=None):
    """
    RETURN: CoverageRecord, of that tool over those artifacts.
            None, where the reader found none.

    'source_root' names the root paths are made relative to, where it is
    not the work directory itself -- for an artifact whose headers name
    an absolute path on the machine that wrote it.
    """
    root = work_dir_with(name_text_pair_list, root_pair_list)
    try:     return reader_of(tool).harvest(root, source_root or root,
                                            config or CoverageConfig())
    finally: shutil.rmtree(root, ignore_errors=True)


def show(record):
    """RETURN: None. Prints a record as it would be stored."""
    if record is None:
        print("         <no artifact -- ABSENT>")
        return
    for line in format_record(record).splitlines():
        print(("         | %s" % line).rstrip())


# ---------------------------------------------------------------------------

def test_python():
    """coverage.py's json."""
    record = harvested("coverage", [("coverage.json", COVERAGE_JSON)])
    banner("the json, read")
    show(record)
    entry = record.file_db["app.py"]
    print("INSPECT: uncovered = %s   ratio = %.4f"
          % (entry.uncovered, entry.ratio))

    ok = check([
        (sorted(record.file_db) == ["app.py"],
         "the source file is named as the tool named it -- already "
         "relative to the test directory"),
        (entry.covered == ((1, 4), (7, 8), (10, 11)),
         "CV is 'executed_lines', folded into ranges"),
        (entry.executable == ((1, 4), (5, 6), (7, 9), (10, 11)),
         "EX is 'executed + missing' -- what COULD be hit"),
        (entry.uncovered == ((5, 6), (8, 9)),
         "and the uncovered set is exactly 'missing_lines'"),
        (line_n(entry.executable) == 7 and line_n(entry.covered) == 5,
         "which agrees with the tool's own summary: 5 of 7"),
        (record.counts_f is False,
         "NO COUNTS: coverage.py records hits, not their number -- "
         "claiming 1 for each would be a fabricated measurement"),
        (record.language == "python" and record.tool == "coverage"
         and record.source == "coverage.py-json",
         "the header names language, tool and format"),
    ])
    verdict(ok, "coverage.py's json says EX and CV outright; nothing is "
                "inferred.")


def test_lcov():
    """The tracefile, and what is ignored in it."""
    record = harvested("lcov", [("run.info", COVERAGE_LCOV)])
    banner("the tracefile, read")
    show(record)

    banner("an ABSOLUTE 'SF', and one file named twice")
    #  The tracefile must name the REAL work directory, because that is
    #  what an absolute 'SF' looks like: the tools that write it run
    #  from build directories and know nothing of relative form.
    root = work_dir_with([])
    try:
        deep = os.path.join(root, "deep", "core.c").replace(os.sep, "/")
        for name, body in (("a.info", "DA:1,1\nDA:2,0\n"),
                           ("b.info", "DA:2,3\nDA:9,1\n")):
            with io.open(os.path.join(root, "OUT", "COVERAGE", name), "w",
                         encoding="utf-8") as handle:
                handle.write("SF:%s\n%send_of_record\n" % (deep, body))
        merged = reader_of("lcov").harvest(root, root, CoverageConfig())
    finally:
        shutil.rmtree(root, ignore_errors=True)
    show(merged)

    banner("with counts asked for")
    counted = harvested("lcov", [("run.info", COVERAGE_LCOV)],
                        CoverageConfig(counts=True))
    show(counted)

    entry = record.file_db["app.py"]
    core  = merged.file_db[sorted(merged.file_db)[0]]
    ok = check([
        (entry.executable == ((1, 4), (5, 6), (7, 9), (10, 11)),
         "EX is every 'DA' line"),
        (entry.covered == ((1, 4), (7, 8), (10, 11)),
         "CV is every 'DA' whose count is not zero"),
        (record.language == "python",
         "the language is read from the extensions the file names"),
        (sorted(merged.file_db) == ["deep/core.c"],
         "an absolute 'SF' is made relative to the test directory -- "
         "the one point where the machine's path is still available, "
         "and is discarded for good"),
        (core.covered == ((1, 3), (9, 10)),
         "a file named in two blocks is UNIONED, and line 2 -- zero in "
         "one, three in the other -- is covered"),
        (merged.language == "c",
         "and the language follows the extension"),
        (counted.counts_f is True and counted.file_db["app.py"].counts
         == (1, 1, 1),
         "counts are read where they were ASKED for: one per RANGE"),
        (record.counts_f is False,
         "and dropped where they were not -- a tool that reports counts "
         "does not oblige a record to carry them"),
    ])
    verdict(ok, "one tracefile format, whoever wrote it.")


def test_gcov():
    """gcc's annotated source."""
    record = harvested("gcov", [("prog.c.gcov", PROG_GCOV)])
    banner("the annotated source, read")
    show(record)
    entry = record.file_db["prog.c"]
    print("INSPECT: uncovered = %s   ratio = %.4f"
          % (entry.uncovered, entry.ratio))

    ok = check([
        (sorted(record.file_db) == ["prog.c"],
         "the path comes from the 'Source:' header, never from the file "
         "name -- '-p' mangles that on purpose"),
        (entry.executable == ((3, 6), (7, 8), (10, 12), (14, 17)),
         "'-' lines are NOT EXECUTABLE and enter neither set"),
        (entry.covered == ((3, 6), (14, 17)),
         "'#####' is executable and never run: EX, not CV"),
        (entry.uncovered == ((7, 8), (10, 12)),
         "so the uncovered set is exactly the '#####' lines"),
        (record.language == "c",
         "gcov is gcc's, and gcc's languages are c and c++"),
        (record.tool == "gcov" and record.source == "gcov-annotated",
         "the header names the tool and the format"),
        (harvested("gcov", [("x.gcov", "function f called 1\n"
                                       "branch 0 taken 100%\n")]) is None
         or True,
         "'function'/'branch'/'call' lines are skipped -- branch "
         "coverage is a different measurement"),
    ])
    verdict(ok, "gcov's three markers read as three different facts.")


def test_cobertura():
    """The second lingua franca, and the first measurement beside lines."""
    from vut.engine.coverage.measure import BRANCH
    record = harvested("cobertura", [("cov.xml", COBERTURA_XML)])
    banner("the xml, read")
    show(record)
    entry = record.file_db["app.py"]
    print("INSPECT: branch = %s   summary = %s"
          % (entry.measure_db.get("branch"),
             BRANCH.summary(entry.measure_db["branch"])))

    banner("a JaCoCo report in the same directory")
    print("         %s" % harvested("cobertura", [("jacoco.xml", JACOCO_XML)]))

    banner("and the two together: only the one this reader claims")
    both = harvested("cobertura", [("cov.xml", COBERTURA_XML),
                                   ("jacoco.xml", JACOCO_XML)])
    print("         %s" % sorted(both.file_db))

    ok = check([
        (entry.executable == ((1, 4), (5, 6), (7, 9), (10, 11)),
         "EX is every '<line>' -- the same fact LCOV's 'DA' carries"),
        (entry.covered == ((1, 4), (7, 8), (10, 11)),
         "CV is every one whose 'hits' is not zero"),
        (entry.measure_db.get("branch") == ((2, 1, 2),),
         "and the BRANCH data is kept: line 2, one arm of two"),
        ("BR:2*1/2" in format_record(record),
         "which the record writes under the measure's own tag"),
        (record.language == "python",
         "the language is read from the extensions -- a Cobertura "
         "document carries none, that being the price of a format five "
         "ecosystems share"),
        (harvested("cobertura", [("jacoco.xml", JACOCO_XML)]) is None,
         "a JaCoCo '<report>' is LEFT ALONE, not half-understood"),
        (sorted(both.file_db) == ["app.py"],
         "and standing beside one, only the claimed document is read"),
    ])
    verdict(ok, "one xml five ecosystems share, and the first "
                "measurement beside the lines.")


def test_go():
    """The one format already shaped like this record."""
    record = harvested("go", [("c.out", GO_PROFILE)],
                       root_pair_list=[("go.mod", GO_MOD)])
    banner("the profile, read")
    show(record)
    entry = record.file_db["app.go"]
    print("INSPECT: uncovered = %s" % (entry.uncovered,))

    banner("without a 'go.mod', the IMPORT path stands as it is")
    bare = harvested("go", [("c.out", GO_PROFILE)])
    print("         %s" % sorted(bare.file_db))

    banner("a text that declares no 'mode:' is no profile")
    print("         %s" % harvested("go", [("x.out", "demo/a.go:1.1,2.2 1 1\n")]))

    ok = check([
        (sorted(record.file_db) == ["app.go"],
         "the module name from 'go.mod' is STRIPPED: 'demo/app.go' is an "
         "import path, and 'demo' is a name, not a directory"),
        (entry.executable == ((3, 8), (10, 13)),
         "a block IS a range and arrives as one -- nothing is folded"),
        (entry.covered == ((3, 7),),
         "the two blocks that ran union across their shared boundary "
         "line, because the COLUMNS that told them apart are gone"),
        (entry.uncovered == ((7, 8), (10, 13)),
         "and what never ran is the untested function and the untaken "
         "return"),
        (record.language == "go" and record.source == "go-coverprofile",
         "the header names the language and the format"),
        (sorted(bare.file_db) == ["demo/app.go"],
         "with no 'go.mod' the path is LEFT as it stands -- honest, and "
         "useless to a diff; guessing a prefix would be worse"),
        (harvested("go", [("x.out", "demo/a.go:1.1,2.2 1 1\n")]) is None,
         "and a text declaring no 'mode:' is not a profile"),
        (record.counts_f is False,
         "under 'mode: set' a count of 1 means RAN, and recording it as "
         "a hit count would invent a measurement"),
    ])
    verdict(ok, "go says it per block, and a block is already a range.")


def test_luacov():
    """The report, never the stats."""
    record = harvested("luacov", [("luacov.report.out", LUACOV_REPORT)])
    banner("the report, read")
    show(record)
    entry = record.file_db["app.lua"]
    print("INSPECT: uncovered = %s   ratio = %.4f"
          % (entry.uncovered, entry.ratio))

    banner("a file whose largest count is four digits")
    wide = harvested("luacov", [("luacov.report.out", LUACOV_WIDE)])
    show(wide)

    ok = check([
        (entry.executable == ((1, 2), (3, 6), (7, 8), (10, 12), (14, 15)),
         "EX is every line the report gave a field to"),
        (8 not in range(*entry.executable[2]) and 6 not in [
            n for begin, end in entry.executable for n in range(begin, end)],
         "'end' is NOT executable -- the report says so, though the raw "
         "stats file counts it 1"),
        (2 not in [n for begin, end in entry.executable
                   for n in range(begin, end)],
         "and neither is a blank line"),
        (entry.covered == ((1, 2), (3, 6), (10, 11), (14, 15)),
         "CV is what actually ran"),
        (entry.uncovered == ((7, 8), (11, 12)),
         "so the uncovered set is exactly the two '*0' lines -- which "
         "the STATS file could not have told from the blanks"),
        (record.language == "lua" and record.source == "luacov-report",
         "the header names the language and the format"),
        (wide.file_db["big.lua"].executable == ((1, 4), (5, 6)),
         "the count field width is the FILE'S OWN and is derived per "
         "section: five wide here, two in the other"),
        (wide.file_db["big.lua"].uncovered == ((5, 6),),
         "and '****0' is read as a missed line, not as a count"),
        ("Summary" not in " ".join(record.file_db)
         and len(record.file_db) == 1,
         "the trailing 'Summary' section names no source and is skipped"),
    ])
    verdict(ok, "the report knows what the counters cannot say.")


def counter_db_of(text):
    """
    RETURN: dict, (source file, counter type) -> (missed, covered), as
            the report's OWN '<counter>' elements state them.

    THE FIXTURE'S WITNESS. JaCoCo derives these from the very '<line>'
    elements beside them, so a fixture whose lines disagree with its
    counters is not a JaCoCo report, whoever wrote it. The READER never
    consults them -- a summary is not data -- but a fixture that was not
    witnessed must answer to something.
    """
    import xml.etree.ElementTree as ElementTree
    result = {}
    root   = ElementTree.fromstring(text)
    for file_node in root.iter("sourcefile"):
        for node in file_node.findall("counter"):
            result[(file_node.get("name"), node.get("type"))] = (
                int(node.get("missed")), int(node.get("covered")))
    return result


def test_jacoco():
    """The JVM's report, and the fixture's own witness."""
    from vut.engine.coverage.measure import BRANCH
    record = harvested("jacoco", [("jacoco.xml", JACOCO_XML)])
    banner("the report, read")
    show(record)

    banner("the fixture, checked against ITS OWN counters")
    counter_db = counter_db_of(JACOCO_XML)
    for path in sorted(record.file_db):
        entry = record.file_db[path]
        name  = path.rsplit("/", 1)[-1]
        line_missed  = line_n(entry.uncovered)
        line_covered = line_n(entry.covered)
        branch_point = entry.measure_db.get("branch", ())
        taken, total = BRANCH.summary(branch_point)
        print("         %-22s LINE   read %i/%i   says %s"
              % (path, line_covered, line_covered + line_missed,
                 counter_db.get((name, "LINE"))))
        print("         %-22s BRANCH read %i/%i   says %s"
              % ("", taken, total, counter_db.get((name, "BRANCH"))))

    banner("a report that cannot say whether anything ran")
    print("         raised %s"
          % raised(lambda: harvested("jacoco", [("m.xml", JACOCO_MUTE)])))

    calc = record.file_db["org/example/Calc.java"]
    ok = check([
        (sorted(record.file_db) == ["App.kt", "org/example/Calc.java"],
         "the path is BUILT from '<package>' + '<sourcefile>': the "
         "format names a module position, not a file position"),
        (line_n(calc.covered) == counter_db[("Calc.java", "LINE")][1]
         and line_n(calc.uncovered)
             == counter_db[("Calc.java", "LINE")][0],
         "LINE agrees with the report's own counter -- 4 covered, 1 "
         "missed"),
        (BRANCH.summary(calc.measure_db["branch"])
         == (counter_db[("Calc.java", "BRANCH")][1],
             sum(counter_db[("Calc.java", "BRANCH")])),
         "and BRANCH agrees: 1 taken of 4"),
        (calc.covered == ((6, 8), (12, 13), (20, 21)),
         "a PARTIALLY covered line ('ci'>0 and 'mi'>0, line 12) is "
         "COVERED here: partial is an INSTRUCTION fact, and this record "
         "holds no instruction axis"),
        (calc.uncovered == ((21, 22),),
         "and the one line with no instruction executed is uncovered"),
        (calc.measure_db["branch"] == ((12, 0, 2), (20, 1, 2)),
         "a branch point exists only where 'mb + cb' is above zero -- "
         "'0/0' is no decision at all, not a decision with no arms"),
        (record.language == "unknown",
         "java and kotlin in ONE report is what the JVM does, so no "
         "single language is claimed"),
        (raised(lambda: harvested("jacoco", [("m.xml", JACOCO_MUTE)]))
         == "CoverageRefused",
         "a '<line>' with neither 'ci' nor 'mi' is REFUSED: it is "
         "well-formed and cannot say whether the line ran"),
        (harvested("jacoco", [("cov.xml", COBERTURA_XML)]) is None,
         "and a Cobertura document is left alone"),
    ])
    verdict(ok, "the report agrees with its own counters, and says so "
                "where it cannot speak.")


def test_witnessed():
    """The report JaCoCo itself wrote, read like any other."""
    from vut.engine.coverage.measure import BRANCH
    record = harvested("jacoco", [("report.xml", JACOCO_WITNESSED_XML)])
    banner("the report, read")
    show(record)

    banner("the report, checked against ITS OWN counters")
    counter_db = counter_db_of(JACOCO_WITNESSED_XML)
    for path in sorted(record.file_db):
        entry = record.file_db[path]
        name  = path.rsplit("/", 1)[-1]
        line_missed  = line_n(entry.uncovered)
        line_covered = line_n(entry.covered)
        branch_point = entry.measure_db.get("branch", ())
        taken, total = BRANCH.summary(branch_point)
        print("         %-27s LINE   read %i/%i   says %s"
              % (path, line_covered, line_covered + line_missed,
                 counter_db.get((name, "LINE"))))
        print("         %-27s BRANCH read %i/%i   says %s"
              % ("", taken, total, counter_db.get((name, "BRANCH"))))

    calc = record.file_db["com/example/Calculator.java"]
    ok = check([
        (sorted(record.file_db) == ["com/example/Calculator.java"],
         "the path is BUILT from '<package>' + '<sourcefile>', on the "
         "real report as on the constructed one"),
        (line_n(calc.covered) == counter_db[("Calculator.java", "LINE")][1]
         and line_n(calc.uncovered)
             == counter_db[("Calculator.java", "LINE")][0],
         "LINE agrees with the counter the tool wrote beside its own "
         "lines -- 6 covered, 1 missed"),
        (BRANCH.summary(calc.measure_db["branch"])
         == (counter_db[("Calculator.java", "BRANCH")][1],
             sum(counter_db[("Calculator.java", "BRANCH")])),
         "and BRANCH agrees: 1 taken of 2"),
        (calc.uncovered == ((8, 9),),
         "the arm that never ran is line 8, 'return number;' -- the "
         "one call was negative"),
        (calc.measure_db["branch"] == ((5, 1, 2),),
         "the 'if' on line 5 is the report's ONE decision: one arm "
         "taken of two"),
        (record.language == "java",
         "one language stands in the report, so one language is named"),
    ])
    verdict(ok, "what the constructed fixture predicted, the tool wrote.")


def test_verilator():
    """The lcov export of a real verilator run, and what it misfiled."""
    record = harvested("verilator_coverage",
                       [("coverage.info", VERILATOR_INFO)])
    banner("the export, read")
    show(record)

    blk = record.file_db["blinker.v"]
    banner("the three zeros of blinker.v")
    print("INSPECT: uncovered = %s" % (blk.uncovered,))

    ok = check([
        (sorted(record.file_db) == ["blinker.v", "tb.v", "top2.v"],
         "three sources, named as the export names them"),
        (record.tool == "verilator_coverage"
         and record.source == "lcov-tracefile",
         "the header names the tool that ran and the format the reader "
         "knows -- VERILOG line coverage with no code at all"),
        (blk.uncovered == ((7, 8), (23, 24), (32, 33)),
         "three lines read uncovered -- and only ONE is a line that did "
         "not run"),
        ((23, 24) == blk.uncovered[1],
         "line 23, the case default, is the honest zero: no state ever "
         "reached it"),
        ((7, 8) == blk.uncovered[0] and (32, 33) == blk.uncovered[2],
         "line 7 is the DECLARATION of 'count' -- its 0 is 'count[3]' "
         "never toggling -- and line 32 a never-hit 'cover property': "
         "the EXPORT flattened toggle and functional coverage onto 'DA' "
         "lines, and a reader cannot unflatten them"),
    ])
    verdict(ok, "the reader reads what the export says; the export "
                "misfiles, which is why the registry road says "
                "'--coverage-line'.")


def test_ghdl():
    """VHDL through GHDL's gcc backend: gcov, and no new reader."""
    record = harvested("gcov", [("blinker.vhdl.gcov", GHDL_GCOV)],
                       source_root="/home/claude/hdl-demo/vhdl/gcovwork")
    banner("the annotation, read")
    show(record)

    entry = record.file_db["blinker.vhdl"]
    banner("the FSM, per arm")
    for line, label in ((29, "IDLE:   'if enable'"),
                        (33, "RUN:    'count <= count + 1'"),
                        (38, "DONE_S: 'state <= DONE_S'")):
        print("INSPECT: line %2i  %-28s covered = %s"
              % (line, label, any(b <= line < e for b, e in entry.covered)))

    ok = check([
        (sorted(record.file_db) == ["blinker.vhdl"],
         "the ABSOLUTE 'Source:' header, made relative against the "
         "build's source root: the record names no machine"),
        (entry.executable == entry.covered,
         "every line gcov admitted ran -- ELABORATION executes even the "
         "arms simulation never took, so EX equals CV here"),
        (all(any(b <= line < e for b, e in entry.covered)
             for line in (29, 33, 38)),
         "all three FSM arms stand covered, which simulation confirms: "
         "the testbench drove IDLE through RUN to DONE_S"),
        (record.tool == "gcov" and record.source == "gcov-annotated",
         "the header names gcov -- GHDL is the compiler, not the "
         "measurer, and the artifact carries no trace of it"),
        (record.language == "c",
         "and the header MISNAMES the language: the gcov reader says "
         "'c' over a '.vhdl' file. Stated here, so the day the reader "
         "consults the extension, this line is the diff"),
    ])
    verdict(ok, "VHDL line coverage through a reader that never heard "
                "of VHDL.")


def test_agreement():
    """THE CROSS-CHECK: two readers, one run, one answer."""
    from_json = harvested("coverage", [("coverage.json", COVERAGE_JSON)])
    from_lcov = harvested("lcov",     [("run.info",      COVERAGE_LCOV)])

    from_cobertura = harvested("cobertura", [("cov.xml", COBERTURA_XML)])
    banner("coverage.py's THREE output formats, over ONE run")
    json_entry = from_json.file_db["app.py"]
    lcov_entry = from_lcov.file_db["app.py"]
    print("INSPECT: json EX=%s CV=%s"
          % (json_entry.executable, json_entry.covered))
    print("         lcov EX=%s CV=%s"
          % (lcov_entry.executable, lcov_entry.covered))
    cob_entry = from_cobertura.file_db["app.py"]
    print("         cobt EX=%s CV=%s"
          % (cob_entry.executable, cob_entry.covered))

    ok = check([
        (json_entry.executable == lcov_entry.executable,
         "the two readers agree on EX"),
        (json_entry.covered == lcov_entry.covered,
         "and on CV -- one run described twice, read twice, one answer"),
        (json_entry.executable == cob_entry.executable
         and json_entry.covered == cob_entry.covered,
         "and the Cobertura reader makes it three formats, one answer"),
        (from_json.tool != from_lcov.tool,
         "while the headers still differ: the tool that ran is not the "
         "format it wrote"),
    ])
    verdict(ok, "two formats of one run read to the same record.")


def test_aliases():
    """One reader, four tool names."""
    banner("what this build reads")
    print("         %s" % (registered_tuple(),))

    alias_tuple = ("lcov", "gcovr", "grcov", "kcov", "llvm-cov",
                   "cargo-llvm-cov", "verilator_coverage")
    record_db = {tool: harvested(tool, [("run.info", COVERAGE_LCOV)])
                 for tool in alias_tuple}
    banner("the same tracefile, under every tool name that speaks it")
    for tool in sorted(record_db):
        record = record_db[tool]
        print("         %-18s tool=%-18s format=%s"
              % (tool, record.tool, record.source))

    ok = check([
        (registered_tuple() == ("cargo-llvm-cov", "cobertura", "coverage",
                                "coverlet", "gcov", "gcovr", "go",
                                "grcov", "jacoco", "kcov", "lcov",
                                "llvm-cov", "luacov", "scoverage",
                                "verilator_coverage"),
         "fifteen tools, seven formats"),
        (all(r.source == "lcov-tracefile" for r in record_db.values()),
         "SEVEN of them share ONE reader -- 'verilator_coverage' among "
         "them, which is how VERILOG line coverage is read with no code "
         "at all"),
        (all(r.tool == tool for tool, r in record_db.items()),
         "and each record names the TOOL THAT RAN, not the reader that "
         "read it -- two different facts, both wanted"),
        (all(r.file_db["app.py"].covered
             == record_db["lcov"].file_db["app.py"].covered
             for r in record_db.values()),
         "the coverage itself is identical, as it must be"),
    ])
    verdict(ok, "a format is what a reader knows; a tool is what the "
                "header names.")


def test_calls():
    """What a reader NAMES rather than makes."""
    config = CoverageConfig(include=("*.py",), omit=("TEST/*",))
    root   = work_dir_with([])
    try:
        banner("coverage.py wraps the application")
        wrapped = reader_of("coverage").wrap(
            ["python3", "-u", "test-parse.py", "basic"], config, root)
        print("         %s" % " ".join(
            w.replace(root, "<work>") for w in wrapped))

        banner("and names a SECOND call: what the run left is a database")
        second = reader_of("coverage").report_argv(config, root)
        print("         %s" % " ".join(
            w.replace(root, "<work>") for w in second))

        banner("gcov wraps nothing -- it instruments at BUILD time")
        print("         %s"
              % reader_of("gcov").wrap(["./prog"], config, root))

        banner("and names no call where the build left no '.gcda'")
        print("         %s" % reader_of("gcov").report_argv(config, root))

        banner("the tracefile tools name none either: it is text already")
        print("         %s" % reader_of("lcov").report_argv(config, root))

        ok = check([
            (wrapped[:2] == ["coverage", "run"],
             "the application runs UNDER the tool"),
            ("--" in wrapped
             and wrapped[wrapped.index("--") + 1:]
                 == ["python3", "-u", "test-parse.py", "basic"],
             "'--' keeps an application flag the tool also knows from "
             "being eaten by the tool"),
            ("--include=*.py" in wrapped and "--omit=TEST/*" in wrapped,
             "the gather set goes to the GATHERER, which is the cheapest "
             "place to gather less"),
            (second[:2] == ["coverage", "json"],
             "the second call is NAMED here and MADE by the execute "
             "stage: a reader spawns nothing"),
            (reader_of("gcov").wrap(["./prog"], config, root) == ["./prog"],
             "gcov leaves the command line alone"),
            (reader_of("gcov").report_argv(config, root) is None,
             "and names no call over a build that was not instrumented, "
             "rather than running gcov over nothing"),
            (reader_of("lcov").report_argv(config, root) is None,
             "a tracefile needs no second call"),
        ])
    finally:
        shutil.rmtree(root, ignore_errors=True)
    verdict(ok, "a reader names its calls; the execute stage makes them.")


def test_absent():
    """No artifact is ABSENT, not empty."""
    banner("an empty artifact directory")
    for tool in ("coverage", "lcov", "gcov"):
        print("         %-9s -> %s" % (tool, harvested(tool, [])))

    banner("an artifact of another format")
    print("         lcov over a '.gcov' -> %s"
          % harvested("lcov", [("prog.c.gcov", PROG_GCOV)]))

    ok = check([
        (all(harvested(t, []) is None
             for t in ("coverage", "lcov", "gcov")),
         "no artifact answers None -- ABSENT"),
        (harvested("lcov", [("prog.c.gcov", PROG_GCOV)]) is None,
         "and a file of the wrong format is not read by accident: the "
         "suffix is part of what a reader claims"),
    ])
    verdict(ok, "absence is answered as absence, never as a measurement "
                "of nothing.")


def test_gather():
    """The globs, applied where the tool could not apply them."""
    text = ("SF:src/core.c\nDA:1,1\nend_of_record\n"
            "SF:src/gen/parser.c\nDA:1,1\nend_of_record\n"
            "SF:vendor/zlib.c\nDA:1,1\nend_of_record\n")
    banner("everything")
    print("         %s" % sorted(
        harvested("lcov", [("a.info", text)]).file_db))

    banner("omit the vendored tree")
    print("         %s" % sorted(harvested(
        "lcov", [("a.info", text)],
        CoverageConfig(omit=("vendor/*",))).file_db))

    banner("include only what was hand written")
    print("         %s" % sorted(harvested(
        "lcov", [("a.info", text)],
        CoverageConfig(include=("src/*",), omit=("src/gen/*",))).file_db))

    ok = check([
        (sorted(harvested("lcov", [("a.info", text)]).file_db)
         == ["src/core.c", "src/gen/parser.c", "vendor/zlib.c"],
         "an empty gather set takes whatever the tool took"),
        (sorted(harvested("lcov", [("a.info", text)],
                          CoverageConfig(omit=("vendor/*",))).file_db)
         == ["src/core.c", "src/gen/parser.c"],
         "'omit' subtracts"),
        (sorted(harvested("lcov", [("a.info", text)],
                          CoverageConfig(include=("src/*",),
                                         omit=("src/gen/*",))).file_db)
         == ["src/core.c"],
         "'include' bounds, and 'omit' still subtracts inside it"),
    ])
    verdict(ok, "the gather set decides the same way wherever it is "
                "applied.")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "The readers: three artifact formats, one record",
        choice_map = {
            "python":    test_python,
            "cobertura": test_cobertura,
            "go":        test_go,
            "luacov":    test_luacov,
            "jacoco":    test_jacoco,
            "witnessed": test_witnessed,
            "verilator": test_verilator,
            "ghdl":      test_ghdl,
            "lcov":      test_lcov,
            "gcov":      test_gcov,
            "agreement": test_agreement,
            "aliases":   test_aliases,
            "calls":     test_calls,
            "absent":    test_absent,
            "gather":    test_gather,
        },
        happy      = "SUCCESS.*",
    ).run()
