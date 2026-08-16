==============================================================================
orchestrator/plan -- THE TEST PLAN
==============================================================================

This component holds the TEST PLAN and the units that make one: the FORM
(nodes, links, exclusion sets, 'CTestPlan', the printer), the WISH, and the
DETERMINATION that emits a plan out of a wish. Executing a plan is the
scheduler's (orchestrator/scheduler); running a test is test_run's.

The plan stands between determination and the scheduler:

    wish + ExplorationResult          CTestPlan            executions
              |                           |                     |
              v                           v                     v
    +-----------------+        +--------------------+       +---------+
    | DETERMINATION   |------->| SCHEDULER          |------>| test_run|
    | emits the plan  |        | reads and obeys it |       |         |
    +-----------------+        +--------------------+       +---------+

The plan is an INSTRUCTION TO THE SCHEDULER. It states constraints and
admissions, never a total order; the scheduler decides at run time what to
dispatch out of the remaining satisfied work. The plan holds selected test
work only; 'on_entry' and 'on_exit' are the scheduler's frame around it.


1  THE NODES  (form.py)
______________________________________________________________________________

Three kinds, one class, three constructors:

    CPlanNode.test(file, choice, ...)     one (file, choice) call;
                                          'choice' is 'None' for the
                                          choice-less application
    CPlanNode.build(action, ...)          one build action, collected from
                                          test_run's multi-builder
    CPlanNode.session(file, ...)          one interactive application call

'name()' is the node's identity, unique per plan:

    TEST        'file'  or  'file choice'      -- the target form
    BUILD       'build[action]'
    SESSION     'session[file]'

A TEST node carries:

    misdep_f     the dependencies cannot be met: the node is never
                 dispatched and is reported as FAILURE
    provenance   NAMED -- the wish named it; IMPLIED -- implication
                 closure over 'dependency' added it
    implied_by   the target that required it; 'None' on a NAMED node

'payload' holds the constructor's own object; the form never reads it and
the printer never prints it.


2  THE LINKS  (form.py)
______________________________________________________________________________

    ORDERING    'x -> y'      TEST -> TEST. 'x' runs to completion before
                              'y' starts. The verdict of 'x' does not
                              enter.
    SUPPORTS    'w ==> t'     BUILD/SESSION ==> TEST. The verdict-carrying
                              link: 'w' broken, 't' FAILS -- it does not
                              wait.

A SESSION node supports the choices of its own file alone.


3  THE EXCLUSION SETS  (form.py)
______________________________________________________________________________

'CExclusionSet(member_tuple)': at most one member stands at a time. A
member is a target: 'file' -- covering every choice of that file -- or
'file choice'. The order in which the scheduler admits the members is the
scheduler's own, timing-driven decision.


4  CONSTRUCTION LAWS  (form.py)
______________________________________________________________________________

'CTestPlan(node_list, link_list, exclusion_list)' refuses at the door, by
name:

    - two nodes of one name
    - a link endpoint naming no node
    - an ORDERING link whose ends are not both TEST
    - a SUPPORTS link whose source is not BUILD/SESSION, or whose target
      is not TEST
    - a SESSION supporting a choice of another file
    - a cycle in the ORDERING links -- resolved before the plan exists;
      asserted here
    - an ORDERING link leaving a [MISDEP] node for a non-[MISDEP] node
    - an exclusion member covering no TEST node of the plan

Derived at construction, deterministic:

    before_db       TEST name -> names that run to completion first
    supports_db     BUILD/SESSION name -> TEST names it supports
    supporter_db    TEST name -> BUILD/SESSION names supporting it


5  THE PRINT  (printer.py)
______________________________________________________________________________

'print_plan(plan)' emits the canonical text -- what the service 'hwut.plan'
prints. One-way: a print is never read back as input. Order is construction
order throughout. Sections print '(none)' where empty.

    TEST PLAN: 5 node(s), 3 link(s), 1 exclusion set(s)
    NODES
        build[make]     BUILD
        session[t.py]   SESSION
        t.py one        TEST
        t.py two        TEST     [MISDEP]
        u.py            TEST     <= required by t.py one
    LINKS
        u.py -> t.py one
        build[make] ==> t.py one
        session[t.py] ==> t.py two
    EXCLUSIONS
        { t.py, u.py }


6  THE WISH  (wish.py)
______________________________________________________________________________

'parse_wish(argv)' reads the selection keywords off a command line and hands
back a 'Wish' and the arguments that are none of them.

    --fail              the last recorded run's verdict was negative
    --pass              the last recorded run's verdict was positive
    --since=<point>     the last recorded run lies AT or AFTER the
                        point; a case never run is not wanted
    --until=<point>     the last recorded run lies BEFORE the point,
                        and a case never run is wanted too
    --glob <target>     the target form with fnmatch's '*', '?' and
                        '[ ]' in either member; may stand several times

A <point> is a SPAN back from now -- a number and one of 's', 'm', 'h',
'd' -- or an ANCHOR reckoned in UTC: 'today', 'yesterday' (that day,
00:00), 'last-week' (Monday of the week before), 'last-month' (the 1st of
the month before), a weekday (the most recent such day, today counted), a
month (the 1st of the most recent such month, this one counted).
'cutoff_instant(spec, now)' answers the instant a point names.

Several '--glob' occurrences hold ONE question and are OR'ed among
themselves; keywords of different kinds are AND'ed. A wish stating nothing
wants everything; 'str(wish)' writes it back as a command line.

WishError, naming the argument: an unreadable point; '--glob', '--since' or
'--until' without a value; '--fail' beside '--pass'; a span pair whose
'--since'/'--until' window is empty.

The cases a wish selects are answered by 'CTestTaskListQuery'
(exploration/task_list_query.py), an ordinary 'CTestTaskList'. Its domain is
what the directory offers; the Bookkeeper answers the base questions about
those cases and is handed in, never constructed there. A case the base has
never recorded has no last run: '--until=' alone among the base questions
wants it.


7  DETERMINATION  (determine.py)
______________________________________________________________________________

    determine(app_set, task_list, build_interview=None)
        -> (CTestPlan, list[str])

The steps, in order: SELECT through 'task_list.get_test_cases'; IMPLICATION
CLOSURE over 'dependency' to a fixed point, each implied case marked with
the first target that required it; the BUILD INTERVIEW, whose actions become
BUILD nodes with supports links; one SESSION node per interactive file
holding a selected case, supports-linked to that file's TEST nodes; ORDERING
links out of 'dependency' restricted to what stands in the plan; the
collision group as an exclusion set, pruned to the members covering a TEST
node and dropped where fewer than two remain.

Node order: BUILD nodes, then SESSION nodes, then TEST nodes in selection
order. An empty selection yields an empty plan and a report.

'I_BuildInterview.actions(case_list)' answers '(action name, ((file,
choice), ...))'. 'SpecificationBuildInterview' is the answer the
specification alone gives: one action per (file, framework) met, named
'<framework> <file>'.
