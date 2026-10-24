#! /usr/bin/env python3
# @hwut {
#     title    = "HwutRunner as front end: what it answers, and when a session differs from one process per choice"
#     choices {
#         front-end  { features = ["front-end-answers"]
#                      tolerance { constraints = ["framework_unanswered == 0"] } }
#         sequential { features = ["leak-shown"]
#                      tolerance { constraints = ["differ > 0"] } }
#         process    { features = ["byte-exact"]
#                      tolerance { constraints = ["differ == 0"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  the answers of two test applications (../app_argv.py,
         ../app_runner.py) to the framework: per request (front-end), or per
         choice, session against own process (sequential, process)
REQUIREMENT  (1) A test application written with hwut's HwutRunner answers
             the framework's requests from its choice map alone.
             (2) Its interactive session is a pure ACCELERATOR: every
             choice's output equals, byte for byte, the output of the same
             choice run in a process of its own (RATIONALE-hwut_runner).

Under test is the FRONT END of two test applications of the same unit
('../numfmt.py', invoice number formatting per locale): '../app_argv.py'
(a dictionary and sys.argv[1], as most test applications start) and
'../app_runner.py' (HwutRunner; APP_PARALLEL=process selects the forking
scheme). This harness plays the framework: it calls the applications and
speaks the interactive protocol (DOWN 'run <choice> <out> <err>', 'info',
'quit'; UP 'done <choice> <status>', 'info: ...', 'bye').

front-end   one row per request, both applications: a choice, a typo, a
            choice by index, no argument (manual mode, '1' on stdin),
            '--hwut-info', '--interactive'. What HwutRunner buys: the info
            block from the map, 'did you mean', indices, the session --
            none of it written by the author.
sequential  one session, choices de, en, ch run one after the other IN
            ONE PROCESS. numfmt configures its separators once per
            process: en and ch print German separators. The matrix marks
            them DIFFERS and shows the lines. This is a real bug of numfmt
            that one-process-per-choice hid; note that 'hwut.run' serves
            the choices from one session ('interactive = true'): a GOOD
            recorded with one process per choice would then fail.
process     the same session with parallel="process": each choice in a
            fork of the session's start state -- every choice equal.

HOW TO READ THE GOOD   front-end: the request ('(framework)' where hwut
itself sends it), then each application's exit status, whether it answered
from the choice map, and its first lines; the framework requests that
app_runner.py leaves unanswered are a binding, law '== 0'. Sessions: the
DOWN/UP transcript (in process mode the 'done' lines stand in a
'potpourri': forks finish in any order; sequential mode keeps its one
order), then one row per choice, own process vs session: 'equal' or
'DIFFERS' with the differing lines; the differing choices are a binding,
'((differ: N))', judged by the choice's law. Temporary sink paths are not
printed.
______________________________________________________________________________
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
UNIT = os.path.join(HERE, "..")
APPS = [("app_argv.py", os.path.join(UNIT, "app_argv.py")),
        ("app_runner.py", os.path.join(UNIT, "app_runner.py"))]
CHOICES = ["de", "en", "ch"]


def call(app, args, stdin="", env=None):
    p = subprocess.run([sys.executable, app] + args, input=stdin, capture_output=True, text=True,
                       env=dict(os.environ, **(env or {})))
    return p.returncode, (p.stdout + p.stderr).splitlines()


def front_end():
    runs_de = lambda rc, lines: rc == 0 and any(l.startswith("de ") for l in lines)
    # (title, argv, stdin, asked by the framework?, what answers it from the choice map)
    requests = [("a choice", ["de"], "", True, runs_de),
                ("a typo", ["dee"], "", False, lambda rc, lines: any("'de'" in l for l in lines)),
                ("a choice by index", ["1"], "", False, runs_de),
                ("no argument, '1' on stdin", [], "1\n", False, runs_de),
                ("--hwut-info", ["--hwut-info"], "", True,
                 lambda rc, lines: rc == 0 and any(l.startswith("CHOICES:") for l in lines)),
                ("--interactive: 'info', 'quit'", ["--interactive"], "info\nquit\n", True,
                 lambda rc, lines: rc == 0 and "bye" in lines and any(l.startswith("info: CHOICES:") for l in lines))]
    print("answered: 'yes' where the reply comes from the choice map (runs the choice,")
    print("names it, or lists the map); (framework) marks a request hwut itself sends")
    print()
    unanswered = 0
    for title, args, stdin, framework, answers in requests:
        print("request: %s   (%s)%s" % (title, " ".join(args) or "no argument",
                                        "   (framework)" if framework else ""))
        for name, app in APPS:
            rc, lines = call(app, args, stdin)
            shown = lines[:5]
            ok = answers(rc, lines)
            if framework and name == "app_runner.py" and not ok:
                unanswered += 1
            print("    %-14s exit %d   answered: %s" % (name, rc, "yes" if ok else "no"))
            for line in shown:
                print("        | %s" % line)
            if len(lines) > len(shown):
                print("        | ... %d more line(s)" % (len(lines) - len(shown)))
        print()
    print("framework requests app_runner.py leaves unanswered ((framework_unanswered: %d))   law == 0   %s"
          % (unanswered, "kept" if unanswered == 0 else "BROKEN"))


def session(parallel):
    env = {"APP_PARALLEL": parallel} if parallel else {}
    normal = dict((c, call(APPS[1][1], [c], env=env)[1]) for c in CHOICES)
    with tempfile.TemporaryDirectory() as sinks:
        down = []
        for c in CHOICES:
            down.append("run %s %s %s" % (c, os.path.join(sinks, c + ".out"), os.path.join(sinks, c + ".err")))
        down += ["quit"]
        p = subprocess.run([sys.executable, APPS[1][1], "--interactive"], input="\n".join(down) + "\n",
                           capture_output=True, text=True, env=dict(os.environ, **env))
        interactive = dict((c, open(os.path.join(sinks, c + ".out")).read().splitlines()) for c in CHOICES)
    print("session: app_runner.py --interactive, parallel=%s" % (parallel or "None (sequential)"))
    for c in CHOICES:
        print("    DOWN  run %s <sink-out> <sink-err>" % c)
    print("    DOWN  quit")
    up = p.stdout.splitlines()
    if parallel:                         # forks finish in any order
        print("##! potpourri")
    for line in up:
        if line.startswith("done"):
            print("    UP    " + line)
    if parallel:
        print("####")
    for line in up:
        if not line.startswith("done"):
            print("    UP    " + line)
    print()
    print("  choice   own process   session")
    differ = 0
    for c in CHOICES:
        same = normal[c] == interactive[c]
        differ += not same
        print(("  %-8s %d lines       %-9s %s"
               % (c, len(normal[c]), "equal" if same else "DIFFERS", "" if same else "!!")).rstrip())
        if not same:
            for a, b in zip(normal[c], interactive[c]):
                if a != b:
                    print("           own process: %-24s session: %s" % (a, b))
    print()
    print("choices printing differently in the session ((differ: %d))   law == 0   %s"
          % (differ, "kept: the session is a pure accelerator" if not differ
             else "BROKEN: state leaks between choices"))


CHOICE_DB = {"front-end": front_end, "sequential": lambda: session(None),
             "process": lambda: session("process")}

if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in CHOICE_DB:
        print("choices: %s" % ", ".join(CHOICE_DB))
        sys.exit(1)
    CHOICE_DB[choice]()
    print("<hwut-end>")
