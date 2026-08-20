==============================================================================
orchestrator/services -- THE COMMAND LINE FACES
==============================================================================

One file per face; each exports 'main(argv, write) -> int'. 'argv' is the
command line WITHOUT the program's own name; 'write' takes one line at a
time and is 'print' where none is given, so a test drives a face without a
process. Every face answers '--help' with its full documentation and takes
'--directory=<path>', reading the current directory else.

EXIT STATUS, common to every face -- ONE enum, 'E_ExitCode'
('_exit.py'); every face returns its members and nothing else:

    0  OK       nothing refused, nothing failed
    1  FAULT    a fault was met, or a test failed; the face still
                printed what stands
    2  REFUSED  the command line cannot be READ: an unknown option, a
                malformed wish, a directory that does not exist --
                refused at the door, by name, with the usage line
    3  EMPTY    the command line reads, and asks for NOTHING: a wish
                that selects no test, a tree holding no test directory
  141  SIGPIPE  the unix convention 128+13: the reader hung up; the
                face went quiet instead of crashing

The faces:

    hwut.show    (show.py)
                 what the framework READ: the configuration as a tree,
                 syntax checked, defaults resolved. One file's, or the
                 whole directory's. '--no-default' drops what nobody
                 stated; '--provenance' names the place of every stated
                 value; '--gnu' names it as 'file:line:column'. The
                 printed form is the specification language itself and
                 can be read back (R-50).

    hwut.plan    (plan.py)
                 what the framework INTENDS: the test plan -- nodes,
                 links, exclusion sets (see orchestrator/plan). The
                 selection keywords state the wish: '--fail', '--pass',
                 '--since=<point>', '--until=<point>', '--glob
                 <target>' (several times, OR'ed among themselves;
                 kinds AND'ed). A point is a span ('2h') or an anchor
                 ('yesterday', 'last-week', 'monday', 'january'),
                 reckoned in UTC. The plan is printed, never read back:
                 to replay is to re-determine (plan/RATIONALE, P-4).
                 The Bookkeeper is made here and handed down, only
                 where the wish asks the base.

    hwut.run     (run.py)
                 what the framework RUNS: the live tree run. Explores
                 below the root, applies the same wish as 'hwut.plan',
                 dispatches through the real test-run dispatcher, and
                 renders the event stream live in the tier-1 console
                 form (display/plain.py). Four tiers ('--verbose',
                 '--plain', '--quiet', '--silent') and a colour
                 decision ('--colour', '--no-colour') govern the
                 rendering. '--no-store' suppresses recording; '--jobs'
                 bounds parallel work per directory.

A fault does not withhold the output: a directory with one broken header
prints the fault, then the tree or the plan of what stands, and answers 1.


THE CONSOLIDATION: every command line face lives HERE -- one door for
the tool, under ONE NAMING LAW:

    hwut.<name>  <=>  vut/engine/orchestrator/services/<name>.py
                      ('python3 -m vut.engine.orchestrator.services.<name>')
    its suite    <=>  TEST/test-<name>.py or TEST/test-<name>.sh

Every plain '<name>.py' in this directory IS a service; a module that
is NOT a service is underscore-prefixed ('_core.py', '_config.py' --
private helpers of the operations faces). 'show.py' and 'plan.py'
face the orchestrator; 'compare.py', 'merge.py' and 'report.py' face
the operations component. A healing face on a stored subject reads
the Bookkeeper; its run-fallback re-enters the orchestrator -- a face
importing both sides sits above both, which is here.
