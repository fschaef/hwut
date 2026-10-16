#! /usr/bin/env python3
#
# @hwut {
#     title      = "The packages are read off the tree: one version, one list, one set of faces"
#     features   = ["one-version"]
#     choices {
#         version      { features = ["one-version"] }
#         faces        { features = ["one-version"] }
#         requirements { features = ["one-requirement-list"] }
#         help-missing { features = ["help-names-missing"] }
#         deb          { features = ["one-version", "one-requirement-list"] }
#     }
# }
#
"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

WHAT EVERY FORM IS CUT FROM (adm/WORK/spec/24): the stage that
'adm/packaging/build.py stage' writes, judged against the tree it was
read off. Nothing is installed and nothing is fetched: this page runs in
the census.

    version       the stage's 'pyproject.toml' states the version of
                  'adm/version.py'
    faces         its entry points are the shims of 'bin/' but
                  'hwut.dev.*'; the stage holds no TEST directory but the
                  demonstration's, no WORK, no completion table
    requirements  the wheel's dependencies and the Debian 'Depends' are
                  the census rows of 'adm/requirement-list.txt', read here
                  by a reader of this page's own
    help-missing  'hwut.help' in an interpreter that has none of them:
                  each named with how to install it, status 1
    deb           'build.py deb': its control file states the version,
                  'Architecture: all' and the 'Depends' of the list; its
                  '/usr/bin' the same faces as the wheel; every face's bash
                  completion linked; postinst and prerm stand
______________________________________________________________________________
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

from   config import HwutRunner                                  # noqa F401,E402

HWUT  = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(
                         __file__)), "..", "..", ".."))
BUILD = os.path.join(HWUT, "adm", "packaging", "build.py")
LIST  = os.path.join(HWUT, "adm", "requirement-list.txt")


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def staged():
    """RETURN: str, a fresh stage written by 'build.py stage' in '/tmp'."""
    target = os.path.join(tempfile.mkdtemp(dir="/tmp"), "stage")
    subprocess.run([sys.executable, BUILD, "stage", target], check=True,
                   stdout=subprocess.DEVNULL)
    return target


def pyproject(stage):
    """RETURN: str, the text of the stage's 'pyproject.toml'."""
    with open(os.path.join(stage, "pyproject.toml")) as fh: return fh.read()


def shim_face_set():
    """RETURN: set[str], the faces of 'bin/' -- every 'hwut' and 'hwut.*'
               shim -- read here without the builder's reader."""
    return set(n for n in os.listdir(os.path.join(HWUT, "bin"))
               if n == "hwut" or n.startswith("hwut."))


def census_python_rows():
    """RETURN: list[(str, str)], (pip spec, Debian spec) of every census
               'python' row of the list, read here without the tree's
               reader."""
    result = []
    with open(LIST) as fh:
        for line in fh:
            m = re.match(r"^python\s+(\S+)\s+census\s+(\S+)", line)
            if m: result.append(m.groups())
    return result


def test_version():
    stage = staged()
    try:
        with open(os.path.join(HWUT, "adm", "version.py")) as fh:
            stated = re.search(r'"([^"]+)"', fh.read()).group(1)
        built = re.search(r'^version\s*=\s*"([^"]+)"', pyproject(stage),
                          re.M).group(1)
        banner("the version")
        print("    adm/version.py      %s" % stated)
        print("    pyproject.toml      %s" % built)
        print("    the same:           %s" % (stated == built))
    finally:
        shutil.rmtree(os.path.dirname(stage))


def test_faces():
    stage = staged()
    try:
        text = pyproject(stage)
        script_set = set(re.findall(r'^"(hwut[^"]*)" = "hwut\.services\._launch:main"',
                                    text, re.M))
        shim_set = shim_face_set()
        dev_set  = set(f for f in shim_set if f.startswith("hwut.dev."))
        banner("the faces")
        print("    the same as bin/ but hwut.dev.*:  %s"
              % (script_set == shim_set - dev_set))
        print("    left out:  %s" % " ".join(sorted(dev_set)))
        print("    launched by one entry point:  %s"
              % ("hwut" in script_set and "hwut.run" in script_set))
        banner("what the stage holds")
        package = os.path.join(stage, "hwut")
        test_list, work_n, table_n = [], 0, 0
        for directory, sub_list, name_list in os.walk(package):
            relative = os.path.relpath(directory, package)
            if os.path.basename(directory) == "TEST": test_list.append(relative)
            if os.path.basename(directory) == "WORK": work_n += 1
            table_n += name_list.count("_complete_db.py")
        print("    TEST directories:  %s" % " ".join(sorted(test_list)))
        print("    WORK directories:  %i" % work_n)
        print("    completion table:  %i" % table_n)
        for relative in ("adm/version.py", "adm/requirement-list.txt",
                         "bin/.hwut.conf", "services/_launch_db.py",
                         "services/shell/hwut.bash", "doc/HOWTO-COMPLETION.txt"):
            print("    %-26s %s" % (relative, os.path.isfile(
                                         os.path.join(package, relative))))
        print("    bin/ holds a shim:  %s" % any(
            n.startswith("hwut") for n in os.listdir(os.path.join(package, "bin"))))
    finally:
        shutil.rmtree(os.path.dirname(stage))


def test_requirements():
    stage = staged()
    try:
        text = pyproject(stage)
        block = re.search(r"^dependencies\s*=\s*\[(.*?)\]", text,
                          re.M | re.S).group(1)
        dependency_list = re.findall(r'"([^"]+)"', block)
        row_list = census_python_rows()
        banner("the wheel's dependencies are the list's census modules")
        for d in dependency_list: print("    " + d)
        print("    the same:  %s" % (dependency_list == [p for p, _ in row_list]))
        print("    requires-python:  %s"
              % re.search(r'^requires-python\s*=\s*"([^"]+)"', text, re.M).group(1))
        banner("the Debian 'Depends', in Debian's numbering")
        sys.path.insert(0, os.path.dirname(HWUT))
        from hwut.services.lib import requirements
        depends = requirements.debian_depends()
        for each in depends.split(", "): print("    " + each)
        stated = [re.sub(r">=(.*)", r" (>= \1)", d) for _, d in row_list]
        print("    every census module there:  %s"
              % all(s in depends.split(", ") for s in stated))
    finally:
        shutil.rmtree(os.path.dirname(stage))


def test_help_missing():
    root = tempfile.mkdtemp(dir="/tmp")
    try:
        venv = os.path.join(root, "bare")
        subprocess.run([sys.executable, "-m", "venv", "--without-pip", venv],
                       check=True)
        python = os.path.join(venv, "bin", "python3")
        env = dict(os.environ, PYTHONPATH=os.path.dirname(HWUT))
        done = subprocess.run([python, "-m", "hwut.services.help"], cwd=root,
                              env=env, capture_output=True, text=True)
        banner("an interpreter without the modules: 'hwut.help'")
        print(done.stdout, end="")
        print("    status %i, stderr %r" % (done.returncode, done.stderr))
    finally:
        shutil.rmtree(root)


def test_deb():
    if shutil.which("dpkg-deb") is None:
        print("    MISSING PRECONDITION: 'dpkg-deb' is not on PATH")
        return
    root = tempfile.mkdtemp(dir="/tmp")
    try:
        subprocess.run([sys.executable, BUILD, "deb", root], check=True,
                       stdout=subprocess.DEVNULL)
        deb = [n for n in os.listdir(root) if n.endswith(".deb")][0]
        path = os.path.join(root, deb)
        control = subprocess.run(["dpkg-deb", "-f", path], check=True,
                                 capture_output=True, text=True).stdout
        field_db = dict(re.findall(r"^([A-Za-z-]+): (.*)$", control, re.M))
        member_list = subprocess.run(["dpkg-deb", "-c", path], check=True,
                                     capture_output=True, text=True).stdout
        member_list = [line.split()[5] for line in member_list.splitlines()]
        with open(os.path.join(HWUT, "adm", "version.py")) as fh:
            stated = re.search(r'"([^"]+)"', fh.read()).group(1)
        face_set = set(m[len("./usr/bin/"):] for m in member_list
                       if m.startswith("./usr/bin/hwut"))
        link_set = set(m.rsplit("/", 1)[1] for m in member_list
                       if m.startswith("./usr/share/bash-completion/completions/")
                       and not m.endswith("/"))
        shim_set = shim_face_set()
        dev_set  = set(f for f in shim_set if f.startswith("hwut.dev."))
        with open(LIST) as fh:
            python_least = re.search(r"^program\s+python3\s+census\s+python3>=(\S+)",
                                     fh.read(), re.M).group(1)
        stated_depends = ["python3 (>= %s)" % python_least] + \
                         [re.sub(r">=(.*)", r" (>= \1)", d)
                          for _, d in census_python_rows()] + ["libvterm0"]
        info = subprocess.run(["dpkg-deb", "-I", path], check=True,
                              capture_output=True, text=True).stdout
        banner("the control file")
        print("    file:          %s" % deb.replace(stated, "<version>"))
        print("    Version:       the same as adm/version.py: %s"
              % (field_db.get("Version") == stated))
        print("    Architecture:  %s" % field_db.get("Architecture"))
        print("    Depends:       the list's census rows: %s"
              % (field_db.get("Depends", "").split(", ") == stated_depends))
        banner("what it lands")
        print("    /usr/bin:      the faces of bin/ but hwut.dev.*: %s"
              % (face_set == shim_set - dev_set))
        print("    completions:   one link per face: %s" % (link_set == face_set))
        print("    package:       %s" % any(m.startswith(
              "./usr/lib/python3/dist-packages/hwut/services/_launch.py")
              for m in member_list))
        print("    TEST directories: %s" % " ".join(sorted(
              m[len("./usr/lib/python3/dist-packages/hwut/"):].rstrip("/")
              for m in member_list if m.endswith("/TEST/"))))
        print("    postinst, prerm: %s" % ("postinst" in info and "prerm" in info))
    finally:
        shutil.rmtree(root)


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "The packages are read off the tree: one version, one list, one set of faces",
        choice_map = {
            "version":      test_version,
            "faces":        test_faces,
            "requirements": test_requirements,
            "help-missing": test_help_missing,
            "deb":          test_deb,
        }).run()
