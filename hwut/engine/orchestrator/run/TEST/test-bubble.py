#! /usr/bin/env python3
#
# @hwut {
#     title      = "Which bubble runs where: S, Q(B), F(B) decided before the first event"
#     choices {
#         local     { features = ["bubble-decided", "bubble-inner-decided-alone"] }
#         refused   { features = ["bubble-refused"] }
#         excluded  { features = ["bubble-decided", "bubble-not-run-untouched"] }
#         handed    { features = ["bubble-handed-hides-inner"] }
#         untouched { features = ["bubble-not-run-untouched"] }
#         stream    { features = ["bubble-handed-run-there"] }
#         sigterm   { features = ["bubble-handed-ended"] }
#         play      { features = ["bubble-play-decided"] }
#         book      { features = ["bubble-book-says-where"] }
#     }
#     tolerance { eq_pattern = ["SUCCESS.*"] }
# }
#
"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE DECISION OF adm/WORK/spec/42-platforms.txt section 3 (plan/42
         P-4; intend/42 rulings 10, 12, 19, 21) on one tree:

    .                 hwut-root.conf, no 'platform'          Q = {local}
    ./TEST            test-top.sh
    none/             hwut-root.conf, no 'platform'          Q = {local}
    linux/            platform = [ linux ]                   Q = {linux}
    linux/inner/      hwut-root.conf, no 'platform'          Q = {local}
    both/             platform = [ "local", linux ]          Q = {local, linux}

CHOICES: local, refused, excluded, handed, untouched, stream, sigterm,
         play, book;

local      S = {local}: '.', none/, both/ run here; linux/ NOT RUN,
           'available'; its inner bubble runs here (ruling 19).
refused    '-p linux', S = {local, linux}: both/ meets two -- REFUSED at
           the call, named, with the remedy; nothing explored.
excluded   '--exclude-local -p linux', S = {linux}, a podman stand-in
           first on PATH answering 1 -- the image absent, no recipe:
           linux/ and both/ NOT RUN, 'reachable'; every bubble requiring
           'local' NOT RUN, 'available'; nothing explored.
handed     the same, the stand-in answering 0 -- the image stands:
           linux/ and both/ HANDED, each with the far run's words ('--as-
           platform=linux': over there its 'local' IS linux); linux/inner/
           is decided over there -- not here, not walked.
untouched  'hwut.run' itself, each S: the stream's 'not-run' lines, the
           RESULTS, and every file below a bubble not run -- the same
           before and after: no book, no 'TMP/', no 'OUT/' (ruling 21).

stream     the hand-over, real: a 'podman' that is this machine ('run'
           changes to '-w' and executes the words after the image).
           'hwut.run --exclude-local -p linux' against 'hwut.run' inside
           linux/ alone: the same verdict per case -- the near run's
           directories below 'linux/', each carrying 'platform' -- and
           the same RESULTS; the inner bubble run over there too.
sigterm    the near run ended by SIGTERM while the far run sleeps: the
           near run ends (128 + 15), the far process with it (E-55).
play       'hwut.play' decides its directory's bubble as 'hwut.run' does
           (ruled 2026-11-03, "yes to play"): in linux/TEST without '-p',
           not run -- the NOTE, EMPTY; with '--exclude-local -p linux',
           handed -- the far play's lines relayed, its recording on this
           disk; in both/TEST with '-p linux', refused; in none/TEST, as
           ever.
book       after 'hwut.run' and 'hwut.run --exclude-local -p linux': each
           book's rows -- the platform's name last where linux measured
           the verdict, nothing where this machine did -- and
           'hwut.report', which reads the books and takes no '-p' (ruling
           21): '(linux)' beside a case linux measured; in JSON, its
           'platform'.

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
         'recipe = "Containerfile" }')
BIN   = os.path.join(config.HWUT_DIRECTORY, "bin")


def seconds_cut(line):
    """RETURN: str, 'line' without the seconds a RESULTS line ends in --
    the machine's, never the page's."""
    return re.sub(r", [0-9.]+ \[sec\].*$", "", line)


def tree():
    """RETURN: str, the root of a new tree as the PURPOSE draws it."""
    root = tempfile.mkdtemp(prefix="hwut_bubble_")
    conf_db = {"": "", "none/": "",
               "linux/": "platform = [ %s ]" % LINUX,
               "linux/inner/": "",
               "both/": 'platform = [ "local", %s ]' % LINUX}
    test_db = {"TEST": "test-top.sh", "none/TEST": "test-a.sh",
               "linux/TEST": "test-b.sh", "linux/inner/TEST": "test-c.sh",
               "both/TEST": "test-d.sh"}
    for where, text in conf_db.items():
        os.makedirs(os.path.join(root, where), exist_ok=True)
        with open(os.path.join(root, where, "hwut-root.conf"), "w") as fh:
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


def decided(root, argv, path=None):
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
        tree_plan = orchestrate(root, wish)
    except SelectionError as error:
        print("    REFUSED: %s" % str(error).replace(root, "<root>"))
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
    print("    PLANNED: %s" % ", ".join(e.directory for e in tree_plan))
    for name in ("TEST", "none/TEST", "linux/TEST", "linux/inner/TEST",
                 "both/TEST"):
        print("    EXPLORED %-18s %i" % (name, counted.count_db.get(name, 0)))
    for line in tree_plan.warning_tuple: print("    %s" % line)


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
        decided(root, [])
    finally:
        shutil.rmtree(root)
    print("SUCCESS: decided, the inner bubble of a bubble not run run here.")


def test_refused():
    """RETURN: None. |F(B)| > 1."""
    root = tree()
    try:
        decided(root, ["-p", "linux"])
        decided(root, ["-p", "linux", "-p", "win11"])
    finally:
        shutil.rmtree(root)
    print("SUCCESS: refused at the call, every such bubble named.")


def test_excluded():
    """RETURN: None. S = {linux}, the image absent, no recipe."""
    root, bin_dir = tree(), podman_bin(1)
    try:
        decided(root, ["--exclude-local", "-p", "linux"],
                first_on_path(bin_dir))
    finally:
        shutil.rmtree(root); shutil.rmtree(bin_dir)
    print("SUCCESS: not available, not reachable; nothing explored.")


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
        for argv, below_tuple in (([], ("linux",)),
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
                if line.startswith(("NOTE  ", "RESULTS", "    (no directory")):
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
        #  THE SAME BUBBLE RUN LOCALLY, as over there: its 'local' is linux.
        for name in ("TMP", "OUT"):
            for here, name_list, _ in os.walk(os.path.join(root, "linux")):
                if name in name_list:
                    shutil.rmtree(os.path.join(here, name))
        local_code, local_list, local_results = run_with_events(
            os.path.join(root, "linux"), ["--as-platform=linux"], environment)
    finally:
        shutil.rmtree(root); shutil.rmtree(bin_dir)
    near_linux = [line for line in verdict_list(near_list)
                  if line.startswith("linux/")]
    local_linux = verdict_list(local_list, "linux")
    print("near  [exit %i] %s" % (near_code, near_results))
    for line in verdict_list(near_list): print("    %s" % line)
    print("local [exit %i] %s   (in linux/)" % (local_code, local_results))
    for line in local_linux: print("    %s" % line)
    ok_f = [line.rsplit(" ", 1)[0] for line in near_linux] \
           == [line.rsplit(" ", 1)[0] for line in local_linux] \
           and all(line.endswith(" linux") for line in near_linux) \
           and "linux/inner/TEST test-c.sh ok linux" in near_linux
    print("%s: the bubble run there is the bubble run here, but for "
          "'platform'." % ("SUCCESS" if ok_f else "FAILURE"))


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
        for where, argv in (("linux/TEST", ["test-b.sh"]),
                            ("linux/TEST", ["--exclude-local", "-p", "linux",
                                            "test-b.sh"]),
                            ("both/TEST", ["-p", "linux", "test-d.sh"]),
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


def test_book():
    """RETURN: None. The books and the report after a run here and one
    handed to linux."""
    import json
    root, bin_dir = tree(), here_podman_bin()
    environment = dict(os.environ, PATH=first_on_path(bin_dir),
                       PYTHONPATH=os.path.dirname(config.HWUT_DIRECTORY))
    try:
        for argv in ([], ["--exclude-local", "-p", "linux"]):
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


if __name__ == "__main__":
    HwutRunner(sys.argv,
               "Which bubble runs where;", {
        "local":     test_local,
        "refused":   test_refused,
        "excluded":  test_excluded,
        "handed":    test_handed,
        "untouched": test_untouched,
        "stream":    test_stream,
        "sigterm":   test_sigterm,
        "play":      test_play,
        "book":      test_book,
    }).run()
