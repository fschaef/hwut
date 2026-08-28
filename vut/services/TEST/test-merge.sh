#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title      = "The merge service face: channels, exit codes, the commit law."
#     choices    = ["cancel", "commit", "stdout_artifact"]
#     eq-pattern = ["SUCCESS.*"]
# }
#
# ---------------------------------------------------------------------------
#
# THE MERGE SERVICE, IN ITS NATURAL HABITAT. The caller is the shell --
# as it will be in the field. What this test owns is the FACE: the
# argument language, the channel discipline, the exit codes, and WHEN
# the artifact is written. The renderer the face drives is tested where
# it lives: interaction/TEST.
#
#     stdin ──► hwut.merge SUBJECT NOMINAL [-o PATH] ──► artifact
#     (the author's answers)        │
#                                   └────► stderr: the UI
#
#     THE CHANNEL LAW      UI on stderr; the artifact on '-o PATH' or,
#                          without '-o', on stdout -- and NOTHING else
#                          ever on the artifact channel.
#     THE COMMIT LAW       written ONLY on commit; a cancel writes
#                          nothing, not even an empty file.
#     THE EXIT CODES       0 commit; 1 cancel; 2 unusable request.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
MERGE="python3 -m vut.services.merge"
export PYTHONPATH="$ROOT"

case "$1" in
    --hwut-info)
        echo "The merge service face: channels, exit codes, the commit law.;"
        echo "CHOICES: commit, cancel, stdout_artifact;"
        echo "HAPPY: SUCCESS.*;"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"

#  THE TREE'S BOUNDARY. Every face ASCENDS collecting 'hwut.conf'
#  until it meets this file; a tree without one is refused, so a
#  fixture states its own. Empty says only 'the tree ends here'.
printf 'hwut {\n}\n' > hwut-root.conf

printf 'alpha\nbeta\n'  > subject.txt
printf 'alpha\nBETA\n'  > nominal.txt

show_file() {           # <path>  -- the file's content, framed;
                        # an absent file is SAID, not a sed error
    if [ -e "$1" ]; then
        echo "          $1 {"
        sed 's/^/              /' "$1"
        echo "          }"
    else
        echo "          $1 : (absent)"
    fi
}

case "$1" in

commit)
    #  The author answers 'c'. The artifact appears at -o, whole; the
    #  UI went to stderr and stdout carried NOTHING.
    echo "STIMULUS  subject.txt: alpha, beta      nominal.txt: alpha, BETA"
    echo "          echo c | hwut.merge subject.txt nominal.txt -o merged.txt --plain"
    echo c | $MERGE subject.txt nominal.txt -o merged.txt --plain \
                    > out.txt 2> ui.txt
    echo "REACTION  exit code : $?"
    show_file merged.txt
    echo "          stdout    : $(wc -c < out.txt) bytes"
    echo "          stderr    : carries the UI -- banner seen: \
$(grep -c 'round 1' ui.txt) time(s)"
    echo
    echo "The artifact is the NOMINAL AS COMMITTED; the UI never"
    echo "touches the artifact channel."
    echo "SUCCESS: commit writes the artifact to -o, and only there."
    ;;

cancel)
    #  The author answers 'q'. NOTHING may exist afterwards -- an empty
    #  file at -o would still be a lie ('a merge happened here').
    echo "STIMULUS  the same streams,"
    echo "          echo q | hwut.merge subject.txt nominal.txt -o merged.txt --plain"
    echo q | $MERGE subject.txt nominal.txt -o merged.txt --plain \
                    > out.txt 2> ui.txt
    code=$?
    if [ -e merged.txt ]; then exists="yes -- IT MUST NOT"; else exists="no"; fi
    echo "REACTION  exit code       : $code"
    echo "          merged.txt exists: $exists"
    echo "          stdout          : $(wc -c < out.txt) bytes"
    echo
    echo "A cancel carries nothing out: no artifact, no empty file, no"
    echo "half-written one."
    echo "SUCCESS: cancel is exit 1 and an untouched file system."
    ;;

stdout_artifact)
    #  Without '-o' the artifact rides stdout -- byte-exact, so the
    #  service composes in a pipe like any shell citizen:
    #
    #      hwut.merge S N | consumer
    echo "STIMULUS  echo c | hwut.merge subject.txt nominal.txt --plain"
    echo "          (no -o: the artifact channel is stdout)"
    echo c | $MERGE subject.txt nominal.txt --plain > out.txt 2> ui.txt
    echo "REACTION  exit code : $?"
    show_file out.txt
    echo "          stderr    : still the UI -- banner seen: \
$(grep -c 'round 1' ui.txt) time(s)"
    echo
    echo "The channels never mix: the pipe downstream receives the"
    echo "artifact and not one byte of conversation."
    echo "SUCCESS: without -o, stdout IS the artifact channel, exactly."
    ;;

*)
    echo "unknown choice: '$1'" >&2
    exit 1 ;;
esac
