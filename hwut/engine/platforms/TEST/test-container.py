#! /usr/bin/env python3
#
# @hwut {
#     title      = "Platforms: the helper, 'local' and 'container', its engine a fake"
#     choices {
#         available { features = ["platform-availability"] }
#         build     { features = ["platform-image-build"] }
#         argv      { features = ["platform-container-call"] }
#         keys      { features = ["platform-kind-keys"] }
#         imports   { features = ["engine-imports-no-face"] }
#         stream    { features = ["platform-stream-translated"] }
#         stop      { features = ["platform-stop-ends-run"] }
#     }
#     tolerance { eq_pattern = ["SUCCESS.*"] }
# }
#
"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE PLATFORMS HELPER (spec/42 section 4), its container engine
         replaced by A FAKE ON PATH: a script named 'podman' or
         'docker' that answers 'image inspect', 'build' and 'run' by
         what a file beside it says, and notes every call. No
         container, no daemon: the page states the helper's answers and
         the engine calls it makes.

CHOICES: available, build, argv, keys, imports, stream, stop;

available  'local' always; no engine on PATH; an engine asked for that
           is not there; the image stands; absent with a recipe;
           absent with no recipe; absent with a recipe that is no file.
build      'start': the image stands, nothing built; absent, built (one
           BUILDING line); the build fails (the ERROR line, the build's
           last five of eight lines, 'image build failed').
argv       the run's engine call for podman and for docker: the bubble
           the working directory; the bubble and the hwut mounted at their
           own paths -- one mount where the bubble lies inside the hwut;
           the far 'hwut.run' silent, '--events /dev/stdout', the words.
stream     'run' over a far run that prints event lines (spec/42 section
           5): tree-begun and tree-done dropped, each 'directory' put
           below the bubble ('.' the bubble), 'platform' added, the time
           kept; a line no event, a 'fault'; a far status 2, a 'fault';
           0 and 1 told by the events alone.
stop       a far run still standing when its reader stops: 'stop' ends
           it, and the reading returns (E-55).
keys       the kinds a conf may name; the keys of 'container'; an
           unknown kind; the reserved 'local'.
imports    every module of engine/platforms read with 'ast': no import
           of anything but the engine and the standard library. A
           planted 'from hwut.services ...' is named (the check sees).
______________________________________________________________________________
"""
import ast
import json
import os
import shutil
import sys
import tempfile
import config                                                     # noqa F401
from   config import HwutRunner                                   # noqa E402
from hwut.engine import platforms                                 # noqa E402
from hwut.engine.platforms import container                       # noqa E402

PLATFORMS_DIR = os.path.join(config.HWUT_DIRECTORY, "engine", "platforms")

_FAKE = """#! %s
import json, os, sys
here = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(here, "calls.txt"), "a") as fh:
    fh.write(json.dumps([os.path.basename(sys.argv[0])] + sys.argv[1:]) + "\\n")
say = json.load(open(os.path.join(here, "fake.json")))
word = sys.argv[1]
if word == "image":
    sys.exit(0 if say.get("image") else 1)
if word == "build":
    for line in say.get("build_lines", []): print(line)
    sys.exit(say.get("build", 0))
for line in say.get("run_lines", []): print(line, flush=True)
if say.get("sleep"):
    import time
    with open(os.path.join(here, "running.txt"), "w") as fh:
        fh.write(str(os.getpid()))
    time.sleep(say["sleep"])
sys.exit(say.get("run", 0))
"""


def check(pair_list):
    """RETURN: True, every claim held; False, at least one did not --
    each printed as 'OK' or 'FAIL' with its claim."""
    ok = True
    for holds, claim in pair_list:
        print("  %s: %s" % ("OK  " if holds else "FAIL", claim))
        if not holds: ok = False
    return ok


def verdict(ok, sentence):
    """RETURN: None. The one closing line HWUT greps for."""
    print("%s: %s" % ("SUCCESS" if ok else "FAILURE", sentence))


class Fake:
    """A tree with a recipe, and a bin directory that alone is PATH:
    the engines placed there are fakes, the machine's own never seen."""

    def __init__(self):
        """RETURN: None. The fixture made: a root holding the recipe, a
        bin directory set as the whole of PATH."""
        self.root = tempfile.mkdtemp(prefix="hwut_platforms_")
        self.recipe = os.path.join(self.root, container.CONTAINERFILE)
        os.makedirs(os.path.dirname(self.recipe))
        with open(self.recipe, "w") as fh: fh.write("FROM scratch\n")
        self.bin = os.path.join(self.root, "bin")
        os.makedirs(self.bin)
        self.old_path = os.environ.get("PATH", "")
        os.environ["PATH"] = self.bin

    def engine(self, name, **say):
        """RETURN: None. A fake 'name' on PATH, answering as 'say'
        tells; the calls noted so far forgotten."""
        path = os.path.join(self.bin, name)
        with open(path, "w") as fh: fh.write(_FAKE % sys.executable)
        os.chmod(path, 0o755)
        with open(os.path.join(self.bin, "fake.json"), "w") as fh:
            json.dump(say, fh)
        calls = os.path.join(self.bin, "calls.txt")
        if os.path.exists(calls): os.remove(calls)

    def no_engine(self):
        """RETURN: None. PATH holds no engine at all."""
        for name in container.ENGINE_TUPLE:
            path = os.path.join(self.bin, name)
            if os.path.exists(path): os.remove(path)

    def call_list(self):
        """RETURN: list of list of str, the engine calls noted, in order,
        the root shown as '<root>'."""
        path = os.path.join(self.bin, "calls.txt")
        if not os.path.exists(path): return []
        with open(path) as fh:
            return [[self.shown(w) for w in json.loads(line)] for line in fh]

    def shown(self, text):
        """RETURN: str, 'text' with the fixture's root as '<root>'."""
        return text.replace(self.root, "<root>")

    def close(self):
        """RETURN: None. PATH as it was, the fixture gone."""
        os.environ["PATH"] = self.old_path
        shutil.rmtree(self.root)


def spec_of(fake, **kw):
    """RETURN: dict, a 'container' entry as the conf's reader hands it:
    image 'hwut-dev', the fixture's recipe, 'kw' over them."""
    spec = {"name": "linux", "kind": "container", "image": "hwut-dev",
            "recipe": fake.recipe}
    spec.update(kw)
    return {k: v for k, v in spec.items() if v is not None}


def ask(fake, title, name, spec):
    """RETURN: (bool, str), what 'is_available' answered; it shown with
    the engine calls it made."""
    answer = platforms.is_available(name, spec)
    print("%-36s -> (%s, %r)" % (title, answer[0], fake.shown(answer[1])))
    for argv in fake.call_list():
        print("    $ %s" % " ".join(argv))
    return answer


def test_available():
    """RETURN: None. 'is_available' asked for local and for every state
    of a container, each answer shown and checked."""
    fake = Fake()
    try:
        local    = ask(fake, "local", "local", {})
        fake.no_engine()
        none     = ask(fake, "no engine on PATH", "linux", spec_of(fake))
        fake.engine("podman", image=True)
        wanted   = ask(fake, "engine 'docker' asked, podman stands",
                       "linux", spec_of(fake, engine="docker"))
        fake.engine("podman", image=True)
        stands   = ask(fake, "image stands", "linux", spec_of(fake))
        fake.engine("podman", image=False)
        recipe   = ask(fake, "image absent, recipe", "linux", spec_of(fake))
        fake.engine("podman", image=False)
        bare     = ask(fake, "image absent, no recipe", "linux",
                       spec_of(fake, recipe=None))
        fake.engine("podman", image=False)
        lost     = ask(fake, "image absent, recipe no file", "linux",
                       spec_of(fake, recipe=fake.recipe + ".gone"))
    finally:
        fake.close()
    ok = check([
        (local == (True, ""), "'local' is always available"),
        (none == (False, "no podman or docker on PATH"),
         "no engine: named, both of them"),
        (wanted == (False, "no docker on PATH"),
         "an engine asked for and absent: named, the other not taken"),
        (stands == (True, ""), "the image stands: available"),
        (recipe == (True, ""), "the image absent, a recipe: available"),
        (bare == (False, "image 'hwut-dev' absent and no recipe"),
         "the image absent, no recipe: named"),
        (not lost[0] and "not found" in lost[1],
         "a recipe that is no file: named"),
    ])
    verdict(ok, "availability, measured and named.")


def begin(fake, title, spec):
    """RETURN: (bool, str), what 'start' answered; its console lines,
    the answer and the engine calls shown."""
    line_list, log_list = [], []
    answer = platforms.start("linux", spec, line_list.append,
                             log_list.append)
    print("%s" % title)
    for line in line_list:  print("    | %s" % fake.shown(line))
    print("    -> (%s, %r); %i line(s) to the log"
          % (answer[0], answer[1], len(log_list)))
    for argv in fake.call_list():
        print("    $ %s" % " ".join(argv))
    return answer, line_list, log_list


def test_build():
    """RETURN: None. 'start' over an image that stands, one built, one
    whose build fails -- console, log and engine calls checked."""
    fake = Fake()
    eight = ["step %i" % i for i in range(1, 8)] + ["Error: no such file"]
    try:
        fake.engine("podman", image=True)
        stands, stands_lines, _ = begin(fake, "image stands", spec_of(fake))
        fake.engine("podman", image=False, build=0,
                    build_lines=["STEP 1/2: FROM scratch", "COMMIT hwut-dev"])
        built, built_lines, built_log = begin(fake, "image absent, built",
                                              spec_of(fake))
        built_calls = fake.call_list()
        fake.engine("podman", image=False, build=1, build_lines=eight)
        failed, failed_lines, failed_log = begin(fake, "the build fails",
                                                 spec_of(fake))
    finally:
        fake.close()
    ok = check([
        (stands == (True, "") and not stands_lines,
         "an image that stands is not built, nothing said"),
        (built == (True, "")
         and built_lines == ["BUILDING: image 'hwut-dev' from "
                             "adm/container/Containerfile"],
         "an absent image is built, said once, the recipe as the tree "
         "names it"),
        (built_calls[-1][:4] == ["podman", "build", "-t", "hwut-dev"]
         and built_calls[-1][-1] == ".",
         "the build: tagged with the image, the root its context"),
        (built_log == ["STEP 1/2: FROM scratch", "COMMIT hwut-dev"],
         "the build's output goes to the log, not the console"),
        (failed == (False, "image build failed")
         and failed_lines[1].startswith("ERROR: image 'hwut-dev' not built")
         and [l.strip() for l in failed_lines[2:]] == eight[-5:],
         "a failed build: the ERROR line, the last five lines, "
         "'image build failed'"),
        (len(failed_log) == 8, "the failed build's whole output in the log"),
    ])
    verdict(ok, "an absent image built; a failed build said.")


def test_argv():
    """RETURN: None. The run's engine call for podman and docker, shown
    and checked word by word."""
    home, inside, outside = "/home/u/work", "/home/u/work/hwut/support", \
                            "/home/u/project/board"
    wish = ["--as-platform=linux", "--glob", "demo/c/TEST/test.c"]
    podman = container.run_argv("podman", "hwut-dev", home, inside, wish,
                                1000, 1000)
    docker = container.run_argv("docker", "hwut-dev", home, inside, wish,
                                1000, 1000)
    apart  = container.run_argv("podman", "hwut-dev", home, outside, wish,
                                1000, 1000)
    for argv in (podman, docker, apart):
        print("$ %s" % " ".join(argv))
    ok = check([
        (podman[:5] == ["podman", "run", "--rm", "-i", "--userns=keep-id"],
         "podman keeps the user by '--userns=keep-id'"),
        ("--user=1000:1000" in docker and "--userns=keep-id" not in docker,
         "docker keeps the user by '--user'"),
        (podman.count("-v") == 1
         and podman[podman.index("-v") + 1] == "%s:%s" % (home, home),
         "a bubble inside the hwut: one mount, at its own path"),
        ([apart[i + 1] for i, w in enumerate(apart) if w == "-v"]
         == ["%s:%s" % (home, home), "%s:%s" % (outside, outside)],
         "a bubble apart: the hwut and the bubble, each at its own path"),
        (podman[podman.index("-w") + 1] == inside,
         "the bubble is the working directory"),
        (podman[podman.index("-e") + 1] == "HOME=/tmp", "HOME=/tmp"),
        (podman[podman.index("hwut-dev") + 1:]
         == ["/home/u/work/hwut/bin/hwut.run", "--silent", "--events",
             "/dev/stdout"] + wish,
         "the hwut that runs here, silent, its events on stdout, "
         "the words after"),
    ])
    verdict(ok, "the bubble's run, one engine call.")


def test_keys():
    """RETURN: None. The kinds a conf may name and the keys of each,
    shown and checked."""
    print("kind_tuple()       = %r" % (platforms.kind_tuple(),))
    print("keys('container')  = %r" % (platforms.keys("container"),))
    print("keys('host')       = %r" % (platforms.keys("host"),))
    print("keys('local')      = %r" % (platforms.keys("local"),))
    ok = check([
        (platforms.kind_tuple() == ("container",),
         "the first release knows 'container' alone"),
        (platforms.keys("container") == ("image", "recipe", "engine"),
         "'container' knows image, recipe, engine"),
        (platforms.keys("host") is None, "an unknown kind has no keys"),
        (platforms.keys("local") is None,
         "'local' is a reserved name, no kind"),
    ])
    verdict(ok, "kinds and their keys.")


def foreign_import_list(path, package):
    """
    RETURN: list of str, every import in the module at 'path' that is
            neither the standard library nor below 'hwut.engine' --
            relative imports resolved against 'package'. Empty, where
            the module keeps the law.
    """
    with open(path) as fh: tree = ast.parse(fh.read(), path)
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            name_list = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package.split(".")[:len(package.split("."))
                                            - node.level + 1]
                name_list = [".".join(base + ([node.module]
                                              if node.module else []))]
            else:
                name_list = [node.module]
        else:
            continue
        for name in name_list:
            top = name.split(".")[0]
            if name == "hwut.engine" or name.startswith("hwut.engine."):
                continue
            if top != "hwut" and top in sys.stdlib_module_names:
                continue
            found.append("%s:%i: %s" % (os.path.basename(path),
                                         node.lineno, name))
    return found


def test_imports():
    """RETURN: None. Every module of engine/platforms read for imports
    beyond the engine and the standard library; a planted one named."""
    module_list = sorted(f for f in os.listdir(PLATFORMS_DIR)
                         if f.endswith(".py"))
    found = []
    for name in module_list:
        found += foreign_import_list(os.path.join(PLATFORMS_DIR, name),
                                     "hwut.engine.platforms")
        print("  read: engine/platforms/%s" % name)
    for line in found: print("  FOREIGN: %s" % line)
    planted_dir = tempfile.mkdtemp(prefix="hwut_platforms_planted_")
    planted = os.path.join(planted_dir, "planted.py")
    with open(planted, "w") as fh:
        fh.write("import os\nfrom ...services.lib import x\n"
                 "from hwut.services import run\nfrom . import local\n")
    seen = foreign_import_list(planted, "hwut.engine.platforms")
    shutil.rmtree(planted_dir)
    for line in seen: print("  planted, named: %s" % line)
    ok = check([
        (len(module_list) >= 3, "the helper's modules were read"),
        (not found, "no module imports beyond the engine and the "
                    "standard library"),
        (seen == ["planted.py:2: hwut.services.lib",
                  "planted.py:3: hwut.services"],
         "a planted face import is named, relative and absolute alike"),
    ])
    verdict(ok, "the engine imports nothing of the faces.")


_FAR_LINE_LIST = [
    '0.00:tree-begun:{"when": "2026-11-03T10:00:00+00:00", '
    '"directory_list": ["TEST"], "node_n": 1}',
    "0.00:dir-begun:TEST,1",
    "0.01:run-begun:TEST,test-a.sh,TEST",
    "0.20:run-ended:TEST,test-a.sh,TEST,false,test-failed,,,",
    "0.21:report:TEST: a note of the far run",
    "the far run said something that is no event",
    '0.22:dir-done:{"directory": "TEST", "good": false, "fail_db": '
    '{"test-a.sh": "ENDED_BAD"}}',
    "0.22:tree-done:false,1,,",
]


def test_stream():
    """RETURN: None. 'run' over a far run that prints event lines: each
    near event shown, then the claims."""
    fake = Fake()
    try:
        result = {}
        for status in (1, 2):
            fake.engine("podman", image=True, run=status,
                        run_lines=_FAR_LINE_LIST)
            event_list = []
            code = platforms.run("linux", spec_of(fake), "support",
                                 ["--as-platform=linux"], event_list.append,
                                 root=fake.root)
            print("far status %i -> run returned %i" % (status, code))
            for item in event_list:
                shown = {k: v for k, v in item.items() if k != "format"}
                #  A FAULT THE NEAR SIDE MAKES is stamped now: a machine
                #  fact, kept off the page.
                if item["kind"] == "fault": shown["when"] = "<now>"
                print("    %s" % fake.shown(json.dumps(shown, sort_keys=True)))
            result[status] = event_list
    finally:
        fake.close()
    near = result[1]
    kind_list = [item["kind"] for item in near]
    ok = check([
        ("tree-begun" not in kind_list and "tree-done" not in kind_list,
         "the far tree-begun and tree-done are dropped"),
        (all(item.get("directory", "support").startswith("support")
             for item in near)
         and near[0]["directory"] == "support/TEST",
         "each directory below the bubble"),
        (all(item.get("platform") == "linux" for item in near),
         "every event carries 'platform'"),
        (near[2]["when"] == "2026-11-03T10:00:00.200000+00:00",
         "the time kept, reckoned from the far tree-begun"),
        (any(item["kind"] == "fault" and "said: the far run said" in
             item["text"] for item in near),
         "a line no event: a fault, the line verbatim"),
        (not any("ended with status" in item.get("text", "")
                 for item in near),
         "status 1: told by the events, no fault"),
        (result[2][-1]["kind"] == "fault"
         and result[2][-1]["text"] == "support/: platform 'linux' ended "
                                      "with status 2",
         "status 2: a fault naming it"),
    ])
    verdict(ok, "the far stream, translated.")


def test_stop():
    """RETURN: None. A far run that sleeps: 'stop' ends it."""
    import threading
    import time
    fake = Fake()
    try:
        fake.engine("podman", image=True, sleep=60)
        returned = []
        reader = threading.Thread(
            target=lambda: returned.append(
                platforms.run("linux", spec_of(fake), "support", [],
                              lambda item: None, root=fake.root)))
        reader.start()
        running = os.path.join(fake.bin, "running.txt")
        for _ in range(200):
            if os.path.exists(running): break
            time.sleep(0.05)
        pid = int(open(running).read())
        started = time.monotonic()
        platforms.stop("linux", spec_of(fake))
        reader.join(15)
        took = time.monotonic() - started
        try:
            os.kill(pid, 0); alive_f = True
        except OSError:
            alive_f = False
    finally:
        fake.close()
    print("far run started; stop called; the reader returned: %s"
          % (not reader.is_alive()))
    ok = check([
        (not alive_f, "the far process is gone"),
        (not reader.is_alive() and took < 15,
         "the reading returned, not after the far run's minute"),
        (returned and returned[0] != 0, "its status says it was ended"),
    ])
    verdict(ok, "stop ends a far run that outlives its reader.")


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "Platforms: the helper, 'local' and 'container'",
        choice_map = {
            "available": test_available,
            "build":     test_build,
            "argv":      test_argv,
            "keys":      test_keys,
            "imports":   test_imports,
            "stream":    test_stream,
            "stop":      test_stop,
        },
        happy      = "SUCCESS.*",
    ).run()
