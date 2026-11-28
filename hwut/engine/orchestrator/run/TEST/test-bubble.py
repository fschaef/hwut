#! /usr/bin/env python3
#
# @hwut {
#     title      = "Which bubble runs where: S, Q(B), F(B) decided before the first event"
#     choices {
#         local     { features = ["bubble-decided", "bubble-inner-decided-alone"] }
#         refused   { features = ["bubble-refused"] }
#         first     { features = ["bubble-decided"] }
#         below     { features = ["bubble-decided"] }
#         header    { features = ["bubble-decided"] }
#         excluded  { features = ["bubble-decided", "bubble-not-run-untouched"] }
#         handed    { features = ["bubble-handed-hides-inner"] }
#         untouched { features = ["bubble-not-run-untouched"] }
#         stream    { features = ["bubble-handed-run-there"] }
#         sigterm   { features = ["bubble-handed-ended"] }
#         play      { features = ["bubble-play-decided"] }
#         book      { features = ["bubble-book-says-where"] }
#         far-empty { features = ["bubble-far-empty-no-fault"] }
#         probe     { features = ["bubble-local-probed"] }
#         label     { features = ["bubble-decided"] }
#     }
#     tolerance { eq_pattern = ["SUCCESS.*"] }
# }
#
"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE DECISION OF adm/WORK/spec/42-platforms.txt section 3 (plan/42
         P-4; intend/42 rulings 12, 19, 21; intend/26 o-50 .. o-58) on one
         tree:

    .                 platform = [ { local  tools = [iverilog] },
                                   { linux  tools = [iverilog, ghdl] } ]
                      no 'requires'                          C = {local}
    ./TEST            test-top.sh
    none/             hwut.conf, no 'requires'               C = {local}
    linux/            requires = [ ghdl ]                    C = {linux}
    linux/inner/      hwut.conf, inherits ghdl (o-57)        C = {linux}
    both/             requires = [ iverilog ]                C = {local, linux}

CHOICES: local, refused, first, below, header, excluded, handed,
         untouched, stream, sigterm, play, book, far-empty, probe,
         label;

MEASURED BEFORE (ruled 2026-11-26, platforms RATIONALE): S was {local}
without a platform word, '-p' ADDED; now every defined platform is
specified, '-p' NARROWS, '--exclude-platform' takes one out, and a
platform a wanted directory needs that cannot be made ready REFUSES the
run before it begins. The choices below say S as they did before by
'--exclude-platform linux' and '-p local -p linux'.

local      S = {local}: '.', none/, both/ run here; linux/ NOT RUN,
           'available', and linux/inner/ with it: it inherits ghdl
           (intend/45 R-4; no inner root, nothing replaces).
refused    REFUSED at the call, named, nothing explored: a 'platform' in
           a hwut.conf below the root (o-53); a tool 'HWUT_ROOT/tools.rst'
           beside the root does not explain (o-52).
first      the FIRST DEFINED wins, '-p' narrows and never orders (o-58):
           '-p local -p linux' -- both/ runs here, 'local' defined
           first; the definitions swapped -- both/ goes to linux.
below      a 'hwut.conf' below none/ requires ghdl, which 'local' does
           not announce: that directory is decided on its own (intend/45
           R-4) -- for linux, not specified: NOT RUN 'available'; its
           sibling runs.
header     a test's header requires ghdl, a choice's iverilog, another
           choice's ghdl (o-59): 'hwut.run' refuses the cases 'local'
           cannot hold, named in REFUSED, uncounted; the rest run;
           'hwut.play' of a refused one says the same, REFUSED.
excluded   '--exclude-local -p linux', S = {linux}, a podman stand-in
           first on PATH answering 1 -- the image absent, no recipe:
           REFUSED before the run, 'PLATFORM missing: linux', the reason
           and '--exclude-platform linux'; nothing explored. A recipe
           standing, the image not made from it: the same refusal, the
           start's reason (ruled 2026-11-26).
handed     the same, the stand-in answering 0 -- the image stands:
           linux/ and both/ HANDED in ONE far run (intend/45 R-4): the
           root, the far run's words ('--as-platform=linux' and the near
           run's platform words) -- over there every directory is decided
           alike, and those decided for linux run.
label      S = {local, linux}, linux not reachable, a label asked: a
           directory of which the label selects no run does not need
           its platform. 'HWUT_ROOT/labels.txt' naming test-b.sh: '-l
           on_linux' REFUSED; '-l "NOT on_linux"' REFUSED too -- of
           linux/inner/TEST, no book and no labelled run, the runs are
           not known, and a run without a label answers 'NOT'. Naming
           test-c.sh as well: '-l "NOT on_linux"' planned without linux,
           '-l on_linux' REFUSED. 'hwut.help': the PLATFORM part -- why,
           the two directories, '--exclude-platform', the anti-label's
           command (ruled 2026-11-27, platforms PL-3).
untouched  'hwut.run' itself, each S: the stream's 'not-run' lines, the
           RESULTS, and every file below a bubble not run -- the same
           before and after: no book, no 'TMP/', no 'OUT/' (ruling 21).
           No platform word, linux not reachable: REFUSED, and nothing
           written anywhere.

stream     the hand-over, real: a 'podman' that is this machine ('run'
           changes to '-w' and executes the words after the image).
           'hwut.run --exclude-local -p linux' against the far run's own
           words run here at the root ('--as-platform=linux --exclude-
           local -p linux'): the same verdict per case, each near one
           carrying 'platform' -- both/, linux/ and linux/inner/ in ONE
           far run (intend/45 R-4).
sigterm    the near run ended by SIGTERM while the far run sleeps: the
           near run ends (128 + 15), the far process with it (E-55).
play       'hwut.play' decides its directory as 'hwut.run' does
           (ruled 2026-11-03, "yes to play"): in linux/TEST with
           '--exclude-platform linux', not run -- the NOTE, EMPTY;
           without a platform word, and with '--exclude-local -p linux',
           handed -- the far play's lines relayed, its recording on this
           disk; in both/TEST with '-p local -p linux', played here
           ('local' is defined first, o-58); in none/TEST, as ever.
far-empty  a wish that selects NOTHING over there (the author's run,
           2026-11-04): 'hwut.run --exclude-local -p linux --dir
           linux/nowhere' -- the far run ends EMPTY (3), and that is no
           fault of the platform's: no 'fault' event, nothing counted,
           the near run EMPTY as well. MEASURED before: 'ERROR linux/:
           platform 'linux' ended with status 3'.
book       after 'hwut.run' and 'hwut.run --exclude-local -p linux': each
           book's rows -- the platform's name last where linux measured
           the verdict, nothing where this machine did -- and
           'hwut.report', which reads the books and takes no '-p' (ruling
           21): '(linux)' beside a case linux measured; in JSON, its
           'platform'.

probe      the declaration is the contract (intend/45 R-5, amending
           E-226, 2026-11-15): 'HWUT_ROOT/tools.rst' gives iverilog 'probe:
           hwut-bubble-probe'. Not on PATH: both/ and a directory below
           none/ requiring iverilog run here as declared, their cases
           FAIL 'platform local does not provide tool iverilog', the
           program named. A stand-in first on PATH: they run. ghdl has
           no 'probe:' line: linux/ keeps its words. MEASURED before
           (4e03ee5, the author's machine): 'local' declaring iverilog
           without it installed -- 'build failed', 10 cases 'unexpected
           stderr'.

EXPLORED counts the walk's own 'explore' per test directory: zero for a
directory of a bubble not run -- nothing of it interviewed or read.
______________________________________________________________________________
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import config                                                     # noqa F401
from   config import HwutRunner                                   # noqa E402
from hwut.engine.orchestrator.exploration import tree_explorer   # noqa E402
from hwut.engine.orchestrator.plan.wish import parse_wish        # noqa E402
from hwut.engine.orchestrator.run.orchestrate import orchestrate  # noqa E402
from hwut.engine.orchestrator.exploration.task_list import \
                                              SelectionError      # noqa E402

LINUX = ('{ name = "linux", kind = "container", image = "hwut-dev", '
         'recipe = "Containerfile", tools = ["iverilog", "ghdl"] }')
BIN   = os.path.join(config.HWUT_DIRECTORY, "bin")


def seconds_cut(line):
    """RETURN: str, 'line' without the seconds a RESULTS line ends in --
    the machine's, never the page's."""
    return re.sub(r", [0-9.]+ \[sec\].*$", "", line)


LOCAL = '{ name = "local", tools = ["iverilog"] }'


def tree(definitions=None, none_text=""):
    """RETURN: str, the root of a new tree as the PURPOSE draws it --
    'definitions' the root's 'platform' list where given, 'none_text'
    what none/'s root conf says."""
    root = tempfile.mkdtemp(prefix="hwut_bubble_")
    conf_db = {"": "platform = [ %s ]"
                   % (definitions or "%s, %s" % (LOCAL, LINUX)),
               "none/": none_text,
               "linux/": 'requires = ["ghdl"]',
               "linux/inner/": "",
               "both/": 'requires = ["iverilog"]'}
    test_db = {"TEST": "test-top.sh", "none/TEST": "test-a.sh",
               "linux/TEST": "test-b.sh", "linux/inner/TEST": "test-c.sh",
               "both/TEST": "test-d.sh"}
    for where, text in conf_db.items():
        #  ONE ROOT, hwut.conf BELOW IT (intend/45 R-1, R-4).
        os.makedirs(os.path.join(root, where), exist_ok=True)
        name = "HWUT_ROOT/setup.conf" if where == "" else "hwut.conf"
        os.makedirs(os.path.dirname(os.path.join(root, where, name)), exist_ok=True)
        with open(os.path.join(root, where, name), "w") as fh:
            fh.write("hwut {\n    %s\n}\n" % text)
    for where, name in test_db.items():
        os.makedirs(os.path.join(root, where, "GOOD"))
        path = os.path.join(root, where, name)
        with open(path, "w") as fh:
            fh.write('#! /bin/sh\n# @hwut { title = "%s" }\necho %s\n'
                     'echo "<hwut-end>"\n' % (name, name))
        os.chmod(path, 0o755)
        with open(os.path.join(root, where, "GOOD", name + ".txt"), "w") as fh:
            fh.write("%s\n<hwut-end>\n" % name)
    return root


class Counted:
    """The walk's 'explore', counted per directory, then done as ever."""

    def __init__(self, root):
        """RETURN: None. Counts kept per directory relative to 'root'."""
        self.root, self.count_db = root, {}
        self.original = tree_explorer.explore

    def __call__(self, directory, *argument_list, **argument_db):
        """RETURN: what 'explore' returns; the call counted."""
        name = os.path.relpath(directory, self.root).replace(os.sep, "/")
        self.count_db[name] = self.count_db.get(name, 0) + 1
        return self.original(directory, *argument_list, **argument_db)


def decided(root, argv, path=None, label_view=None):
    """
    RETURN: None. 'orchestrate' over 'root' for the wish 'argv' (PATH set
            to 'path' where given): each bubble not run, the directories
            planned, and per test directory how often it was explored --
            or the refusal.
    """
    print("$ %s" % (" ".join(argv) or "(no -p)"))
    wish, _ = parse_wish(argv, platform_f=True)
    counted = Counted(root)
    tree_explorer.explore = counted
    old_path = os.environ["PATH"]
    if path is not None: os.environ["PATH"] = path
    try:
        tree_plan = orchestrate(root, wish, label_view=label_view)
    except SelectionError as error:
        print("    REFUSED: %s"
              % re.sub(r"\S*/hwut_bubble_\w+", "<root>",
                       str(error).replace(root, "<root>")))
        print("    EXPLORED: %s" % (sorted(counted.count_db) or "nothing"))
        return
    finally:
        tree_explorer.explore = counted.original
        os.environ["PATH"] = old_path
    for decision in tree_plan.not_run_tuple:
        print("    not-run  %-14s %-10s %-9s %s"
              % (decision.name, decision.platform or "''", decision.reason,
                 decision.text.replace(root, "<root>")))
    for decision, far_argv in tree_plan.handed_tuple:
        print("    handed   %-14s %-10s far: hwut.run %s"
              % (decision.name, decision.platform, " ".join(far_argv)))
        print("             takes: %s" % ", ".join(decision.directory_tuple))
    print("    PLANNED: %s" % ", ".join(e.directory for e in tree_plan))
    for name in ("TEST", "none/TEST", "linux/TEST", "linux/inner/TEST",
                 "both/TEST"):
        print("    EXPLORED %-18s %i" % (name, counted.count_db.get(name, 0)))
    for line in tree_plan.warning_tuple: print("    %s" % line)
    #  A PLATFORM LACKING WHAT IT DECLARES (intend/45 R-5): the cases that
    #  fail, not run, with the reason.
    from hwut.engine.orchestrator.plan.bubble import tool_absent_refusal_f
    for entry in tree_plan:
        for name, reason in entry.refused_tuple:
            if tool_absent_refusal_f(reason):
                print("    FAIL     %s %s -- %s" % (entry.directory, name,
                                                     reason))


def podman_bin(status):
    """
    RETURN: str, a new directory holding a 'podman' stand-in that answers
            'status' to every call: 0, the image stands; 1, it does not
            -- and the tree holds no recipe, so the platform cannot be
            reached. Put FIRST on PATH, it is found before any engine the
            machine has; PATH is never narrowed (E-197).
    """
    directory = tempfile.mkdtemp(prefix="hwut_bubble_bin_")
    with open(os.path.join(directory, "podman"), "w") as fh:
        fh.write("#! /bin/sh\nexit %i\n" % status)
    os.chmod(os.path.join(directory, "podman"), 0o755)
    return directory


def first_on_path(directory):
    """RETURN: str, PATH with 'directory' put first."""
    return directory + os.pathsep + os.environ["PATH"]


def test_local():
    """RETURN: None. S = {local}."""
    root = tree()
    try:
        decided(root, ["--exclude-platform", "linux"])
    finally:
        shutil.rmtree(root)
    print("SUCCESS: decided, the inner bubble of a bubble not run run here.")


def test_refused():
    """RETURN: None. Confs refused at the start."""
    root = tree(none_text="platform = [ %s ]" % LOCAL)
    try:
        decided(root, [])
    finally:
        shutil.rmtree(root)
    root = tree()
    try:
        os.makedirs(os.path.join(root, "HWUT"), exist_ok=True)
        os.makedirs(os.path.join(root, "HWUT_ROOT"), exist_ok=True)
        with open(os.path.join(root, "HWUT_ROOT/tools.rst"), "w") as fh:
            fh.write("[[iverilog]]\n    Icarus Verilog.\n")
        decided(root, [])
    finally:
        shutil.rmtree(root)
    print("SUCCESS: refused at the call, every such conf named.")


def test_first():
    """RETURN: None. The first defined, '-p' narrowing."""
    bin_dir = podman_bin(0)          # the image stands: linux/ handed
    root = tree()
    try:
        decided(root, ["-p", "local", "-p", "linux"], first_on_path(bin_dir))
    finally:
        shutil.rmtree(root)
    root = tree(definitions="%s, %s" % (LINUX, LOCAL))
    try:
        decided(root, ["-p", "local", "-p", "linux"], first_on_path(bin_dir))
        decided(root, ["-p", "local"])
    finally:
        shutil.rmtree(root); shutil.rmtree(bin_dir)
    print("SUCCESS: the first defined of those specified.")


def test_below():
    """RETURN: None. A directory requiring more than its platform holds."""
    root = tree()
    try:
        for where in ("none/deep", "none/shallow"):
            os.makedirs(os.path.join(root, where, "TEST", "GOOD"))
            path = os.path.join(root, where, "TEST", "test-e.sh")
            with open(path, "w") as fh:
                fh.write('#! /bin/sh\n# @hwut { title = "E" }\n'
                         'echo e\necho "<hwut-end>"\n')
            os.chmod(path, 0o755)
        with open(os.path.join(root, "none/deep/hwut.conf"), "w") as fh:
            fh.write('hwut { requires = ["ghdl"] }\n')
        decided(root, ["--exclude-platform", "linux"])
    finally:
        shutil.rmtree(root)
    print("SUCCESS: the directory not entered, its sibling run.")


def test_header():
    """RETURN: None. A test's header requiring a tool."""
    root, bin_dir = tree(), podman_bin(1)
    environment = dict(os.environ, PATH=first_on_path(bin_dir),
                       PYTHONPATH=os.path.dirname(config.HWUT_DIRECTORY))
    try:
        where = os.path.join(root, "none", "TEST")
        for name, header, good in (
                ("test-g.sh", 'title = "G"  requires = ["ghdl"]', "g"),
                ("test-h.sh", 'title = "H"  choices { one { requires = '
                              '["iverilog"] } two { requires = ["ghdl"] } }',
                 None)):
            path = os.path.join(where, name)
            with open(path, "w") as fh:
                fh.write('#! /bin/sh\n# @hwut { %s }\necho "$1"\n'
                         'echo "<hwut-end>"\n' % header)
            os.chmod(path, 0o755)
            for stem in ([name] if good else
                         ["%s--one" % name, "%s--two" % name]):
                with open(os.path.join(where, "GOOD", stem + ".txt"),
                          "w") as fh:
                    fh.write("%s\n<hwut-end>\n"
                             % (good or stem.rsplit("--", 1)[1]))
        done = subprocess.run([sys.executable, "-m", "hwut.services.run",
                               "--plain", "--jobs=1", "--exclude-platform",
                               "linux"], cwd=root,
                              env=environment, capture_output=True,
                              text=True)
        print("$ hwut.run --exclude-platform linux   [exit %i]"
              % done.returncode)
        show_f = False
        for line in done.stdout.splitlines():
            if line.startswith("REFUSED"): show_f = True
            if show_f and line.strip() and not line.startswith("="):
                print("    %s" % seconds_cut(line.replace(root, "<root>")))
            if line.startswith("RESULTS"): show_f = False
        done = subprocess.run([sys.executable, "-m",
                               "hwut.services.lib.run.play", "--plain",
                               "--exclude-platform", "linux",
                               "test-h.sh", "two"], cwd=where,
                              env=environment, capture_output=True,
                              text=True)
        print("$ (none/TEST) hwut.play --exclude-platform linux test-h.sh "
              "two   [exit %i]"
              % done.returncode)
        for line in (done.stdout + done.stderr).splitlines():
            print("    %s" % line.replace(root, "<root>"))
    finally:
        shutil.rmtree(root); shutil.rmtree(bin_dir)
    print("SUCCESS: the cases this platform cannot hold refused, named.")


def test_excluded():
    """RETURN: None. S = {linux}, the image absent: no recipe, then a
    recipe from which no image is made."""
    root, bin_dir = tree(), podman_bin(1)
    try:
        decided(root, ["--exclude-local", "-p", "linux"],
                first_on_path(bin_dir))
        with open(os.path.join(root, "Containerfile"), "w") as fh:
            fh.write("FROM nowhere\n")
        decided(root, ["--exclude-local", "-p", "linux"],
                first_on_path(bin_dir))
    finally:
        shutil.rmtree(root); shutil.rmtree(bin_dir)
    print("SUCCESS: a platform missing refused before the run; nothing "
          "explored of it.")


def test_handed():
    """RETURN: None. S = {linux}, the image stands."""
    root, bin_dir = tree(), podman_bin(0)
    try:
        decided(root, ["--exclude-local", "-p", "linux"],
                first_on_path(bin_dir))
    finally:
        shutil.rmtree(root); shutil.rmtree(bin_dir)
    print("SUCCESS: handed; the inner bubble decided over there.")


def listing(root, below_tuple):
    """RETURN: list of str, every file below the directories 'below_tuple'
    of 'root', relative, sorted -- a bubble's inner bubble left out."""
    found = []
    for below in below_tuple:
        for here, name_list, file_list in os.walk(os.path.join(root, below)):
            name_list[:] = sorted(n for n in name_list if n != "inner")
            for name in file_list:
                found.append(os.path.relpath(os.path.join(here, name), root))
    return sorted(found)


def test_untouched():
    """RETURN: None. 'hwut.run' itself: nothing of a bubble not run."""
    root, bin_dir = tree(), podman_bin(1)
    environment = dict(os.environ, PATH=first_on_path(bin_dir),
                       PYTHONPATH=os.path.dirname(config.HWUT_DIRECTORY))
    try:
        for argv, below_tuple in ((["--exclude-platform", "linux"], ("linux",)),
                                  ([], ("TEST", "none", "linux", "both")),
                                  (["--exclude-local", "-p", "linux"],
                                   ("TEST", "none", "linux", "both"))):
            before = listing(root, below_tuple)
            done = subprocess.run([sys.executable, "-m", "hwut.services.run",
                                   "--plain", "--jobs=1"] + argv, cwd=root,
                                  env=environment, capture_output=True,
                                  text=True)
            print("$ hwut.run %s   [exit %i]"
                  % (" ".join(argv) or "(no -p)", done.returncode))
            for line in done.stdout.splitlines():
                if line.startswith(("NOTE  ", "RESULTS", "    (no directory",
                                    "REFUSED", "         =>")):
                    print("    %s" % seconds_cut(line.replace(root, "<root>")))
            after = listing(root, below_tuple)
            print("    below %s: %i file(s) before, %i after%s"
                  % (", ".join(below_tuple), len(before), len(after),
                     "" if before == after
                     else "  -- NEW: %s" % sorted(set(after) - set(before))))
    finally:
        shutil.rmtree(root); shutil.rmtree(bin_dir)
    print("SUCCESS: a bubble not run leaves no trace.")


_HERE_PODMAN = """#! %s
# A CONTAINER THAT IS THIS MACHINE: 'image inspect' stands; 'run' changes to
# '-w' and executes the words after the image, as the image would.
import os, sys
argv = sys.argv[1:]
if argv[:2] == ["image", "inspect"]: sys.exit(0)
i, cwd = 1, None
while i < len(argv):
    word = argv[i]
    if word in ("-v", "-e", "--user"): i += 2; continue
    if word == "-w": cwd = argv[i + 1]; i += 2; continue
    if word.startswith("-"): i += 1; continue
    break
command = argv[i + 1:]
os.chdir(cwd)
%s
os.execvp(command[0], command)
"""


def here_podman_bin(before=""):
    """
    RETURN: str, a new directory holding the 'podman' that is this machine
            -- 'before' a line of Python run before the far command is
            executed.
    """
    directory = tempfile.mkdtemp(prefix="hwut_bubble_here_")
    path = os.path.join(directory, "podman")
    with open(path, "w") as fh: fh.write(_HERE_PODMAN % (sys.executable, before))
    os.chmod(path, 0o755)
    return directory


def run_with_events(where, argv, environment):
    """
    RETURN: (int, list of dict, str), 'hwut.run' in 'where' with 'argv':
            its exit status, its events (read back from '--events'), its
            RESULTS line without the seconds.
    """
    from hwut.engine.protocol.line import event_of
    event_path = os.path.join(tempfile.mkdtemp(prefix="hwut_bubble_ev_"),
                              "events.txt")
    done = subprocess.run([sys.executable, "-m", "hwut.services.run",
                           "--plain", "--jobs=1", "--events", event_path]
                          + argv, cwd=where, env=environment,
                          capture_output=True, text=True)
    with open(event_path) as fh:
        event_list = [event_of(line) for line in fh if line.strip()]
    shutil.rmtree(os.path.dirname(event_path))
    results = [line for line in done.stdout.splitlines()
               if line.startswith("RESULTS")]
    return done.returncode, event_list, \
           (seconds_cut(results[0]) if results else "(no RESULTS)")


def verdict_list(event_list, prefix=""):
    """RETURN: list of str, '<directory> <node> <verdict> <platform>' per
    'run-ended' of 'event_list', 'prefix' put before each directory,
    sorted."""
    return sorted("%s %s %s %s" % (os.path.normpath(os.path.join(
                                       prefix, item["directory"])),
                                   item["node"], item["verdict"],
                                   item.get("platform", "-"))
                  for item in event_list if item["kind"] == "run-ended")


def test_stream():
    """RETURN: None. The hand-over against a local run of the bubble."""
    root, bin_dir = tree(), here_podman_bin()
    environment = dict(os.environ, PATH=first_on_path(bin_dir),
                       PYTHONPATH=os.path.dirname(config.HWUT_DIRECTORY))
    try:
        near_code, near_list, near_results = run_with_events(
            root, ["--exclude-local", "-p", "linux"], environment)
        #  THE FAR RUN'S OWN WORDS, run here (intend/45 R-4): at the
        #  project's root, '--as-platform=linux' and the near run's
        #  platform words -- it takes exactly what was decided for linux.
        for name in ("TMP", "OUT"):
            for here, name_list, _ in os.walk(root):
                if name in name_list:
                    shutil.rmtree(os.path.join(here, name))
        local_code, local_list, local_results = run_with_events(
            root, ["--as-platform=linux", "--exclude-local", "-p", "linux"],
            environment)
    finally:
        shutil.rmtree(root); shutil.rmtree(bin_dir)
    near_far = verdict_list(near_list)
    local_far = verdict_list(local_list)
    print("near  [exit %i] %s" % (near_code, near_results))
    for line in near_far: print("    %s" % line)
    print("local [exit %i] %s   (the far run's words, at the root)"
          % (local_code, local_results))
    for line in local_far: print("    %s" % line)
    ok_f = [line.rsplit(" ", 1)[0] for line in near_far] \
           == [line.rsplit(" ", 1)[0] for line in local_far] \
           and all(line.endswith(" linux") for line in near_far) \
           and "linux/inner/TEST test-c.sh ok linux" in near_far
    print("%s: what runs there is what runs here, but for 'platform'; one "
          "far run takes every directory decided for linux."
          % ("SUCCESS" if ok_f else "FAILURE"))


def test_sigterm():
    """RETURN: None. A near run ended while its far run sleeps."""
    import signal
    import time
    root = tree()
    pid_path = os.path.join(root, "far.pid")
    bin_dir = here_podman_bin(
        "open(%r, 'w').write(str(os.getpid())); import time; "
        "time.sleep(60)" % pid_path)
    environment = dict(os.environ, PATH=first_on_path(bin_dir),
                       PYTHONPATH=os.path.dirname(config.HWUT_DIRECTORY))
    try:
        near = subprocess.Popen([sys.executable, "-m", "hwut.services.run",
                                 "--plain", "--exclude-local", "-p", "linux"],
                                cwd=root, env=environment,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
        for _ in range(400):
            if os.path.exists(pid_path) and open(pid_path).read(): break
            time.sleep(0.05)
        far_pid = int(open(pid_path).read())
        started = time.monotonic()
        near.send_signal(signal.SIGTERM)
        code = near.wait(30)
        took = time.monotonic() - started
        time.sleep(0.2)
        try:
            os.kill(far_pid, 0); alive_f = True
        except OSError:
            alive_f = False
    finally:
        shutil.rmtree(root); shutil.rmtree(bin_dir)
    print("near run ended by SIGTERM: exit %i" % code)
    print("far process gone: %s" % (not alive_f))
    ok_f = code == 128 + signal.SIGTERM and not alive_f and took < 30
    print("%s: a signal at the near run ends the far run with it."
          % ("SUCCESS" if ok_f else "FAILURE"))


def test_play():
    """RETURN: None. 'hwut.play' in each kind of bubble."""
    root, bin_dir = tree(), here_podman_bin()
    environment = dict(os.environ, PATH=first_on_path(bin_dir),
                       PYTHONPATH=os.path.dirname(config.HWUT_DIRECTORY))
    try:
        for where, argv in (("linux/TEST", ["--exclude-platform", "linux",
                                            "test-b.sh"]),
                            ("linux/TEST", ["test-b.sh"]),
                            ("linux/TEST", ["--exclude-local", "-p", "linux",
                                            "test-b.sh"]),
                            ("both/TEST", ["-p", "local", "-p", "linux",
                                           "test-d.sh"]),
                            ("none/TEST", ["test-a.sh"])):
            done = subprocess.run([sys.executable, "-m",
                                   "hwut.services.lib.run.play", "--plain"]
                                  + argv, cwd=os.path.join(root, where),
                                  env=environment, capture_output=True,
                                  text=True)
            print("$ (%s) hwut.play %s   [exit %i]"
                  % (where, " ".join(argv), done.returncode))
            for line in done.stdout.splitlines():
                if line.startswith(("NOTE", "REFUSED", "         =>",
                                    "nothing played", "RECORDED")) \
                   or "| test-" in line:
                    print("    %s" % re.sub(r"\(digest: [^)]*\)", "(digest)",
                                            line))
            recorded = os.path.join(root, where, "OUT")
            print("    OUT here: %s" % (sorted(os.listdir(recorded))
                                        if os.path.isdir(recorded) else "-"))
    finally:
        shutil.rmtree(root); shutil.rmtree(bin_dir)
    print("SUCCESS: play decided as the run is.")


def test_far_empty():
    """RETURN: None. A far run whose wish selects nothing is no fault."""
    root, bin_dir = tree(), here_podman_bin()
    environment = dict(os.environ, PATH=first_on_path(bin_dir),
                       PYTHONPATH=os.path.dirname(config.HWUT_DIRECTORY))
    try:
        code, event_list, results = run_with_events(
            root, ["--exclude-local", "-p", "linux", "--dir",
                   "linux/nowhere"], environment)
    finally:
        shutil.rmtree(root); shutil.rmtree(bin_dir)
    fault_list = [item["text"] for item in event_list
                  if item["kind"] == "fault"]
    verdict_n = sum(1 for item in event_list if item["kind"] == "run-ended")
    print("$ hwut.run --exclude-local -p linux --dir linux/nowhere")
    print("    near exit %i (3 is EMPTY)" % code)
    print("    %s" % results)
    print("    fault(s): %s" % (fault_list or "none"))
    print("    verdict(s): %i" % verdict_n)
    ok_f = code == 3 and not fault_list and verdict_n == 0
    print("%s: a far run that selects nothing is EMPTY, not a fault."
          % ("SUCCESS" if ok_f else "FAILURE"))


def test_probe():
    """RETURN: None. 'local' probed through 'HWUT_ROOT/tools.rst'."""
    root, bin_dir = tree(), tempfile.mkdtemp(prefix="hwut_bubble_probe_")
    try:
        os.makedirs(os.path.join(root, "HWUT"), exist_ok=True)
        os.makedirs(os.path.join(root, "HWUT_ROOT"), exist_ok=True)
        with open(os.path.join(root, "HWUT_ROOT/tools.rst"), "w") as fh:
            fh.write("[[iverilog]]\n    Icarus Verilog.\n"
                     "    probe: hwut-bubble-probe\n"
                     "[[ghdl]]\n    GHDL, no probe line.\n")
        os.makedirs(os.path.join(root, "none", "deep", "TEST", "GOOD"))
        path = os.path.join(root, "none", "deep", "TEST", "test-e.sh")
        with open(path, "w") as fh:
            fh.write('#! /bin/sh\n# @hwut { title = "E" }\n'
                     'echo e\necho "<hwut-end>"\n')
        os.chmod(path, 0o755)
        with open(os.path.join(root, "none", "deep", "hwut.conf"), "w") as fh:
            fh.write('hwut { requires = ["iverilog"] }\n')
        print("--- the probe's program not on PATH")
        decided(root, ["--exclude-platform", "linux"])
        with open(os.path.join(bin_dir, "hwut-bubble-probe"), "w") as fh:
            fh.write("#! /bin/sh\nexit 0\n")
        os.chmod(os.path.join(bin_dir, "hwut-bubble-probe"), 0o755)
        print("--- a stand-in first on PATH")
        decided(root, ["--exclude-platform", "linux"], first_on_path(bin_dir))
    finally:
        shutil.rmtree(root); shutil.rmtree(bin_dir)
    print("SUCCESS: a declared tool its probe misses fails its cases, named.")


def test_book():
    """RETURN: None. The books and the report after a run here and one
    handed to linux."""
    import json
    root, bin_dir = tree(), here_podman_bin()
    environment = dict(os.environ, PATH=first_on_path(bin_dir),
                       PYTHONPATH=os.path.dirname(config.HWUT_DIRECTORY))
    try:
        for argv in (["--exclude-platform", "linux"], ["--exclude-local", "-p", "linux"]):
            subprocess.run([sys.executable, "-m", "hwut.services.run",
                            "--plain", "--jobs=1"] + argv, cwd=root,
                           env=environment, capture_output=True)
        for where in ("TEST", "none/TEST", "linux/TEST", "linux/inner/TEST",
                      "both/TEST"):
            with open(os.path.join(root, where, "GOOD", "book.csv")) as fh:
                row_list = [l for l in fh.read().splitlines()
                            if not l.startswith("#")]
            print("%-17s %s" % (where, " | ".join(row_list)))
        page = subprocess.run([sys.executable, "-m", "hwut.services.report",
                               "--plain"], cwd=root, env=environment,
                              capture_output=True, text=True).stdout
        print("$ hwut.report")
        for line in page.splitlines():
            if line.startswith("        test-"): print("    %s" % line)
        document = json.loads(subprocess.run(
            [sys.executable, "-m", "hwut.services.report", "--format=json"],
            cwd=root, env=environment, capture_output=True,
            text=True).stdout)
        print("$ hwut.report --format=json   ('platform' per case)")
        for block in document["directory_list"]:
            for case in block["case_list"]:
                print("    %-17s %-10s %s" % (block["directory"], case["file"],
                                             case.get("platform", "-")))
    finally:
        shutil.rmtree(root); shutil.rmtree(bin_dir)
    print("SUCCESS: the book says where; the report reads it.")


def test_label():
    """RETURN: None. A label the wish asks decides which platform is
    needed (ruled 2026-11-27, "(b)"); 'hwut.help' says the ways past."""
    from hwut.services.lib.labels import view_at
    root, bin_dir = tree(), podman_bin(1)
    try:
        labels = os.path.join(root, "HWUT_ROOT", "labels.txt")
        print("--- 'HWUT_ROOT/labels.txt' names linux/TEST/test-b.sh only")
        with open(labels, "w") as fh:
            fh.write("./linux/TEST/test-b.sh : on_linux\n")
        for argv in (["-l", "on_linux"], ["-l", "NOT on_linux"]):
            decided(root, argv, first_on_path(bin_dir), view_at(root))
        print("--- ... and linux/inner/TEST/test-c.sh")
        with open(labels, "a") as fh:
            fh.write("./linux/inner/TEST/test-c.sh : on_linux\n")
        for argv in (["-l", "NOT on_linux"], ["-l", "on_linux"]):
            decided(root, argv, first_on_path(bin_dir), view_at(root))
        os.remove(labels)
        environment = dict(os.environ, PATH=first_on_path(bin_dir),
                           PYTHONPATH=os.path.dirname(config.HWUT_DIRECTORY))
        done = subprocess.run([sys.executable, "-m", "hwut.services.help"],
                              cwd=root, env=environment, capture_output=True,
                              text=True)
        print("$ hwut.help   [exit %i]" % done.returncode)
        shown_f = False
        for line in done.stdout.splitlines():
            shown_f = shown_f or line.startswith("PLATFORM")
            if shown_f: print("    %s" % line.replace(root, "<root>"))
    finally:
        shutil.rmtree(root); shutil.rmtree(bin_dir)
    print("SUCCESS: what the label selects decides what is needed.")


if __name__ == "__main__":
    HwutRunner(sys.argv,
               "Which bubble runs where;", {
        "local":     test_local,
        "first":     test_first,
        "below":     test_below,
        "header":    test_header,
        "refused":   test_refused,
        "excluded":  test_excluded,
        "handed":    test_handed,
        "untouched": test_untouched,
        "stream":    test_stream,
        "sigterm":   test_sigterm,
        "play":      test_play,
        "book":      test_book,
        "far-empty": test_far_empty,
        "probe":     test_probe,
        "label":     test_label,
    }).run()
