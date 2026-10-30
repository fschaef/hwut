#! /bin/bash
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title    = "Linked nominals: a '.link' in GOOD/ holds a case against another case's '.txt' (bookkeeper B-32, services E-209)"
#     choices {
#         read-through { features = ["good-link-read"] }
#         writers      { features = ["good-link-writers"] }
#         faces        { features = ["good-link-faces"] }
#         isolate      { features = ["good-link-isolate"] }
#         remove       { features = ["good-link-remove"] }
#         move         { features = ["good-link-move"] }
#         sanitize     { features = ["good-link-sanitize"] }
#     }
# }
#
# ---------------------------------------------------------------------------
#
# Ruled 2026-10-30. A tree of four test directories under one root, each
# with 'test-a.sh' (choices x, y), and 'e/' a bubble of its own:
#
# read-through  'hwut.good.link' writes 'c/TEST/GOOD/test-a.sh--x.link' and
#               the book entry; the run of 'c/TEST' passes against the text
#               it names, with no 'REGISTERED' note; 'hwut.report.details'
#               shows the link and the text it names, one subject.
# writers       the linked case's output changes: 'hwut.accept --force' is
#               refused by name -- the text is another case's GOOD -- and
#               '--unlink' gives the case its own '.txt'; the text it named
#               is untouched. 'hwut.merge' opens no session over a link.
# faces         directory to directory; again, every standing GOOD listed
#               and kept (exit 1); '--force' replaces; the refusals: a
#               link as source, a link onto its own case, a target whose
#               test does not stand, a target in another root.
#               'hwut.good.link.show' for a text, a link, a directory.
# isolate       'hwut.good.isolate' of a link, of a text (every link of it);
#               'hwut.good.rebase' points the links of one text at another,
#               and the old text is free.
# remove        'hwut.remove' of a linked text is refused, naming the links
#               and the three ways out; a linked case's removal takes its
#               link and leaves the text.
# move          'hwut.move' of a linked case writes its link anew from the
#               new place; of a linked text, every link follows it; into
#               another root, refused before anything moves.
# sanitize      '--links': a link naming nothing, a link beside its case's
#               own '.txt'; 'unlink' heals both, and refuses a sound link.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
export PYTHONPATH="$ROOT"
BIN="$ROOT/hwut/bin"
export PATH="$BIN:$PATH"
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "Linked nominals (bookkeeper B-32);"
        echo "CHOICES: read-through, writers, faces, isolate, remove, move, sanitize;"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"
CONF='hwut {\n    language-setup { bash { extensions = [".sh"] interpreter = "bash" } }\n}\n'
printf "$CONF" > hwut-root.conf
shown() {
    sed -E "s|$WORK|\$WORK|g; s/[0-9]+\.[0-9]+ \[sec\]/<t> [sec]/g;
            s/ +\|\|[0-9]+$//"
}
app() {                 # <dir> [word]: 'test-a.sh' in <dir>/TEST, x and y
    mkdir -p "$1/TEST"
    { echo '#! /bin/bash'; echo '# @hwut { choices = ["x", "y"] }'
      echo "echo \"${2:-hello} \$1\""; echo 'echo "<hwut-end>"'; } > "$1/TEST/test-a.sh"
    chmod +x "$1/TEST/test-a.sh"
}
accepted() {            # <dir>: both choices played and accepted
    ( cd "$1/TEST" && "$BIN/hwut.play" --all --plain > /dev/null 2>&1 \
      && "$BIN/hwut.accept" > /dev/null 2>&1 )
}
said() {                # <command...>: what it says, and its exit status
    "$@" 2>&1 | shown; echo "   exit ${PIPESTATUS[0]}"
}
run_of() {              # <dir>: the run's lines that matter here
    ( cd "$1/TEST" && "$BIN/hwut.run" --plain 2>&1 ) \
        | grep -E "RESULTS|NOTE|GOOD missing" | shown
}
for d in a b c; do app $d; done
accepted a

case "$1" in
    read-through)
        echo "== hwut.good.link a/TEST/GOOD/test-a.sh--x.txt c/TEST"
        said hwut.good.link a/TEST/GOOD/test-a.sh--x.txt c/TEST
        echo "== c/TEST/GOOD holds"; ls c/TEST/GOOD
        echo "== the link reads"; cat c/TEST/GOOD/test-a.sh--x.link
        echo "== hwut.run in c/TEST (y has no GOOD)"; run_of c
        echo "== hwut.report.details test-a.sh x (in c/TEST): the link and its text"
        ( cd c/TEST && "$BIN/hwut.report.details" test-a.sh x 2>&1 ) \
            | grep -E "status report|\(good " | sed -E 's/ +[0-9]+ bytes//' | shown ;;
    writers)
        hwut.good.link a/TEST c/TEST > /dev/null
        app c changed
        ( cd c/TEST && "$BIN/hwut.play" test-a.sh x --plain > /dev/null 2>&1 )
        echo "== hwut.accept --force test-a.sh x (in c/TEST)"
        ( cd c/TEST && said hwut.accept --force test-a.sh x ) | grep -E "REFUSED|exit"
        echo "== hwut.merge test-a.sh x (in c/TEST)"
        ( cd c/TEST && said hwut.merge test-a.sh x < /dev/null ) | grep -E "refused|exit"
        echo "== hwut.accept --unlink test-a.sh x (in c/TEST)"
        ( cd c/TEST && said hwut.accept --unlink test-a.sh x ) | grep -E "blessed|exit"
        echo "== c/TEST/GOOD holds"; ls c/TEST/GOOD
        echo "== its own text"; head -1 c/TEST/GOOD/test-a.sh--x.txt
        echo "== a's text, untouched"; head -1 a/TEST/GOOD/test-a.sh--x.txt ;;
    faces)
        echo "== directory to directory"
        said hwut.good.link a/TEST b/TEST
        echo "== again"
        said hwut.good.link a/TEST b/TEST
        echo "== --force, one file"
        said hwut.good.link --force a/TEST/GOOD/test-a.sh--y.txt b/TEST/GOOD/test-a.sh--y.txt
        echo "== a link as source"
        said hwut.good.link b/TEST/GOOD/test-a.sh--x.link c/TEST
        echo "== onto its own case"
        said hwut.good.link a/TEST/GOOD/test-a.sh--x.txt a/TEST/GOOD/test-a.sh--x.txt
        echo "== no test stands"
        mkdir -p d/TEST
        said hwut.good.link a/TEST/GOOD/test-a.sh--x.txt d/TEST
        echo "== into a bubble"
        app e; printf "$CONF" > e/hwut-root.conf
        said hwut.good.link a/TEST/GOOD/test-a.sh--x.txt e/TEST
        echo "== hwut.good.link.show a/TEST/GOOD/test-a.sh--x.txt"
        said hwut.good.link.show a/TEST/GOOD/test-a.sh--x.txt
        echo "== hwut.good.link.show b/TEST/GOOD/test-a.sh--y.link"
        said hwut.good.link.show b/TEST/GOOD/test-a.sh--y.link
        echo "== hwut.good.link.show (the whole root)"
        said hwut.good.link.show ;;
    isolate)
        hwut.good.link a/TEST b/TEST > /dev/null
        hwut.good.link a/TEST c/TEST > /dev/null
        echo "== hwut.good.isolate b/TEST/GOOD/test-a.sh--x.link"
        said hwut.good.isolate b/TEST/GOOD/test-a.sh--x.link
        echo "== hwut.good.isolate a/TEST/GOOD/test-a.sh--y.txt"
        said hwut.good.isolate a/TEST/GOOD/test-a.sh--y.txt
        echo "== hwut.good.rebase a/TEST/GOOD/test-a.sh--x.txt b/TEST/GOOD/test-a.sh--x.txt"
        said hwut.good.rebase a/TEST/GOOD/test-a.sh--x.txt b/TEST/GOOD/test-a.sh--x.txt
        echo "== what links now"; said hwut.good.link.show
        echo "== b and c pass"; run_of b; run_of c ;;
    remove)
        hwut.good.link a/TEST/GOOD/test-a.sh--x.txt c/TEST > /dev/null
        echo "== hwut.remove test-a.sh x (in a/TEST)"
        ( cd a/TEST && said hwut.remove test-a.sh x --dont-ask ) | grep -E "REFUSED|NOTE|exit"
        echo "== hwut.remove test-a.sh x (in c/TEST)"
        ( cd c/TEST && said hwut.remove test-a.sh x --dont-ask ) | grep -E "GOOD|exit"
        echo "== a/TEST/GOOD holds"; ls a/TEST/GOOD ;;
    move)
        hwut.good.link a/TEST/GOOD/test-a.sh--x.txt c/TEST > /dev/null
        mkdir -p d/TEST
        echo "== hwut.move c/TEST/test-a.sh d/TEST/"
        said hwut.move c/TEST/test-a.sh d/TEST/ --dont-ask | grep -E "link|exit"
        echo "== the link reads"; cat d/TEST/GOOD/test-a.sh--x.link
        mv c/TEST/test-a.sh d/TEST/
        echo "== hwut.move a/TEST/test-a.sh b2/TEST/"
        mkdir -p b2/TEST
        said hwut.move a/TEST/test-a.sh b2/TEST/ --dont-ask | grep -E "link|exit"
        mv a/TEST/test-a.sh b2/TEST/
        echo "== the link reads"; cat d/TEST/GOOD/test-a.sh--x.link
        echo "== hwut.run in d/TEST (y has no GOOD)"; run_of d
        echo "== into a bubble"
        mkdir -p e/TEST; printf "$CONF" > e/hwut-root.conf
        said hwut.move b2/TEST/test-a.sh e/TEST/ --dont-ask | grep -E "REFUSED|NOTE|exit" ;;
    sanitize)
        hwut.good.link a/TEST c/TEST > /dev/null
        cp a/TEST/GOOD/test-a.sh--x.txt c/TEST/GOOD/test-a.sh--x.txt
        hwut.good.link a/TEST/GOOD/test-a.sh--y.txt b/TEST > /dev/null
        rm c/TEST/GOOD/test-a.sh--y.link
        echo "../../nowhere/GOOD/test-a.sh--y.txt" > c/TEST/GOOD/test-a.sh--y.link
        echo "== hwut.sanitize.propose --links"
        hwut.sanitize.propose --links 2>&1 | grep -vE "^#( |$)|^$" | shown
        hwut.sanitize.propose --links -o heal.txt > /dev/null 2>&1
        echo "== hwut.sanitize.apply heal.txt"
        said hwut.sanitize.apply heal.txt | grep -E "unlink|exit"
        echo "== c/TEST/GOOD holds"; ls c/TEST/GOOD
        echo "== a sound link is not sanitize's"
        echo "unlink b/TEST/GOOD/test-a.sh--y.link" > sound.txt
        said hwut.sanitize.apply sound.txt | grep -E "unlink|exit"
        ls b/TEST/GOOD ;;
    *)
        echo "unknown choice '$1'"; exit 1 ;;
esac
echo "<hwut-end>"
