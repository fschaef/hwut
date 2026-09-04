==============================================================================
README-INDEX -- WHAT EACH README COVERS, AND WHERE IT HAS DRIFTED
==============================================================================

VERSION: 2

Goal (3) of three: the README knowledge indexed. READMEs state
MECHANICS -- how a thing works, not why it was chosen. The 'why' is
goal (2), 'adm/WORK/RATIONALE-LOGIC.txt'.

DERIVED. Nothing was moved and no README rewritten; where this
disagrees with a README, the README is right -- EXCEPT where section 2
says the README disagrees with THE TREE, and then neither is right.

TOTAL: 4806 lines across 20 READMEs. Two of them --
operations (1283) and exploration (798) -- are 43% of all README text.

------------------------------------------------------------------------------
1  DRIFT: WHAT A README NAMES THAT THE TREE DOES NOT HAVE
------------------------------------------------------------------------------

Measured, not read: every module path quoted in a README was looked up
in the tree. Three do not resolve, and all three are real.

1.1  'provision/provider.py'  -- engine/operations/README.txt   ** REAL **
     A STALE PATH, not a dissolved shape. The module EXISTS, as
     'operations/run/provider.py'; there is no 'operations/provision/'
     directory. The README (line 309) names the right module at the
     wrong place. Milder than version 1 of this file claimed.

1.2  'parser/core.py'  -- engine/coverage/README.txt   ** WITHDRAWN **
     NOT A DEFECT. Line 118 reads 'SF:parser/core.py' -- an 'SF:'
     field inside an EXAMPLE LCOV RECORD, sample data illustrating the
     format, not a claim about any VUT module. The extraction regex
     caught example content. Version 1 of this file was wrong.

1.3  'adm/census.py'  -- engine/coverage/README.txt   ** REAL **
     A STALE CITATION OF A RETIRED TOOL. Version 1 guessed this was
     an untracked file. IT IS NOT: the complete tree has no
     'census.py' anywhere, and 'CENSUS' is a VERB in this project --
     of five uses in the tree, four are the action ("nobody had
     reason to census 'bin/' directly"; "CENSUS bin/, ADM/, AND EVERY
     OTHER DIRECTORY"), and only this one names a file.

     WHAT DOES THE CENSUSING IS 'hwut.run'. 'adm/TEST/hwut-info.dat'
     and 'bin/TEST/hwut-info.dat' both exist: adm and bin are
     themselves hwut test directories, so the framework censuses
     itself. 'census.py' was the BOOTSTRAP, needed before hwut could
     run over its own tree, and retired when it could. The citation
     outlived it.

1.4  WITHDRAWN LIKEWISE: 'plan/wish.py' (display README) and
     'feeder/html_feeder.py' (operations README). Both modules exist;
     version 1's candidate-path list simply failed to find them.

     OF FIVE PATHS FLAGGED IN VERSION 1, TWO ARE REAL AND THREE WERE
     FALSE POSITIVES. The lesson is the one r-5 taught three times
     over, now turned on this file's own method: a measurement is
     only as good as what it measured against, and version 1 measured
     against an INCOMPLETE TREE (review-r6: six coverage modules were
     absent from the dump). Re-run on the complete tree, the finding
     shrank by three fifths.

ALSO: SEVEN READMEs STILL SAY 'test_run', a component that no longer
exists -- it became 'operations'. They are:
     auxiliary/README-directory_mutex.txt   orchestrator/README.txt
     orchestrator/plan/README.txt           orchestrator/run/README.txt
     orchestrator/scheduler/README.txt      operations/README.txt
     bookkeeper/README.txt
Some are historical prose ('test_run's directory lock lived inside
store.py') and correct as history; others are live references. They
were NOT distinguished here, because that needs reading, not grepping.

------------------------------------------------------------------------------
2  READMEs WITH NO SECTION STRUCTURE
------------------------------------------------------------------------------

Six READMEs carry no numbered sections, so nothing in them can be
cited by section and nothing can be checked for completeness:
       179  test_writing_support/hwut_pype/README.txt
       164  services/README.txt
       114  engine/compare/README.txt
        95  engine/display/README.txt
        45  bin/README.txt
        43  services/lib/viewers/nvim/README.txt

'services/README.txt' (164 lines) is the notable one: services is the
component with the most faces and the most E- rulings, and its README
has no navigable structure at all.

------------------------------------------------------------------------------
3  THE SECTIONS, BY README (largest first)
------------------------------------------------------------------------------

==============================================================================
engine/operations/README.txt   [1283 lines]
==============================================================================
  1      THE TASK
  2      THE DESIGN
      2.1    AT A GLANCE. One declarative description flows down into the
      2.2    LAYERING.
      2.3    ONE ARTIFACT, THREE ROLES: The behavior description
      2.4    THREE CONCERNS, kept strictly apart. Compare sits BETWEEN two
      2.5    THREE OPERATIONS -- two READERS and one WRITER, on one groundwor
      2.6    TWO LAWS THAT KEPT RE-DERIVING THEMSELVES. Both were reached
      2.7    THE CONFIGURATION. THREE WORLDS, kept apart.
      2.8    THE FRONT DOOR. One callable assembles everything below, so noth
  3      RUN -- provision by execution
  4      RECORDING -- capturing a Run for a later loaded read
  5      REPLAY -- provision by stored data
  6      THE NOMINAL -- the accepted subject record
  7      THE SUBJECTS-TO-NOMINALS MAP  (compare-side; used by the two REA
  8      EquivalenceCheck -- read -> verdict
  9      DifferenceDisplay -- read -> feed the aligned comparison
  10     Accept -- write the nominal (THIN; the intelligence is EXTERNAL)
  11     THE FEED -- protocol, hubs, targets, and the merge loop
      11.1   THE SESSION -- two hubs, two halves. Feeding a consumer is a ses
      11.2   DOWN IS COMPARE'S -- reuse it, do not invent one. compare/feeder
      11.3   UP IS THE ARTIFACT, NOT THE VIEW. DOWN is a rich PROJECTION for
      11.4   THE HUBS AND THE DISPLAY ADAPTER. Our hub drives the session (em
      11.5   DISPLAY TARGETS. The shipped interactive tier is the TERMINAL:
      11.6   THE MERGE LOOP -- who keeps display and content coherent. Editin
      11.7   RE-ASSOCIATION IS BLOCK-SCOPED, AND THE BLOCK IS NAMED BY COMPAR
  12     THE OBSERVER  (progress seam -- all operations)
  13     THE BRIEF REPORT  (verdict vocabulary -- reused, lightly extende
  14     NAMES

==============================================================================
engine/orchestrator/exploration/README.txt   [798 lines]
==============================================================================
  1      THE SPECIFICATION LANGUAGE
  2      THE TEST PARAMETERS
      2.1    ABSENCE, OFF, AND THE SCOPE
  3      THE THREE CARRIERS
  4      THE HEADER
      4.1    '%' IS THE SOURCE FILE'S STEM
  5      hwut.conf
      5.1    'default_app'
      5.2    TARGETS
  6      EXCLUSIVITY
  7      LANGUAGE
      7.1    WHAT THE FRAMEWORK READ
  8      THE READING PIPELINE
  9      THE RELATION TABLE
  10     EXPLORE -- CTestAppSet
  11     SELECT -- CTestTaskList
  12     ACT -- CTestCaseSequence

==============================================================================
engine/coverage/README.txt   [505 lines]
==============================================================================
  1      THE THREE THINGS THIS COMPONENT OWNS
  2      THE MODULES
  3      THE ROAD OF ONE MEASUREMENT
  4      THE RECORD
  5      WHAT A COVERAGE RUN IS
  6      EVERY REFUSAL THIS COMPONENT MAKES
  7      ADDING A LANGUAGE
  8      THE TEST
  9      SEE ALSO

==============================================================================
engine/orchestrator/plan/README.txt   [222 lines]
==============================================================================
  1      THE NODES  (form.py)
  2      THE LINKS  (form.py)
  3      THE EXCLUSION SETS  (form.py)
  4      CONSTRUCTION LAWS  (form.py)
  5      THE PRINT  (printer.py)
  6      THE WISH  (wish.py)
  7      DETERMINATION  (determine.py)
  8      THE TREE PLAN  (tree.py)
  9      THE PROVISION LADDER  (P-18)

==============================================================================
engine/orchestrator/run/README.txt   [200 lines]
==============================================================================
  1      THE VOCABULARY  (vocabulary.py)
  2      THE TREE SCHEDULER  (orchestrate.py)
  3      THE SUMMARY  (summary.py)
  4      THE RECEIVER  (receiver.py)
  5      THE REAL DISPATCHER  (dispatcher.py, adapter.py)
  6      THE TRANSLATION  (adapter.py)

==============================================================================
test_writing_support/hwut_pype/README.txt   [179 lines]
==============================================================================
    no numbered sections

==============================================================================
test_writing_support/python/README-hwut_hocon.txt   [174 lines]
==============================================================================
  1      THE GRAMMAR
  2      STRINGS CARRY QUOTES
  3      NUMBERS
  4      BOOLEANS AND NOTHING
  5      COMMENTS
  6      REFUSED, BY NAME
  7      FAULTS
  8      WHAT THE PARSER HANDS BACK

==============================================================================
engine/operations/run/README-provider.txt   [173 lines]
==============================================================================
  1      THE STAGES, AND THE ONE ANSWER SHAPE
  2      THE PROVIDER FAMILY
  3      SEQUENCE: THE INTERACTIVE SESSION (MultiExecute)
  4      SEQUENCE: THE WAVE BUILD (MultiBuild)
  5      THE ORCHESTRATOR'S DECISION

==============================================================================
services/README.txt   [164 lines]
==============================================================================
    no numbered sections

==============================================================================
engine/compare/region/potpourri/solver/README.txt   [155 lines]
==============================================================================
  1000   or more. Any other approach, was exponentially slower. The autho

==============================================================================
test_writing_support/python/README-hwut_runner.txt   [141 lines]
==============================================================================
  1      COMMAND LINE -- THE TWO FRAMEWORK MODES
  2      INTERACTIVE MODE
  3      EXECUTION SCHEMES
  4      BARRIER -- WHAT 'done' GUARANTEES
  5      RESET DISCIPLINE (SEQUENTIAL MODE)
  6      FURTHER CONTENT OF THE MODULE

==============================================================================
engine/orchestrator/README.txt   [136 lines]
==============================================================================
  1      THE STRUCTURE
  2      THE BOOKKEEPER
      2.1    THE NAMING
      2.2    THE BASE
      2.3    RECORDING
      2.4    THE QUERIES
      2.5    THE DIVERGENCE

==============================================================================
engine/bookkeeper/README.txt   [128 lines]
==============================================================================
  1      WHAT IT HOLDS
  2      THE ONE SENTENCE
  3      WHO REFERS TO IT
  4      THE IDS
  5      THE TESTS

==============================================================================
engine/compare/README.txt   [114 lines]
==============================================================================
    no numbered sections

==============================================================================
engine/compare/engine/README-constraint_namespace.txt   [114 lines]
==============================================================================
  1      A NAMESPACE PER TEST RUN
  2      WHAT A CONSTRAINT MAY CONTAIN
  3      WHAT REFUSES AN EXPRESSION
  4      A VARIABLE MAY NOT BE CALLED LIKE A NAME OF THE NAMESPACE
  5      WHERE THE CONSTRAINTS COME FROM

==============================================================================
engine/display/README.txt   [95 lines]
==============================================================================
    no numbered sections

==============================================================================
engine/orchestrator/scheduler/README.txt   [72 lines]
==============================================================================
  1      THE STATE MACHINE  (state.py)
  2      THE SCHEDULER  (scheduler.py)

==============================================================================
auxiliary/README-directory_mutex.txt   [65 lines]
==============================================================================
  1      THE MECHANISM
  2      THE INTERFACE
  3      USERS

==============================================================================
bin/README.txt   [45 lines]
==============================================================================
    no numbered sections

==============================================================================
services/lib/viewers/nvim/README.txt   [43 lines]
==============================================================================
    no numbered sections
