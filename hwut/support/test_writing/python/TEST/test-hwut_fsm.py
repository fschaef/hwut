#! /usr/bin/env python3
#
# @hwut {
#     title      = "hwut_fsm: a state machine as the test's model of the system"
#     choices {
#         syntax    { features = ["fsm-text-model"] }
#         refused   { features = ["fsm-text-model"] }
#         dfa       { features = ["fsm-breach-line"] }
#         nfa       { features = ["fsm-set-of-states"] }
#         forbidden { features = ["fsm-breach-line"] }
#         model     { features = ["fsm-model-questions"] }
#         report    { features = ["fsm-coverage-report"] }
#         masks     { features = ["fsm-changing-law"] }
#     }
# }
#
"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Pin what 'hwut_fsm' prints and answers -- the text of a model, the
         breach lines, a machine of several states at once, the questions a
         tester asks of the model alone, and the coverage report.

CHOICES: syntax, refused, dfa, nfa, forbidden, model, report, masks;

    syntax     a model in text, read and written back ('to_string'); the
               author's own form 'state A ---( ev )---> state B', a chain,
               ':' for the state that began the line above, comments.
    refused    models that cannot be meant, each refused with its line.
    dfa        events fired: allowed, not allowed, never named; 'state',
               'allowed', 'can'.
    nfa        DFA=False: an event leads to several states at once.
    forbidden  a forbidden state entered is said, and entered.
    model      the model alone: unreachable states, dead ends, forbidden
               states the model lets the system reach, shortest paths.
    report     what the events covered of the model; a non-final end.
    masks      the law changing while the machine runs: events disallowed
               and allowed, states forbidden and permitted, for a block;
               the questions under the masks and as written.
______________________________________________________________________________
"""
import sys
import config                                                       # noqa: F401

from hwut.test_writing_support.python.hwut_runner import HwutRunner
from hwut.test_writing_support.python.hwut_fsm    import Machine, FsmError

#  THE PROTOCOL OF EVERY CHOICE: a request is waited on, granted, released;
#  a fault while busy crashes it -- which must never happen.
PROTOCOL = """
    initial:   idle
    forbidden: crashed
    final:     idle
    idle    ---( request )---> waiting ---( grant )---> busy
    busy    ---( release )---> idle
    :       ---( fault )--->   crashed       # the state that began line 6
    waiting ---( cancel )---> idle
"""


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def run_syntax():
    """RETURN: None. Models read from text and written back."""
    banner("the protocol, written back")
    print(Machine.from_string(PROTOCOL).to_string())
    banner("the author's form: 'state', a chain, ':', blanks around '-->'")
    print(Machine.from_string("""
        state A ---( event )---> state B
        :                ---(event2)---> state C ---(event) --> state D
        state E          # no transition yet
    """).to_string())


def run_refused():
    """RETURN: None. Each model that cannot be meant, and why."""
    for text in ("A ---( x )---> B\n: ---( x )---> C",
                 "A ---(  )---> B",
                 ": ---( x )---> B",
                 "A B ---( x )---> C",
                 "initial: A, B\nA ---( x )---> B",
                 "forbidden: Q\nA ---( x )---> B",
                 "# nothing but a comment"):
        banner(text.replace("\n", " | "))
        try:
            Machine.from_string(text)
            print("accepted")
        except FsmError as error:
            print("FsmError: %s" % error)


def run_dfa():
    """RETURN: None. Events fired, one machine."""
    m = Machine.from_string(PROTOCOL)
    for number, event in enumerate(["request", "release", "grant",
                                    "release", "jump", "request"], start=1):
        moved = m.fire(event, where=number)
        print("    %-8s -> %-5s now %-8s allowed: %s"
              % (event, moved, m.state, ", ".join(m.allowed())))
    banner("questions where it stands")
    print("can('grant')  ", m.can("grant"))
    print("can('release')", m.can("release"))
    print("in_state('waiting')", m.in_state("waiting"))
    print("trace:", " ".join("%s:%s>%s" % (w, e, t) for w, _, e, t in m.trace()))


def run_nfa():
    """RETURN: None. DFA=False: several states at once."""
    m = Machine.from_string("""
        A ---( x )---> B ---( y )---> D
        : ---( x )---> C ---( y )---> E
        C ---( z )---> F
    """, DFA=False)
    for event in ("x", "z", "y"):
        m.fire(event, where="t=%s" % event)
        print("    after %s: %s" % (event, ", ".join(sorted(m.current()))))
    banner("'state' asked of a set")
    m.reset(); m.fire("x")
    try:
        print(m.state)
    except FsmError as error:
        print("FsmError: %s" % error)


def run_forbidden():
    """RETURN: None. A forbidden state entered."""
    m = Machine.from_string(PROTOCOL)
    for number, event in enumerate(["request", "grant", "fault"], start=1):
        print("    %-8s -> %s" % (event, m.fire(event, where=number)))
    print("now in", m.state, "-- breaches:", m.breach_n)


def run_model():
    """RETURN: None. The model alone."""
    m = Machine.from_string(PROTOCOL + "\n    state limbo\n    limbo ---( kick )---> idle\n")
    print("check:", m.check())
    banner("path_to")
    for state in ("busy", "crashed", "limbo", "idle"):
        print("    %-8s %s" % (state, m.path_to(state)))
    m.fire("request")
    print("    busy from now:", m.path_to("busy", start="now"))
    print("    state_reachable('idle', start='now'):",
          m.state_reachable("idle", start="now"))


def run_report():
    """RETURN: None. Coverage, and an end outside the final states."""
    m = Machine.from_string(PROTOCOL, name="protocol")
    for event in ("request", "grant", "release", "request", "grant"):
        m.fire(event)
    print("report returns", m.report())


def run_masks():
    """RETURN: None. The law changing while the machine runs."""
    m = Machine.from_string(PROTOCOL)
    banner("'grant' disallowed in every state, since line 2")
    m.disallow("grant", where=2)
    m.fire("request", where=3)
    print("    allowed now:", ", ".join(m.allowed()), "-- can('grant'):",
          m.can("grant"))
    m.fire("grant", where=4)
    print("    path_to('busy'):              ", m.path_to("busy"))
    print("    path_to('busy', masked=False):", m.path_to("busy", masked=False))
    print("    check():", m.check())
    print("    check(masked=False):", m.check(masked=False))
    banner("allowed again; 'busy' forbidden while standing in it")
    m.allow("grant", where=5)
    m.fire("grant", where=6)
    m.forbid("busy", where=7)
    m.fire("release", where=8)
    m.fire("request", where=9)
    m.fire("grant", where=10)
    banner("permitted: 'busy', and the model's own 'crashed'")
    m.permit("busy", where=11)
    m.permit("crashed", where=12)
    print("    fault ->", m.fire("fault", where=13), "-- now in", m.state)
    banner("a phase: 'release' disallowed in 'busy' for a block")
    m.reset()
    m.fire("request"); m.fire("grant")
    with m.disallowed("release", state="busy", where="phase"):
        m.fire("release", where=20)
    m.fire("release", where=21)
    m.disallow("cancel", where=22)
    m.report()
    banner("refused: a word the model never names")
    for call in (lambda: m.disallow("jump"), lambda: m.forbid("limbo"),
                 lambda: m.allow("grant", state="nowhere")):
        try:
            call()
        except FsmError as error:
            print("FsmError: %s" % error)


HwutRunner(
    argv       = sys.argv,
    title      = "hwut_fsm: a state machine as the test's model of the system",
    choice_map = {
        "syntax":    run_syntax,
        "refused":   run_refused,
        "dfa":       run_dfa,
        "nfa":       run_nfa,
        "forbidden": run_forbidden,
        "model":     run_model,
        "report":    run_report,
        "masks":     run_masks,
    },
).run()
