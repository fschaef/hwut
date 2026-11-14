#! /bin/bash
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title      = "The urgency reaction: a face that cannot run says what this machine is."
#     choices {
#         module-absent  { features = ["face-urgency-module-absent"] }
#         no-python      { features = ["face-urgency-no-python"] }
#         too-old        { features = ["face-urgency-python-too-old"] }
#         crash          { features = ["face-urgency-crash"] }
#         endings        { features = ["face-launch-transparent"] }
#     }
# }
#
# ---------------------------------------------------------------------------
#
# THE URGENCY REACTION (services E-224, ruled 2026-11-12: "A plus
# signals"). MEASURED BEFORE: a face without 'bidict' ended in a
# traceback through 'engine/compare/contract/analogy_db.py'; a machine
# without 'python3' in '/bin/sh: python3: not found', status 127; a crash
# in 'Segmentation fault' and nothing else.
#
# module-absent  a bare interpreter ('venv --without-pip') first on PATH:
#                'hwut.run' reports, status 1.
# no-python      PATH holds only what the shim and '_no_python.sh' call,
#                as 'exec <abs path>' wrappers (E-197): status 127.
# too-old        the age check, on the versions either side of the
#                requirement list's 'python3' minimum.
# crash          a 'bidict' on PYTHONPATH whose import segfaults: the
#                Python stack, the report, and the launcher DIES BY SEGV
#                (a parent reads it as such, not as status 139).
# endings        what the watcher must not change: 0, 2, 3 as the faces
#                say them; SIGTERM sent to the launcher ALONE ends the
#                face once ('ended forcefully', 143).
#
# THE BLOCK'S VALUES ARE MACHINE FACTS (determinism law): 'masked' keeps
# each key and replaces its value by '...'; 'face' and 'problem' stand;
# 'missing' shows the 'python' rows of a bare interpreter, which lacks
# them all on every machine; the place in 'failed' is code, masked too.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
BIN=$(cd "$HERE/../../bin" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)

case "$1" in
    --hwut-info)
        echo "The urgency reaction: a face that cannot run says what this machine is.;"
        echo "CHOICES: module-absent, no-python, too-old, crash, endings;"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"
printf 'hwut {\n}\n' > hwut-root.conf

masked() {
    awk '
        /^<hwut-system>$/  { inside = 1; print; next }
        /^<\/hwut-system>$/ { inside = 0; print; next }
        !inside            { print; next }
        /^(face|problem):/ { print; next }
        /^failed:/         { key = 0; sub(/ \([^()]*\)$/, " (...)"); print; next }
        /^missing:/        { key = 1; show($0); next }
        /^ /               { if (key) show($0); next }
        { key = 0; sub(/:.*/, ": ..."); print }
        function show(line) {
            if (line ~ /python [A-Za-z_]+ \(/) { print line }
            else if (line ~ /^missing:/) { sub(/:.*/, ": ...", line); print line }
        }'
}

if [ "$1" == "module-absent" ]; then
    python3 -m venv --without-pip "$WORK/bare"
    PATH="$WORK/bare/bin:$PATH" "$BIN/hwut.run" --plain > out.txt 2> err.txt
    echo "status $?, stdout $(wc -c < out.txt) bytes"
    masked < err.txt
fi

if [ "$1" == "no-python" ]; then
    mkdir tools
    for tool in dirname readlink basename sed uname; do
        printf '#! /bin/sh\nexec %s "$@"\n' "$(command -v $tool)" > tools/$tool
        chmod +x tools/$tool
    done
    PATH="$WORK/tools" /bin/sh "$BIN/hwut.run" --plain > out.txt 2> err.txt
    echo "status $?, stdout $(wc -c < out.txt) bytes"
    masked < err.txt
fi

if [ "$1" == "too-old" ]; then
    PYTHONPATH="$ROOT" python3 - <<'EOF'
from hwut.services._launch import too_old_problem, least_python
least = least_python()
print("least  %s" % least)
for version in ((3, 8, 10), (3, 9, 18), (3, 10, 0), (3, 13, 1)):
    print("%-10s %s" % (".".join(map(str, version)),
                        too_old_problem(version, least)))
EOF
fi

if [ "$1" == "crash" ]; then
    mkdir -p fake/bidict
    printf 'import ctypes\nctypes.string_at(0)\n' > fake/bidict/__init__.py
    PYTHONPATH="$WORK/fake" python3 - "$BIN/hwut.run" err.txt <<'EOF'
import signal, subprocess, sys
done = subprocess.run([sys.argv[1], "--plain"], capture_output=True, text=True)
print("launcher: %s" % ("killed by %s" % signal.Signals(-done.returncode).name
                        if done.returncode < 0 else
                        "status %i" % done.returncode))
print("stdout %i bytes" % len(done.stdout))
with open(sys.argv[2], "w") as fh: fh.write(done.stderr)
EOF
    sed -n '/^Fatal Python error/p; /^hwut\.run was killed/,$p' err.txt | masked
fi

if [ "$1" == "endings" ]; then
    "$BIN/hwut.about" > /dev/null 2>&1;            echo "hwut.about            status $?"
    "$BIN/hwut.run" --no-such-option > /dev/null 2>&1; echo "hwut.run --no-such   status $?"
    "$BIN/hwut.run" --plain > /dev/null 2>&1;      echo "hwut.run (no tests)   status $?"
    printf 'on: "x" => flush;\non: <else> => ignore;\non: <eof> => ignore;\n' > f.pype
    mkfifo in
    sleep 60 > in &
    writer=$!
    "$BIN/hwut.pype" f.pype < in > out.txt 2> err.txt &
    face=$!
    #  THE WATCHER MUST STAND before it is signalled: the shim is
    #  replaced by python, which forks the face.
    for i in $(seq 100); do
        [ "$(pgrep -P $face | wc -l)" -ge 1 ] && break
        sleep 0.1
    done
    kill -TERM $face
    wait $face
    echo "hwut.pype, TERM to the launcher alone: status $?"
    kill $writer 2> /dev/null
    sed 's/^/    stderr: /' err.txt
fi
echo "<hwut-end>"
