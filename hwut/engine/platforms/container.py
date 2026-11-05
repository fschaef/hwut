"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: 'container' -- a bubble run in a podman or docker image, the
         tree mounted at its own path (spec/42 section 4; rulings 17, 20,
         22).

    platform = [ { name   = "linux"
                   kind   = "container"
                   image  = "hwut-dev"                       required
                   recipe = "../adm/container/Containerfile" optional
                   engine = "podman" } ]                     optional

    image    the image the bubble runs in.
    recipe   the Containerfile that builds it where it does not stand;
             the build's context is THE ROOT. The conf's reader hands it
             here as a path that opens from anywhere (resolved against
             the conf's directory).
    engine   'podman' or 'docker'; absent: the first of them on PATH.

THE BUBBLE AND THE HWUT ARE MOUNTED AT THEIR OWN PATHS: the bubble's
directory (its own 'hwut-root.conf' bounds the far run's climb) and the
hwut that runs here -- the directory holding the package 'hwut/' -- so
both sides are one version (CONTRACT: HWUT), a path inside is the same
path outside, and what a test writes there it writes here (ruling 22).
Where the bubble lies inside that directory, as 'support/' does, one
mount holds both.

'hwut.dev.podman.build' and 'hwut.dev.podman.enter' take 'engine',
'root_of' and 'CONTAINERFILE' from here: the faces import the engine,
never the other way round.
______________________________________________________________________________
"""
import os
import shutil
import subprocess
from   datetime import datetime, timezone

from ._status              import FAR_EMPTY_STATUS
from ..protocol.line       import LineError, event_of
from ..protocol.vocabulary import event

KEY_TUPLE     = ("image", "recipe", "engine")
ENGINE_TUPLE  = ("podman", "docker")
CONTAINERFILE = os.path.join("hwut", "adm", "container", "Containerfile")

#  THE KINDS A FAR RUN HAS OF ITS OWN: the near run begins and ends the
#  tree itself (spec/42 section 5).
_SWALLOWED_KIND_SET = frozenset(("tree-begun", "tree-done"))
_ERROR_TAIL_N       = 5

#  THE HWUT THAT RUNS HERE: the directory holding the package 'hwut/'.
HWUT_HOME = os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.abspath(__file__)))))

#  THE FAR RUNS STANDING, per platform name: 'stop' ends one that outlives
#  its reader -- a signal at the near run (E-55).
_live_db = {}


def engine(wanted=None):
    """
    RETURN: str, the engine's name -- 'wanted' where given and on PATH,
            else the first of 'podman', 'docker' that stands on PATH.
            None, where none of them does.
    """
    for name in ((wanted,) if wanted else ENGINE_TUPLE):
        if shutil.which(name): return name
    return None


def root_of(directory=None):
    """
    RETURN: str, the absolute path of the directory holding 'hwut/',
            found by ascending from 'directory' (the working directory
            where none is given).
            None, where no ancestor holds one.
    """
    here = os.path.abspath(directory or os.getcwd())
    while True:
        if os.path.isdir(os.path.join(here, "hwut")) \
           and os.path.isfile(os.path.join(here, CONTAINERFILE)):
            return here
        parent = os.path.dirname(here)
        if parent == here: return None
        here = parent


def check(name, spec):
    """
    RETURN: tuple of (str, str), one (key, text) per fault of a
            'container' entry's own keys: a key not in 'KEY_TUPLE', a
            value that is no string, 'image' missing, an 'engine' that
            is neither podman nor docker. Empty, where the entry reads.
    """
    fault_list = []
    for key, value in spec.items():
        if key in ("name", "kind"): continue
        if key not in KEY_TUPLE:
            fault_list.append((key, "platform '%s': key '%s' is not a "
                                    "'container' key -- %s"
                                    % (name, key, ", ".join(KEY_TUPLE))))
        elif not isinstance(value, str):
            fault_list.append((key, "platform '%s': key '%s' wants a "
                                    "string" % (name, key)))
        elif key == "engine" and value not in ENGINE_TUPLE:
            fault_list.append((key, "platform '%s': engine '%s' is not "
                                    "known -- %s"
                                    % (name, value, ", ".join(ENGINE_TUPLE))))
    if "image" not in spec:
        fault_list.append(("kind", "platform '%s': key 'image' missing -- "
                                   "a 'container' runs in an image" % name))
    return tuple(fault_list)


def is_available(name, spec):
    """
    RETURN: (True, ""), the engine stands on PATH and the image stands,
            or a 'recipe' file stands to build it from.
            (False, why), else -- 'why' names what is missing.
    """
    tool = engine(spec.get("engine"))
    if tool is None: return (False, "no %s on PATH" % _engine_text(spec))
    image = spec["image"]
    if image_stands(tool, image): return (True, "")
    recipe = spec.get("recipe")
    if not recipe:
        return (False, "image '%s' absent and no recipe" % image)
    if not os.path.isfile(recipe):
        return (False, "image '%s' absent and recipe '%s' not found"
                       % (image, recipe))
    return (True, "")


def start(name, spec, write, log=None):
    """
    RETURN: (True, ""), the image stands -- it stood, or it was built
            now from the recipe (ruling 17).
            (False, why), else -- a failed build said by 'write' as an
            ERROR with the build's last lines; 'why' is "image build
            failed".

    The build is said once on 'write' ('BUILDING: ...'); its output goes
    to 'log', line by line (dropped where None), never to the console.
    """
    tool = engine(spec.get("engine"))
    if tool is None: return (False, "no %s on PATH" % _engine_text(spec))
    image = spec["image"]
    if image_stands(tool, image): return (True, "")
    recipe = spec.get("recipe")
    if not recipe or not os.path.isfile(recipe):
        return is_available(name, spec)
    root = root_of(os.path.dirname(os.path.abspath(recipe)))
    if root is None:
        return (False, "no directory holding '%s' above the recipe '%s'"
                       % (CONTAINERFILE, recipe))
    shown = _shown(recipe, root)
    write("BUILDING: image '%s' from %s" % (image, shown))
    status, line_list = _build(tool, image, recipe, root, log)
    if status == 0: return (True, "")
    write("ERROR: image '%s' not built from %s" % (image, shown))
    for line in line_list[-_ERROR_TAIL_N:]:
        write("       %s" % line)
    return (False, "image build failed")


def run_argv(tool, image, home, bubble_path, wish, uid, gid):
    """
    RETURN: list of str, the engine's call that runs the bubble at the
            absolute 'bubble_path' in 'image': the bubble and the hwut
            'home' (the directory holding 'hwut/') mounted at their own
            paths -- one mount where the bubble lies inside 'home' --,
            the bubble the working directory, the user kept, the far
            'hwut.run' silent with its events on stdout, one line each,
            'wish' after them.
    """
    return _engine_argv(tool, image, home, bubble_path, bubble_path,
                        [os.path.join(home, "hwut", "bin", "hwut.run"),
                         "--silent", "--events", "/dev/stdout"] + list(wish),
                        uid, gid)


def _engine_argv(tool, image, home, bubble_path, directory, command, uid,
                 gid):
    """
    RETURN: list of str, the engine's call that runs 'command' in
            'image' in 'directory': the bubble and the hwut 'home' mounted
            at their own paths -- one mount where the bubble lies inside
            'home' --, the user kept, HOME at '/tmp'.
    """
    argv = [tool, "run", "--rm", "-i"]
    if tool == "podman": argv.append("--userns=keep-id")
    else:                argv.append("--user=%i:%i" % (uid, gid))
    mount_list = [home]
    if bubble_path != home and not bubble_path.startswith(home + os.sep):
        mount_list.append(bubble_path)
    for path in mount_list:
        argv += ["-v", "%s:%s" % (path, path)]
    return argv + ["-w", directory, "-e", "HOME=/tmp", image] + list(command)


def relay(name, spec, bubble_path, directory, argv, write):
    """
    RETURN: int, the far face's exit status. 'argv' -- a face of the hwut
            that runs here, its name first ('hwut.play'), then its words
            -- ran in the image in 'directory', inside the bubble at
            'bubble_path'; each line it printed reached 'write' as it
            came, stderr with stdout. 'stop' ends it while it runs.
    """
    command = [os.path.join(HWUT_HOME, "hwut", "bin", argv[0])] + list(argv[1:])
    process = subprocess.Popen(
        _engine_argv(engine(spec.get("engine")), spec["image"], HWUT_HOME,
                     bubble_path, directory, command, os.getuid(),
                     os.getgid()),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    _live_db.setdefault(name, set()).add(process)
    try:
        for line in process.stdout: write(line.rstrip("\n"))
        return process.wait()
    finally:
        _live_db[name].discard(process)


def run(name, spec, bubble, wish, sink, root=None):
    """
    RETURN: int, the far run's exit status. Each far event line reached
            'sink' as it came, translated: tree-begun and tree-done
            dropped, 'directory' put below 'bubble', 'platform' added,
            the time reckoned from the far 'tree-begun'; an unreadable
            line and a status other than 0, 1 and 3 each a 'fault'
            event (ruling 20); 3 is EMPTY -- the far wish selected
            nothing, which is no more a fault over there than it is
            here (2026-11-04).

    'bubble' is the bubble's directory relative to 'root', the near
    run's root (the working directory where None); 'wish' the far
    'hwut.run's words. The far process is 'stop's to end while it runs.
    """
    root        = os.path.abspath(root or os.getcwd())
    bubble_path = os.path.normpath(os.path.join(root, bubble))
    argv = run_argv(engine(spec.get("engine")), spec["image"], HWUT_HOME,
                    bubble_path, wish, os.getuid(), os.getgid())
    process = subprocess.Popen(argv, stdout=subprocess.PIPE, text=True)
    _live_db.setdefault(name, set()).add(process)
    origin = None
    try:
        for line in process.stdout:
            if not line.strip(): continue
            try:
                far = event_of(line, origin)
            except LineError:
                sink(_fault(bubble, "platform '%s' said: %s"
                                    % (name, line.rstrip("\n")), name))
                continue
            if far["kind"] == "tree-begun": origin = far["when"]
            near = translated(far, bubble, name)
            if near is not None: sink(near)
        status = process.wait()
    finally:
        _live_db[name].discard(process)
    if status not in (0, 1, FAR_EMPTY_STATUS):
        sink(_fault(bubble, "platform '%s' ended with status %i"
                            % (name, status), name))
    return status


def translated(far, bubble, name):
    """
    RETURN: dict, the far event as a near one: its 'directory' below
            'bubble' ('.' becomes 'bubble'), 'platform' set to 'name'.
            None, for a kind the near run has of its own (tree-begun,
            tree-done).
    """
    if far["kind"] in _SWALLOWED_KIND_SET: return None
    near = {key: value for key, value in far.items() if key != "t"}
    if "directory" in near:
        near["directory"] = os.path.normpath(
            os.path.join(bubble, near["directory"]))
    near["platform"] = name
    return near


def stop(name, spec):
    """
    RETURN: None. Every far run of platform 'name' still standing is
            terminated, and waited for -- a near run ended by a signal
            leaves none behind (E-55). '--rm' removes the container.
    """
    for process in tuple(_live_db.get(name, ())):
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def image_stands(tool, image):
    """RETURN: True, 'image' stands in the engine's store; False, else."""
    return subprocess.run([tool, "image", "inspect", image],
                          stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL).returncode == 0


def _build(tool, image, recipe, root, log):
    """
    RETURN: (int, list of str), the build's exit status and its output
            lines, stdout and stderr merged; each line also given to
            'log' where one is.
    """
    process = subprocess.Popen([tool, "build", "-t", image, "-f",
                                os.path.abspath(recipe), "."], cwd=root,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True)
    line_list = []
    for line in process.stdout:
        line = line.rstrip("\n")
        line_list.append(line)
        if log is not None: log(line)
    return process.wait(), line_list


def _shown(recipe, root):
    """
    RETURN: str, 'recipe' as the tree names it: relative to the tree's
            top, '<root>/hwut' -- 'adm/container/Containerfile'.
    """
    return os.path.relpath(os.path.abspath(recipe),
                           os.path.join(root, "hwut"))


def _engine_text(spec):
    """
    RETURN: str, the engine the spec asks for, or 'podman or docker'
            where it asks for none.
    """
    return spec.get("engine") or " or ".join(ENGINE_TUPLE)


def _fault(bubble, text, name):
    """
    RETURN: dict, a 'fault' event on 'bubble' saying '<bubble>/: text',
            'platform' set to 'name'.
    """
    near = event("fault", datetime.now(timezone.utc).isoformat(),
                 directory=bubble, text="%s/: %s" % (bubble, text))
    near["platform"] = name
    return near
