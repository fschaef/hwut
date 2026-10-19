#! /usr/bin/env python3
#
# @hwut {
#     title      = "TAB completion -- the completer, its setup, the bash script (E-151)"
#     features   = ["complete-static"]
#     choices {
#         static   { features = ["complete-static"] }
#         values   { features = ["complete-static", "complete-cheap"] }
#         apps     { features = ["complete-cheap"] }
#         labels   { features = ["complete-dear"] }
#         targets  { features = ["complete-dear"] }
#         silent   { features = ["complete-silent"] }
#         shells   { features = ["complete-shells"] }
#         entry    { features = ["complete-tab-fast", "complete-silent"] }
#         setup    { features = ["complete-setup"] }
#         bash     { features = ["complete-bash-script"] }
#         zsh      { features = ["complete-zsh-script"] }
#         powershell { features = ["complete-powershell-script"] }
#     }
# }
#
"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

THE COMPLETION (services E-151, adm/WORK/gathered/0s). Every choice but
'setup' asks the completer against a FIXTURE table and a fixture tree in
'/tmp'; 'setup' asks the real faces.

    static    face names; a face's options; a face without a table
    values    an option's words ('enum'), '--opt=value', directories
    apps      the short form: applications here, then the choices of
              one -- 'choices = [...]' and a 'choices { }' block
    labels    'hwut-root.labels' at the boundary, plus 'all', 'meta'
    targets   the targets the current directory's 'hwut.conf' binds
    silent    a broken line, a missing table, an unreadable file: no
              candidate, nothing on stderr, status 0
    shells    one candidate list, three renderings
    entry     through 'bin/hwut': the modules of the tree a TAB imports
    setup     'hwut --command-line-setup --output=<file>': a face with a
              parser enters with its rows, one without by name only
    bash      'services/shell/hwut.bash' sourced, a TAB simulated
    zsh       'services/shell/hwut.zsh' sourced after 'compinit'; the
              registration is zsh's own, the answer is caught by
              'compadd' and '_describe' standing in for compsys's
    powershell 'services/shell/hwut.ps1' dot-sourced; a TAB asked of
              PowerShell's own 'TabExpansion2'
    A SHELL THAT IS NOT THERE IS A MISSING PRECONDITION, said as one: the
    choice goes red, never green unasked (adm/requirement-list.txt).
______________________________________________________________________________
"""
import os
import shutil
import subprocess
import sys
import tempfile

from   config import HwutRunner                                  # noqa F401,E402
from hwut.services import _complete                              # noqa: E402
from hwut.services._complete_setup import text_of                # noqa: E402

HWUT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(
                        __file__)), "..", ".."))
BIN  = os.path.join(HWUT, "bin")

TABLE_DB = {
    "FACE_TUPLE": ("hwut", "hwut.about", "hwut.execute", "hwut.labels.remove",
                   "hwut.run", "hwut.run.play"),
    "TABLE": {
        "hwut.run": (("--fail", "flag", ()), ("--glob", "value", ()),
                     ("--dir", "value", ()), ("-l", "value", ()),
                     ("--label", "value", ()), ("--directory", "file", ()),
                     ("--strategy", "enum", ("linear", "parallel")),
                     ("--format", "enum", ("plain", "junit")),
                     ("--jobs", "value", ())),
        "hwut.run.play": (("--save", "flag", ()), ("--raw", "flag", ())),
    },
}

APP_A = """#! /bin/sh
# @hwut {
#     title   = "a"
#     choices = ["one", "two", "three"]
# }
echo a
"""
APP_B = """#! /usr/bin/env python3
#
# @hwut {
#     title   = "b"
#     choices {
#         alpha { features = ["x"] }
#         beta  { }
#     }
# }
"""
NOT_APP = "#! /bin/sh\necho not a test\n"


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def ask(line, shell="bash", table_db=TABLE_DB):
    """RETURN: None. The line, and the completer's answer on one line --
               '(nothing)' where it answers nothing."""
    answer = _complete.complete(line, table_db)
    print("    %-34r -> %s" % (line, " ".join(answer) or "(nothing)"))


def fixture_tree():
    """
    RETURN: str, a fresh tree in '/tmp': 'hwut-root.conf', a labels file,
            'TEST/' with two applications, a plain file and a 'hwut.conf'
            binding two targets, 'TEST/sub/', and 'GOOD/', 'OUT/', 'TMP/'
            and a marked 'hwut.coverage/' that hold no application.
    """
    root = tempfile.mkdtemp(dir="/tmp")
    test = os.path.join(root, "TEST")
    os.makedirs(os.path.join(test, "sub"))
    for name in ("GOOD", "OUT", "TMP", "hwut.coverage"):
        os.makedirs(os.path.join(test, name))
    open(os.path.join(test, "hwut.coverage",
                      "hwut.no-entry-here.marker"), "w").close()
    files = {
        "hwut-root.conf":   "hwut { }\n",
        "hwut-root.labels": "#  hwut-root.labels\n#___\n"
                            "./TEST/test-a.sh : smoke nightly\n"
                            ":/test-b.py      : nightly\n",
        "TEST/test-a.sh":   APP_A,
        "TEST/test-b.py":   APP_B,
        "TEST/notes.txt":   NOT_APP,
        "TEST/hwut.conf":   "hwut {\n    target {\n"
                            "        clean = \"./clean.sh\"   # the OUT\n"
                            "        check { script = \"./c.sh\" }\n"
                            "    }\n}\n",
    }
    for name, text in files.items():
        with open(os.path.join(root, name), "w") as fh: fh.write(text)
    return root


def in_fixture(function):
    """RETURN: None. 'function' called with the fixture's 'TEST/' as the
               current directory; the fixture removed after."""
    root, here = fixture_tree(), os.getcwd()
    try:
        os.chdir(os.path.join(root, "TEST"))
        function()
    finally:
        os.chdir(here)
        shutil.rmtree(root, ignore_errors=True)


def test_static():
    banner("face names")
    ask("hwut.r")
    ask("hwut.run.")
    banner("a face's options")
    ask("hwut.run --")
    ask("hwut.run --f")
    ask("/opt/hwut/bin/hwut.run --st")
    ask("hwut.run.play test-a.sh --s")
    banner("a face without a table: nothing")
    ask("hwut.about --")
    ask("hwut.unknown --")


def test_values():
    def body():
        banner("an option's words")
        ask("hwut.run --strategy ")
        ask("hwut.run --strategy p")
        ask("hwut.run --format=")
        ask("hwut.run --format=j")
        banner("directories")
        ask("hwut.run --dir ")
        ask("hwut.run --directory s")
        banner("a value of no kind: nothing")
        ask("hwut.run --jobs ")
    in_fixture(body)


def test_apps():
    def body():
        banner("the applications here; a directory is a step")
        ask("hwut.run.play ")
        ask("hwut.run.play test-")
        ask("hwut.run ")
        ask("hwut.run --glob test-a")
        banner("the choices of one")
        ask("hwut.run.play test-a.sh ")
        ask("hwut.run.play test-a.sh t")
        ask("hwut.run test-b.py ")
        ask("hwut.run --fail test-b.py a")
        ask("hwut.run --strategy linear test-a.sh o")
        banner("an option's value is no application")
        ask("hwut.run --glob test-a.sh ")
    in_fixture(body)


def test_labels():
    def body():
        banner("labels at the boundary, and the standard ones")
        ask("hwut.run -l ")
        ask("hwut.run --label n")
        ask("hwut.labels.remove ")
        ask("hwut.labels.remove s")
    in_fixture(body)
    root = tempfile.mkdtemp(dir="/tmp")
    here = os.getcwd()
    try:
        os.chdir(root)
        banner("outside a tree: the standard ones")
        ask("hwut.run -l ")
    finally:
        os.chdir(here)
        shutil.rmtree(root)


def test_targets():
    def body():
        banner("the targets this directory binds")
        ask("hwut.execute ")
        ask("hwut.execute c")
        ask("hwut.execute cl")
        banner("the second word is the script's")
        ask("hwut.execute clean ")
    in_fixture(body)


def run_main(argv, environ=None):
    """RETURN: None. '_complete.main' run in a child; its status, stdout
               and stderr printed."""
    code = "import sys; from hwut.services import _complete; " \
           "sys.exit(_complete.main(%r))" % (argv,)
    env = dict(os.environ, PYTHONPATH=os.path.dirname(HWUT),
               **(environ or {}))
    done = subprocess.run([sys.executable, "-c", code], env=env,
                          capture_output=True, text=True)
    print("    %-44r status %i, stdout %r, stderr %r"
          % (argv, done.returncode, done.stdout, done.stderr))


def test_silent():
    root = tempfile.mkdtemp(dir="/tmp")
    try:
        missing = os.path.join(root, "absent.py")
        broken  = os.path.join(root, "broken.py")
        with open(broken, "w") as fh: fh.write("TABLE = {\n")
        banner("no candidate, no word on stderr, status 0")
        run_main([])
        run_main(["bash"])
        run_main(["bash", ""], {"HWUT_COMPLETE_DB": missing})
        run_main(["bash", "hwut.run --"], {"HWUT_COMPLETE_DB": broken})
        run_main(["fish", "hwut.r"], {"HWUT_COMPLETE_DB": broken})
        run_main(["bash", "hwut.run.play /nonexistent/x"])
        run_main(["bash", "hwut.run.play /nonexistent.sh "])
    finally:
        shutil.rmtree(root)


def test_shells():
    candidate_list = ["--format=junit", "--format=plain"]
    banner("bash: cut at the last '=' or ':'")
    print(_complete.render("bash", "--format=", candidate_list), end="")
    print(_complete.render("bash", "a:b", ["a:bc"]), end="")
    banner("zsh: ':' escaped")
    print(_complete.render("zsh", "a:b", ["a:bc"]), end="")
    banner("powershell: candidate, TAB, description")
    print(_complete.render("powershell", "--format=", candidate_list), end="")
    banner("an unknown shell, or no candidate: nothing")
    print(repr(_complete.render("fish", "x", ["xy"])))
    print(repr(_complete.render("bash", "x", [])))


def written_table(root):
    """RETURN: str, the path of a table written from TABLE_DB below 'root'."""
    path = os.path.join(root, "table.py")
    with open(path, "w") as fh:
        fh.write(text_of(TABLE_DB["FACE_TUPLE"], TABLE_DB["TABLE"]))
    return path


def test_entry():
    root = tempfile.mkdtemp(dir="/tmp")
    try:
        env = dict(os.environ, PYTHONPATH=os.path.dirname(HWUT),
                   HWUT_COMPLETE_DB=written_table(root))
        banner("through 'bin/hwut'")
        for line in ("hwut.run --f", "hwut.r", "hwut.run --format="):
            done = subprocess.run([os.path.join(BIN, "hwut"),
                                   "--command-line-complete", "bash", line],
                                  env=env, capture_output=True, text=True)
            print("    %-24r status %i, %r, stderr %r"
                  % (line, done.returncode, done.stdout, done.stderr))
        banner("the modules of the tree a TAB imports")
        done = subprocess.run([sys.executable, "-X", "importtime", "-m",
                               "hwut.services.run", "--command-line-complete",
                               "bash", "hwut.run --f"],
                              env=env, capture_output=True, text=True)
        for line in done.stderr.splitlines():
            name = line.rpartition("|")[2].strip()
            if name.split(".")[0] == "hwut": print("    " + name)
    finally:
        shutil.rmtree(root)


def test_setup():
    root = tempfile.mkdtemp(dir="/tmp")
    try:
        output = os.path.join(root, "db.py")
        done = subprocess.run([os.path.join(BIN, "hwut"),
                               "--command-line-setup", "--output=" + output],
                              capture_output=True, text=True, cwd=root)
        banner("written and compiled")
        print("    status %i, stderr %r" % (done.returncode, done.stderr))
        print("    first word: %s" % done.stdout.split()[0])
        cache = os.path.join(root, "__pycache__")
        print("    compiled:   %s" % any(n.startswith("db.")
                                         for n in os.listdir(cache)))
        name_db = {}
        with open(output) as fh: exec(fh.read(), name_db)
        banner("faces by name, options where a parser stands")
        for face in ("hwut", "hwut.run", "hwut.run.play", "hwut.about"):
            row_list = name_db["TABLE"].get(face, ())
            spelling_set = set(r[0] for r in row_list)
            print("    %-14s named %-5s rows %-5s '--glob' %s"
                  % (face, face in name_db["FACE_TUPLE"], bool(row_list),
                     "--glob" in spelling_set))
        banner("a word setup does not take")
        done = subprocess.run([os.path.join(BIN, "hwut"),
                               "--command-line-setup", "--force"],
                              capture_output=True, text=True, cwd=root)
        print("    status %i, %s" % (done.returncode, done.stderr.strip()))
    finally:
        shutil.rmtree(root)


def test_bash():
    root = tempfile.mkdtemp(dir="/tmp")
    try:
        script = os.path.join(HWUT, "services", "shell", "hwut.bash")
        program = """
            source %s
            complete -p hwut.run.play hwut
            tab() { COMP_LINE="$1"; COMP_POINT=${#1}; COMPREPLY=()
                    _hwut_complete; echo "    [$1] -> ${COMPREPLY[*]}"; }
            tab "hwut.run --f"
            tab "hwut.run --format=j"
            tab "hwut.r"
            tab "hwut.run.play --sa"
        """ % script
        env = dict(os.environ, PATH=BIN + os.pathsep + os.environ["PATH"],
                   HWUT_COMPLETE_DB=written_table(root))
        banner("sourced: every face on PATH registered; a TAB answered")
        done = subprocess.run(["bash", "-c", program], env=env, cwd=root,
                              capture_output=True, text=True)
        print(done.stdout, end="")
        print("    status %i, stderr %r" % (done.returncode, done.stderr))
        banner("no face on PATH: sourced quietly")
        done = subprocess.run(["bash", "-c", "source %s; echo $?" % script],
                              env=dict(env, PATH="/usr/bin:/bin"),
                              capture_output=True, text=True)
        print("    %s, stderr %r" % (done.stdout.strip(), done.stderr))
    finally:
        shutil.rmtree(root)


def shell_run(program_name, argv, root):
    """
    RETURN: None. 'argv' run with the faces of this tree first on PATH
            and the fixture table written below 'root'; its stdout, then
            its status and stderr, printed. Where 'program_name' is not
            on PATH, that is said instead.
    """
    if shutil.which(program_name) is None:
        print("    MISSING PRECONDITION: '%s' is not on PATH" % program_name)
        return
    env = dict(os.environ, PATH=BIN + os.pathsep + os.environ["PATH"],
               HWUT_COMPLETE_DB=written_table(root))
    done = subprocess.run(argv, env=env, cwd=root, capture_output=True,
                          text=True)
    print(done.stdout, end="")
    print("    status %i, stderr %r" % (done.returncode, done.stderr))


def test_zsh():
    root = tempfile.mkdtemp(dir="/tmp")
    try:
        os.mkdir(os.path.join(root, "sub"))
        script = os.path.join(HWUT, "services", "shell", "hwut.zsh")
        program = """
            autoload -U compinit; compinit -u -D
            source %s
            print "    registered: hwut.run.play ${_comps[hwut.run.play]}, hwut ${_comps[hwut]}"
            compadd()   { print -r -- "        compadd $*"; }
            _describe() { print -r -- "        _describe ${(P)4}"; }
            for line in "hwut.run --f" "hwut.run --format=j" "hwut.run --dir s" \
                        "hwut.run.play --sa" "hwut.about --"; do
                print -r -- "    [$line]"; LBUFFER=$line _hwut_complete
            done
        """ % script
        banner("sourced after 'compinit': registered; a TAB answered")
        shell_run("zsh", ["zsh", "-f", "-c", program], root)
    finally:
        shutil.rmtree(root)


def test_powershell():
    root = tempfile.mkdtemp(dir="/tmp")
    try:
        os.mkdir(os.path.join(root, "sub"))
        script = os.path.join(HWUT, "services", "shell", "hwut.ps1")
        program = """
            . '%s'
            foreach ($s in 'hwut.run --f', 'hwut.run --format=j',
                           'hwut.run --dir s', 'hwut.run.play --sa',
                           'hwut.about --') {
                $r = TabExpansion2 -inputScript $s -cursorColumn $s.Length
                '    [' + $s + '] -> ' + (($r.CompletionMatches |
                    ForEach-Object CompletionText) -join ' ')
            }
        """ % script
        banner("dot-sourced: a TAB asked of 'TabExpansion2'")
        #  .NET's W^X double mapping sizes a memory file past the page's
        #  10 MB per-file cap (RLIMIT_FSIZE, SIGXFSZ): measured, it dies
        #  under any cap below 'unlimited'. Off, it runs within it.
        os.environ["DOTNET_EnableWriteXorExecute"] = "0"
        shell_run("pwsh", ["pwsh", "-NoProfile", "-NonInteractive",
                           "-Command", program], root)
    finally:
        shutil.rmtree(root)


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "TAB completion -- the completer, its setup, the bash script (E-151)",
        choice_map = {
            "static":  test_static,
            "values":  test_values,
            "apps":    test_apps,
            "labels":  test_labels,
            "targets": test_targets,
            "silent":  test_silent,
            "shells":  test_shells,
            "entry":   test_entry,
            "setup":   test_setup,
            "bash":    test_bash,
            "zsh":     test_zsh,
            "powershell": test_powershell,
        }).run()
