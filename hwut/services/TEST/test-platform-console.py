#! /usr/bin/env python3
#
# @hwut {
#     title      = "The console of a run with bubbles: marker lines, the platform named"
#     choices {
#         available { features = ["console-bubble-not-available"] }
#         reachable { features = ["console-bubble-not-reachable"] }
#         handed    { features = ["console-bubble-measured-there"] }
#     }
# }
#
"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE CONSOLE OF adm/WORK/spec/42-platforms.txt section 6 (plan/42
         P-7; intend/42 ruling 21) -- what 'hwut.run' says, in its final
         tree, of a bubble not run and of a directory measured on a
         platform; RESULTS untouched. The tree (as P-4's):

    .                 platform = [ { local  tools = [iverilog] },
                                   { linux  tools = [iverilog, ghdl] } ]
                      no 'requires'                          C = {local}
    ./TEST            test-top.sh
    none/             hwut-root.conf, no 'requires'          C = {local}
    linux/            requires = [ ghdl ]                    C = {linux}
    linux/inner/      hwut-root.conf, no 'requires'          C = {local}
    both/             requires = [ iverilog ]                C = {local, linux}

CHOICES: available, reachable, handed;

available  'hwut.run': linux/ stands in the tree where the walk meets it,
           '[PLATFORM not available]', the reason beside; its inner
           bubble below it, run here.
reachable  'hwut.run --exclude-local -p linux', a 'podman' that answers
           1 -- the image absent, no recipe: every bubble one marker
           line, 'available' or 'reachable'; nothing ran, no RESULTS.
handed     the same, a 'podman' that is this machine: '.' and none/ not
           available; every directory of linux/ and both/ named with
           '(linux)' once -- the verdicts beside, RESULTS as ever.

Each choice prints the final tree, its header's clock cut, and the
RESULTS line without its seconds.
______________________________________________________________________________
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import config                                                     # noqa F401

LINUX = ('{ name = "linux", kind = "container", image = "hwut-dev", '
         'recipe = "Containerfile", tools = ["iverilog", "ghdl"] }')
LOCAL = '{ name = "local", tools = ["iverilog"] }'

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
os.execvp(command[0], command)
"""


def tree():
    """RETURN: str, the root of a new tree as the PURPOSE draws it."""
    root = tempfile.mkdtemp(prefix="hwut_console_")
    conf_db = {"": "platform = [ %s, %s ]" % (LOCAL, LINUX), "none/": "",
               "linux/": 'requires = ["ghdl"]',
               "linux/inner/": "",
               "both/": 'requires = ["iverilog"]'}
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


def podman_bin(text):
    """RETURN: str, a new directory holding a 'podman' whose text is
    'text' -- put first on PATH, it is found before any engine the
    machine has; PATH is never narrowed (E-197)."""
    directory = tempfile.mkdtemp(prefix="hwut_console_bin_")
    path = os.path.join(directory, "podman")
    with open(path, "w") as fh: fh.write(text)
    os.chmod(path, 0o755)
    return directory


def console(argv, podman_text=None):
    """
    RETURN: None. 'hwut.run --plain --jobs=1 <argv>' over a new tree, a
            'podman' of 'podman_text' first on PATH where given: its exit
            status, the final tree (the header's clock cut, the tree's
            root said '<root>'), and the RESULTS line without its
            seconds.
    """
    root    = tree()
    bin_dir = podman_bin(podman_text) if podman_text is not None else None
    environment = dict(os.environ,
                       PYTHONPATH=os.path.dirname(config.HWUT_DIRECTORY))
    if bin_dir is not None:
        environment["PATH"] = bin_dir + os.pathsep + os.environ["PATH"]
    for name in ("NO_COLOR", "CI", "COLUMNS"): environment.pop(name, None)
    try:
        done = subprocess.run([sys.executable, "-m", "hwut.services.run",
                               "--plain", "--jobs=1"] + argv, cwd=root,
                              env=environment, capture_output=True,
                              text=True)
    finally:
        shutil.rmtree(root)
        if bin_dir is not None: shutil.rmtree(bin_dir)
    print("$ hwut.run %s   [exit %i]" % (" ".join(argv) or "(no -p)",
                                         done.returncode))
    line_list, inside_f = done.stdout.splitlines(), False
    for line in line_list:
        if line.startswith("DIRECTORIES"):
            inside_f = True
            print("    DIRECTORIES  (counts: %s)"
                  % re.sub(r", [0-9:]+$", "", line[len("DIRECTORIES"):]
                                              .strip()))
            continue
        if not inside_f: continue
        if line.startswith("="): inside_f = False; continue
        if line.startswith("-"): continue
        print("    %s" % line.rstrip().replace(root, "<root>"))
    for line in line_list:
        if line.startswith("RESULTS"):
            print("    %s" % re.sub(r", [0-9.]+ \[sec\].*$", "", line))
    if not any(line.startswith("RESULTS") for line in line_list):
        print("    (no RESULTS)")


if __name__ == "__main__":
    if "--hwut-info" in sys.argv:
        print("The console of a run with bubbles: marker lines, the "
              "platform named;")
        print("CHOICES: available, reachable, handed;")
        sys.exit(0)
    choice = sys.argv[1]
    if choice == "available":
        console([])
    elif choice == "reachable":
        console(["--exclude-local", "-p", "linux"], "#! /bin/sh\nexit 1\n")
    elif choice == "handed":
        console(["--exclude-local", "-p", "linux"],
                _HERE_PODMAN % sys.executable)
    print("<hwut-end>")
