==============================================================================
orchestrator/exploration -- SPECIFICATION, EXPLORATION, SELECTION
==============================================================================

This component is the ORCHESTRATOR's reading end. It answers what the
directory offers and what a wish selects out of it; the orchestrator does
the rest. It depends on nothing of the orchestrator's, and the orchestrator
reaches it through one call.

A TEST DIRECTORY holds test applications. A TEST APPLICATION is a file whose
SPECIFICATION states a title and, optionally, named CHOICES. A CHOICE is the
single argument with which the test application is called; the choice name is
the call. The exploration component reads specifications, builds the set of
what exists, and turns a stated wish into the sequence of what runs.

    directory              wish                 sequence
       |                    |                      |
       v                    v                      v
    +----------+        +--------------+       +------------------+
    | EXPLORE  |        | SELECT       |       | ACT              |
    |          |        |              |       |                  |
    | CTestApp |------->| CTestTaskList|------>| CTestCaseSequence|
    |   Set    |        | .get_test_   |       |                  |
    |          |        |  cases(set)  |       | per-choice       |
    | per-app  |        |              |       | elements         |
    +----------+        +--------------+       +------------------+

      what EXISTS         what is ASKED           what RUNS

EXPLORE is a function of the directory alone. SELECT is the only stage that
carries the user's wish. ACT receives elements that require no further
resolution.


1  THE SPECIFICATION LANGUAGE
______________________________________________________________________________

Specifications are written in HOCON. All keys are lowercase. 'hwut' is the
marker: a region opened by it and closed by its matching brace is a
specification. 'title' is the only required key; its presence makes a file a
test application.

    @hwut {
        title    = "..."
        language = "..."

        <test parameters, general>

        choices {
            <choice-name> {
                <test parameters, specific>
            }
        }
    }

The general parameters stand at the root and hold for every choice. A
parameter repeated inside a choice overwrites the general one for that choice
alone. 'title', 'language' and 'choices' are structural: they are not test
parameters and do not participate.

Where no choice needs parameters of its own, 'choices' is written as a list
of names:

    choices = [one, two, three]

which means the same as a map whose bodies are all empty. Where 'choices' is
absent altogether, the specification describes the single choice-less test
application, and its general parameters are that one call's parameters.

A STRING VALUE IS WRITTEN IN DOUBLE QUOTES:

    build   = "make"            choices = ["one", "two"]
    numeric = 0.01              slash   = yes

A bare token is a boolean ('true', 'yes', 'false', 'no'), a number, or a
spelling of nothing ('null', 'nil', 'none', 'nihil', or an empty value), and
it ends at a blank. An unquoted word that is none of those is refused, and
the message shows the word in the quotes it wants.

Keys may stand bare; they are not values. A key carrying a blank -- a target
naming a choice -- carries quotes.

2  THE TEST PARAMETERS
______________________________________________________________________________

One grammar unit. Every key below may appear at the root of a specification
and inside a choice, with the same meaning in both places -- with two
exceptions, marked AT THE ROOT ONLY, which are statements a single choice
cannot make.

    BUILD
        build       the build framework, named alone:

                        build = "make"

                    or the scope:

                        build {
                            framework  = "make"
                            executable = "special.exe"
                            caps { ... }
                        }

                    'framework'  the build framework
                    'executable' the artefact to call; the source file's
                                 stem where unstated
                    'caps'       the caps of the BUILD process

                    '%' in 'framework' and 'executable' is the SOURCE
                    FILE'S STEM (section 4.1). The coverage-capable
                    target is NOT stated here: it is the language's
                    word, 'language-setup.<lang>.coverage_target'
                    (section 7), and a 'coverage_target' inside 'build'
                    is refused by name.

    CANONICALISATION -- the D of Equivalence(D(b_pole), D(b), T)
        pype        pype script that rewrites a stream into canonical
                    form. PYPE-ING IS ONLY EVER APPLIED TO STDOUT --
                    not to stderr (never read as a subject), not to
                    files (not a stream; read whole, after the end).
                    A first word ending in '.pype' is run by the
                    interpreter, whatever the file's she-bang or mode
                    (E-28); any other first word runs as stated.

    WHAT THE TEST PRODUCES
        output      the subjects, in order. Absent: '<stdout>' alone.

                        output = ["<stdout>", "result.csv"]

                    '<stdout>' is the ONE channel name; every other
                    entry is a FILE NAME. Three laws govern here:

                    (1) STDERR IS NEVER SUBJECT TO TESTING. stderr is
                        for ERROR REPORTING; that is its whole job. It
                        is never a nominal, never compared, never
                        pype-d -- '<stderr>' in this list is refused
                        by name. Where error reporting is itself the
                        thing under test, the application FLUSHES IT
                        TO A FILE and names that file here.

                    (2) A FILE IS READ ONLY AFTER THE RUN HAS
                        TERMINATED -- so its content is NOT subject to
                        race conditions: no interleaving to observe,
                        no flush to time. Read, recorded, and REMOVED:
                        the store's record is the product, the file
                        was only the carrier; a stale file can never
                        green a run that stopped producing it.

                    (3) A DECLARED FILE THE RUN DID NOT LEAVE is the
                        verdict 'output-file-not-found', not a
                        silence.

    TOLERANCE -- the T
        numeric     relative numeric tolerance, ratio in [0..1]
        eq-pattern  equivalence patterns; two elements matching one of
                    them are equivalent
        nothing     visible-nothing patterns; a matching element reads
                    as nothing
        analogy     the marker pair:  analogy = ["((", "))"]
        constraints the constraint expressions:
                        constraints = ["x < y + 2",
                                       "abs(sin(z) - x) < epsilon"]
        comment     the marker PAIR of an ignored line, read like
                    'analogy':  comment = ["##", "##"]
        slash_eqv       '/' and '\\' are the same character: the dos and
                        the unix spelling of one path. On by default.
        whitespace_eqv  whitespace of any kind and any extent is the
                        same whitespace. On by default.

    THE FILE'S OWN, AT THE ROOT ONLY
        same         all choices share ONE nominal file. It saves
                     storage, and it facilitates acceptance: one choice
                     is checked and blessed, the rest must follow.
                     Default is off -- nominals differ per choice. A
                     statement about the SET, so 'same' cannot be a
                     choice attribute.
        interactive  the application serves a SESSION -- choices driven
                     over stdin, several per call, no restart per
                     choice. A property of the file's front end.

    EXECUTION
        caps        the caps of the RUN -- procsitter's scope:

                        caps {
                            timeout_sec = 30
                            network     = false
                        }

                    The vocabulary is fixed; an unknown cap is a fault:

                        timeout_sec           wall clock
                        cpu_sec               CPU time
                        memory_mb             address space
                        file_size_mb          largest file written
                        child_process_max_n   children spawned
                        file_handle_max_n     handles held open
                        network               reachability of the world
                        write_directory_list  where it may write; by
                                              default the test source's
                                              directory and below

                    'caps' stands in two places: inside 'build' it caps
                    the build process, at parameter level it caps the run.
                    One noun, one meaning.

                    A cap procsitter cannot enforce on a given platform
                    refuses the test: a cap that does not cap is worse
                    than no cap. The runner's '--ignore=<cap>' runs it
                    anyway, knowingly.


2.1  ABSENCE, OFF, AND THE SCOPE
______________________________________________________________________________

ABSENCE IS NOT OFF. A key that is not written takes the default of the
component that owns it (section 9). 'analogy' unstated means compare's own
marker pair; 'analogy' switched off is written:

    analogy = []            analogy = false            analogy =
    analogy = no            analogy = null

The same five spellings switch 'comment' and 'constraints' off. A marker
pair set to 'true' is refused: it states no markers and leaves nothing to
read.

A key bound to nothing where a value is required -- 'numeric =' --  is
refused with the sentence that names the alternative: leave it unstated for
the default, or name a value.

A SCOPE MERGES FIELD BY FIELD, at every depth. The root is the default and
the choice's own value overwrites -- one level down and every level down:

    root:   caps { timeout_sec = 30   network = false }
    choice: caps { timeout_sec = 5 }
    yields: caps { timeout_sec = 5    network = false }


3  THE THREE CARRIERS
______________________________________________________________________________

A specification reaches the exploration component on one of two carriers.

    HEADER      the specification stands in the source file's own header,
                inside a comment.

    hwut.conf   a file in the TEST directory. Its 'apps' key names test
                application files and carries their specifications.

One file is described by exactly one carrier. 'hwut.conf' describes only
files that carry no header. A file that carries a header and is also named
under 'apps' is a TEST DIRECTORY ERROR.

Nothing above the TEST directory is consulted. 'hwut.propagate global.conf'
webs shared sections into the 'hwut.conf' files of a directory tree; it does
not touch headers. A header is written by hand, always.

    INTERVIEW   neither carrier speaks for the file, and the file
                answers 'app --hwut-info'. Its answer is read as a
                specification. Read: the title, 'CHOICES:', 'HAPPY:'
                (-> eq-pattern), 'SAME;' (-> same), 'INTERACTIVE;'
                (-> interactive).

The interview is the MIGRATION path: an hwut 1.0 test application carries no
'hwut' trigger, because it predates the trigger, and is named under no
'apps' entry. It has always answered '--hwut-info', and that answer is a
specification.

Only what hwut 1.0 defines is read -- the title, 'CHOICES:' and 'HAPPY:' --
and a line beyond that is passed over in silence. A file that does not
answer, answers unreadably, or exits non-zero is not a test application; it
is not a fault.

Exploration therefore EXECUTES, but only here: a file carrying a header and
a file named under 'apps' are never run in order to be read.

4  THE HEADER
______________________________________________________________________________

The region stands inside a comment of the file's own language; no
compiler or interpreter reads it.

    /* @hwut {                              @hwut {
     *     title = "Parser corner cases"       title = "Parser corner cases"
     *     build = "make"                      build = "make"
     *     choices {                           choices {
     *         one { }                             one { }
     *         two { tolerance { numeric_ratio = 0.05 } }              two { tolerance { numeric_ratio = 0.05 } }
     *     }                                   }
     * } */                              }

'hwut.parse' shows what was extracted from a file, how it parsed, and the
effective value of every parameter with its provenance.


4.1  '%' IS THE SOURCE FILE'S STEM
______________________________________________________________________________

Wherever a NAME OR A COMMAND about one test application is stated, '%'
expands to the stem of its source file -- 'test-parse.c' gives
'test-parse' -- and '%%' is one literal '%'. It is admitted in:

    build.framework                        header, 'apps'
    build.executable                       header, 'apps'
    language-setup.<lang>.coverage_target  hwut-root.conf     '%.cov.exe'

It is NOT admitted in 'target { }' of 'hwut.conf': a target is the
directory's word, and a directory has no stem. Nothing else expands it.


5  hwut.conf
______________________________________________________________________________

    @hwut {
        on_entry  = "setup.sh"
        on_exit   = "teardown.sh"
        ignore    = ["*.gen.c"]

        collision = ["test-net.py", "test-port.py two"]

        dependency {
            "test-b.py"     = ["test-a.py"]
            "test-c.py two" = ["test-a.py", "test-b.py one"]
        }

        apps {
            test-gen.c {
                title = "generated parser"
                build = "make"
                choices = [one, two]
            }
        }
    }

'on_entry' and 'on_exit' name scripts run on entering and leaving the
directory. 'ignore' adds glob expressions to those omitted by default:
'*.txt', '*.xml', '*.json'.

'collision' and 'dependency' state how test applications stand to one
another; both are written in TARGETS (section 5.1).

'collision' names the applications that cannot run AT THE SAME TIME. What is
not named may run in parallel. The orchestrator and procsitter may in
addition watch -- lsof and kin -- whether two running applications touch one
resource.

'dependency' names, per target, what must have RUN FIRST. It is an ordering
relation and not a success relation: a dependant runs once its dependencies
have run to completion, whatever their verdict. A cycle is a directory
failure; every case whose dependencies cannot be met reports '[MISDEP]'.

'target' binds the USER-DEFINED TARGETS of 'hwut.target' (services E-7)
in a dictionary of its own -- an open-ended namespace of user-chosen
names, local, never inherited:

    @hwut {
        target {
            clean = "./clean.sh"
        }
    }

'on_entry' and 'on_exit' are STANDARD targets with fixed semantics and
their own top-level keys; a standard name inside 'target { }' is refused
by name. A directory binding any target is walked by 'hwut.target':
definition is membership.


5.1  'default_app'
______________________________________________________________________________

'hwut.conf' may carry a 'default_app' scope of test parameters. Every
application of the directory receives them, and they DO NOT OVERWRITE: what
an application states itself stands.

    @hwut {
        default_app {
            comment = "//"
            caps    { timeout_sec = 5 }
        }
    }

The three sources, outermost first: 'default_app', the application's own
root, the choice. A value taken from 'default_app' reports its provenance
as 'hwut.conf:<line>' (section 7.1).


5.1a  VARIANT GROUPS
______________________________________________________________________________

'hwut-root.conf' may carry 'variant_group { }'. Each GROUP is a DIMENSION of
configuration; each of its alternatives is a point on that dimension.

    variant_group {
        opt  { o0   { build { executable = "%-O0.exe" } }
               o3   { build { executable = "%-O3.exe" } } }
        load { fast { caps { timeout_sec = 30 } }
               slow { caps { timeout_sec = 600 } } }
    }

'--variant=gcov,slow' merges what those alternatives state over the
base -- one alternative per group. A variant states DIFFERENCES only;
what it leaves unstated keeps the base's value, and the order of names
carries no meaning.

    two alternatives of ONE group      REFUSED, naming the group
    a name no group declares           REFUSED, naming what is declared
    one name in TWO groups             REFUSED at the declaration

Within a group the alternatives configure the same parameters; across
groups the subspaces are disjoint (RATIONALE E-9). Every alternative of
every group stands in ONE namespace, so a selection never needs
qualifying.


5.2  TARGETS
______________________________________________________________________________

A TARGET is a file name, or a file name and a choice name with one blank
between -- the call itself:

    test-a.py           every choice of the file
    "test-a.py two"     that one choice

Quotes are needed only where a choice is named, a bare key ending at the
blank.

'apps' carries the specifications of header-less files; an entry uses
the vocabulary of sections 1 and 2, entire and unchanged.

'language-setup' (section 7) and 'apps' hold user-chosen names and
nothing else, as 'choices' does. A user-chosen name never stands beside
a framework key.


6  EXCLUSIVITY
______________________________________________________________________________

    KEY                          HEADER  hwut.conf  hwut-root.conf
    ------------------------------------------------------------------
    title                          x        x          -
    language                       x        x          -
    choices                        x        x          -
    every test parameter (2)       x        x          -

    on_entry, on_exit, ignore      -        x          -
    collision, dependency          -        x          -
    target                         -        x          -
    apps                           -        x          -

    variant_group                  -        -          x
    language-setup                 -        -          x

'on_entry', 'on_exit', 'ignore', 'collision' and 'dependency' are properties
of the directory; no file owns them. A file cannot state what it collides
with or depends on, since the statement is about a PAIR.

THE CLIMB ENDS AT 'TEST/TMP' (R-76). Ascending from a directory that
stands under a test directory's transient root -- a 'TMP' beside a
'GOOD/' -- stops there and finds no root conf: what a run makes under
'TMP/' is outside every tree, and a fixture built there does not read
the enclosing project's 'hwut-root.conf' as its own.

'language-setup' and 'variant_group' are the ROOT'S ALONE (R-73, E-9):
a language's tooling and a run's dimensions are read in one place, and a
nearer 'hwut.conf' stating either is refused by name. 'apps' is the
carrier for header-less files; a header describes one file and needs no
such key.

The root of 'hwut.conf' carries directory keys only. It carries no test
parameters for the directory at large.


7  LANGUAGE
______________________________________________________________________________

THE LANGUAGE IS THE ACTIVATION KEY (R-73). A test application's language
selects ONE ENTRY of 'language-setup' in 'hwut-root.conf', and
everything HWUT does with the file follows from that entry:

    hwut {
        language-setup {
            python   { extensions  = [".py", ".pyw"]
                       interpreter = "python3"
                       coverage    = ["coverage", "slipcover", "trace"] }
            c        { extensions  = [".c"]
                       coverage    = ["gcov", "llvm-cov", "kcov"]
                       coverage_target = "%.cov.exe" }
            dep4711_c { interpreter = "dep4711-run"
                        coverage    = [] }
        }
    }

    extensions       the file extensions that select this entry where a
                     header states no 'language'; each with its dot. An
                     extension two entries claim is refused at the root.
    interpreter      the call for an INTERPRETED test, an argv prefix;
                     the entry's own name where unstated
    coverage         the candidate coverage tools, PREFERENCE ORDER: the
                     first this machine has serves. '[]' is an ANSWER --
                     nobody vouches for a tool (coverage D-2)
    coverage_target  the coverage-capable build target of a COMPILED
                     test, built and run in place of 'build.executable'
                     under 'hwut.cov'; '%' the source file's stem (4.1)
    profiler         declared, not yet consumed

The entry's NAME is the language, and the name is free: 'dep4711_c' is
a language. A file selects it with 'language = "dep4711_c"'.

HOW A FILE'S LANGUAGE IS FOUND, in this order:

    1  the header's (or 'apps' entry's) 'language' word
    2  the entry whose 'extensions' claims the file's extension --
       DERIVED, and said so: 'hwut.show' marks it
    3  none: the file is EXECUTABLE, and its she-bang decides

A language with no 'language-setup' entry is called by its own name
(R-10): 'language = "heartfun"' calls 'heartfun test-app.hf'.

'language-setup' STANDS IN 'hwut-root.conf' AND NOWHERE ELSE. The
framework ships no table: the boundary face writes one when it places
the root conf (services E-25), and 'hwut.show --root-conf-template'
prints that text for pasting into a root conf placed by hand.

'--language=<name>' on every face SELECTS the test applications of a
language; several are a union. It states nothing about any file (R-75).


7.1  WHAT THE FRAMEWORK READ
______________________________________________________________________________

'hwut.parse' prints the complete configuration IN THE SPECIFICATION
LANGUAGE: what is printed can be read back, and the shape an author writes
is the shape he is shown.

    test-a.py {
        title = "Tolerances"
        choices {
            two {
                caps {
                    timeout_sec = 30.0            # app
                    network     = true            # default
                }
                tolerance { numeric_ratio = 0.05 }
                comment = "//"                    # hwut.conf:3
            }
        }
    }

The PROVENANCE stands in a comment, and only where the value is not this
choice's own word:

    (nothing)       the author wrote it here
    app             the application's root, reaching every choice
    hwut.conf:<n>   'default_app', or the 'apps' entry carrying the
                    application; the line is the key's own
    --hwut-info     the application said it through its info block
    default         the component that owns the parameter declared it

'--no-default' drops every line that reads 'default'. What remains is what
somebody stated.

'--provenance' names the PLACE of every stated value instead of the short
word -- 'test-a.py:5' -- the author's own file included.

'--gnu' puts the place at the LINE'S BEGINNING, in the GNU error format,
where an editor's error parser looks for it:

    test-a.py:4:17:             caps {
    test-a.py:4:17:                 timeout_sec = 30.0
    test-a.py:1:9:                  network = true
    test-a.py:4:17:             }
    test-a.py:5:23:             tolerance { numeric_ratio = 0.05 }
    hwut.conf:2:19:             tolerance { slash = false }

The places stand in a column of their own, padded to the longest of them,
and the specification's own indentation stands underneath.

EVERY LINE CARRIES A PLACE. A line with none of its own -- a brace, a title,
a defaulted value -- takes the place of what ENCLOSES it: the scope's first
stated member, else the specification's own head. So every entry in an
editor's error list jumps somewhere the author can edit.

A file whose specification carries a fault prints no tree and its faults
instead -- the service shows what exploration will do, and exploration
refuses rather than guesses.


8  THE READING PIPELINE
______________________________________________________________________________

    source file                          hwut.conf
        |                                    |
    +----------------+                       |
    | DETECTOR       |                       |
    +----------------+                       |
        |                                    |
    +----------------+                       |
    | UNWRAPPER      |                       |
    +----------------+                       |
        |                                    |
        +------------------+-----------------+
                           |
                +----------------------+
                | HOCON PARSER         |   annotated tree
                +----------------------+
                           |
                +----------------------+
                | VALIDATOR            |   refuse, or emit
                +----------------------+
                           |
                       plain tree

THE DETECTOR finds the first occurrence of 'hwut' followed by its brace, at
any position in the file, and the matching closing brace.

THE UNWRAPPER strips the longest common leading prefix of the region's lines
and tolerates a trailing closer on the last line. No table of comment
syntaxes exists; the prefix is discovered. The unwrapper carries the region's
line offset and each line's column offset forward; positions are
file-relative from the start. No position anywhere in the system is
region-relative.

'hwut.conf' enters the pipeline at the HOCON parser; the whole file is the
text.

THE HOCON PARSER produces the ANNOTATED TREE: every key, every value and
every block carries its position in the source file. It does not live here:
it is test-writing support and stands at

    vut/test_writing_support/python/hocon_parser.py

with its own TEST directory. Every supported language is given a parser that
behaves the same way; the Python one's GOOD files are the description the
other ports are measured against. It states its own fault record, which
'reader.py' converts into the engine's.

What stays here is what is HWUT's and not HOCON's: the detector and the
unwrapper know that a specification may live inside a comment, and the
validator knows the vocabulary.

THE VALIDATOR reads the annotated tree, checks it against the vocabulary and
the exclusivity of section 6, and refuses by name with a position. On
acceptance it emits the PLAIN TREE. The annotated tree lives between parser
and validator and nowhere else; no consumer downstream knows it existed.

The plain tree is built of typed, slotted, frozen dataclasses. A field the
author did not state is 'None'.


9  THE RELATION TABLE
______________________________________________________________________________

One table relates HWUT's parameter names to the configuration members that
carry them:

    RELATION = {
        "numeric":          (ConfigCompare, "numeric_tolerance_ratio"),
        "caps.timeout_sec": (ConfigCaps,    "timeout_sec"),
        "tolerance.analogy": (ConfigCompare, ("analogy_f",
                                             "analogy_begin_marker",
                                             "analogy_end_marker"),
                                            ANALOGY),
        ...
    }

It serves both directions:

    write     setattr the parsed values into a fresh configuration
    read      the default the component DECLARES for the member

A configuration is a frozen dataclass, so its default stands in its
declaration and is read without constructing anything. No component
maintains a table for HWUT and none states a default in HWUT's words; a
component takes part by declaring its configuration, and by nothing else.

A plain entry names ONE member. An ADAPTED entry names several and carries
two tiny functions:

    forward     our value      -> {member: value, ...}
    backward    {member: ...}  -> our value

'forward' writes; 'backward' DERIVES the default from the component's own
declarations. Compare declares a flag and two analogy markers; backward
reads all three and hands back the marker pair this vocabulary speaks in.
So no default is restated here, and no component is asked for a second
declaration to keep in step with its own.

A scope of the grammar relates leaf by leaf: 'caps' is HWUT's word for a
group of parameters, 'timeout_sec' is procsitter's word for one of them.

What leaves instantiation is a COMPLETE configuration: every member carries
the value that will apply, and a customer does not hunt for a blank. Where a
component declares 'None', 'None' IS that value: it documents that the thing
is absent -- no build framework, no canonicalisation -- and nothing
substitutes for it.

The RECORD keeps its own 'None's for a different reason: the store must know
what was CHOSEN.

The table is checked AT IMPORT against the classes it names: a member
renamed or a default forgotten in a component fails at the import of
'relation.py', naming parameter, class and member.

A parameter name the table does not carry is refused, not defaulted.

Default provision is part of each owner's contract, and the contract is
checked in TEST/test-defaults.py: the table and the vocabulary cover each
other exactly, every related member exists on its class and declares a
default, and the declared values are printed -- a changed default is a
visible contract change.


10  EXPLORE -- CTestAppSet
______________________________________________________________________________

Exploration reads 'hwut.conf' first: its directory keys govern what follows.
It then reads the headers of the directory's files, omitting the default and
configured ignore globs.

Two things happen per choice.

    RESOLUTION      a general parameter is written into every choice that
                    does not overwrite it. Records are frozen; resolution
                    builds new ones.

    INSTANTIATION   the consumer configurations are built -- compare's
                    Configuration and the rest -- with the default table
                    supplying every field the record leaves 'None'.

The record is kept beside the instantiated configurations. The record says
what the author CHOSE; the configuration says what will happen. The store
records the record, so a default setting adds nothing to an entry and a
deliberate one is recorded the day it is used.

The choice-less specification is normalised at construction into the single
entry 'None'. The list form of 'choices' is normalised into the map form.
Every element therefore has one shape.

    CTestApp("test-myprog.py", { "one": ..., "two": ... })
    CTestApp("test-lonely.sh", { None:  ... })

'CTestAppSet' holds these elements. It states what exists. It carries no
selection and no order.

Where a test application answers '--hwut-info', its reported choices are
compared against the specification and the difference feeds error message
hints. The protocol is not imposed; no answer is not a fault.


11  SELECT -- CTestTaskList
______________________________________________________________________________

    class CTestTaskList:
        def get_test_cases(self, app_set: CTestAppSet) -> CTestCaseSequence

'get_test_cases' is the whole interface. What a 'CTestTaskList' holds and how
it decides is not fixed here: name patterns over applications, named choices,
expected durations, coverage requirements, and further criteria all satisfy
the same signature.

A task that names an application or a choice which 'app_set' does not carry
is refused at the door, by name.


12  ACT -- CTestCaseSequence
______________________________________________________________________________

A 'CTestCase' is one (file, choice) pair together with the record and the
instantiated configurations that apply to it. The choice-less test
application appears as 'CTestCase(file, None, ...)' -- absence is data.

An element carries its own origin ('header' or 'hwut.conf') as a field, and
the position at which its specification begins.

'CTestCaseSequence' is a flat, ordered sequence of such elements. Run, diff,
merge, and accept each act on one element and read nothing else.

CANDIDACY REFUSAL (E-41). 'finder.candidate_list' answers (candidates,
refused): a file whose name matches 'REFUSED_NAME_GLOB_TUPLE' ('*~',
'#*#', '*.bak', '*.backup', '*.orig', '*.old', '*.save', '*.rej',
'*.copy', '*.swp', '*.tmp') is no candidate and is named, with its
reason, in 'ExplorationResult.refused_tuple'. An ignored file ('ignore'
in 'hwut.conf', the default globs) is silent; a refused one is reported.

THE TOLERANCE SCOPE (E-42) holds every lexical tolerance and there is no
second place one may be written:

    tolerance { numeric_ratio  whitespace  slash  regions
                eq_pattern  nothing  analogy  constraints  comment }

Each is a RELATION key 'tolerance.<leaf>', so 'hwut.show' prints it
inside the braces and 'default_of' derives its default from compare's
own declaration. The five that moved in from the root ('eq-pattern',
'nothing', 'analogy', 'constraints', 'comment') are REFUSED where they
stood, by a message naming the new place; 'eq-pattern' is spelled
'eq_pattern' inside the scope, which has one convention.
