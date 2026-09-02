#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title      = "The hwut.report face: the databases, rendered."
#     choices    = ["json", "junit", "never_run", "refused", "stain",
#                   "tap", "traditional", "width"]
#     tolerance { eq_pattern = ["STATUS: [0-9]"] }
# }
#
# ---------------------------------------------------------------------------
#
# THE 'hwut.report' FACE -- what the result databases hold, rendered
# for somebody else.
#
# NOTE: no 'hwut-info.dat' stands in these fixtures, so the directory
# TITLE is absent and the page omits it -- which is itself pinned. A
# directory that HAS one triggers the '--hwut-info' interview, and that
# path wants 'procsitter/chain.py', which this tree does not hold.
#
# traditional  the HWUT page at a stated width: the per-directory
#              blocks, the summary with its prefix-elided directory
#              column, the failures listed once more, the total.
# width        the page fills what it is given: the same report at two
#              widths, the verdicts right-aligned in both.
# junit        the XML, well-formed, and PARSED to prove it.
# tap          version 13, the plan first.
# json         the document, its verdicts true/false/null.
# stain        A STAIN IS A FAILURE IN EVERY FORMAT, never a 'skipped':
#              JUnit goes red and the message names it.
# never_run    a case the books never saw: 'never run', verdict null,
#              and the page still counts it.
# refused      an unknown format, a bad width, an unknown option, a
#              directory that is not there.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
export PYTHONPATH="$ROOT"
FACE="python3 -m vut.services.report"
RUN="python3 -m vut.services.run"
STABILITY="python3 -m vut.services.stability"
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "The hwut.report face: the databases, rendered.;"
        echo "CHOICES: traditional, width, junit, tap, json, stain, never_run, refused;"
        echo "HAPPY: STATUS: [0-9];"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"

#  THE TREE'S BOUNDARY. Every face ASCENDS collecting 'hwut.conf'
#  until it meets this file; a tree without one is refused, so a
#  fixture states its own. Empty says only 'the tree ends here'.
printf 'hwut {\n}\n' > hwut-root.conf

face() {
    $FACE "$@" > out.txt 2> err.txt
    echo "STATUS: $?"
    echo "STDOUT {"; sed 's/^/    /' < out.txt; echo "}"
    if [ -s err.txt ]; then
        echo "STDERR {"; sed 's/^/    /' < err.txt; echo "}"
    fi
}

mask() {    # the recorded instant is the machine's
    sed -E 's/[0-9]{4}y[0-9]{2}m[0-9]{2}d [0-9]{2}h[0-9]{2}/YYYYyMMmDDd hhhmm/g
            s/"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:]+Z"/"<instant>"/g'
}

masked() {
    $FACE "$@" > out.txt 2> err.txt
    echo "STATUS: $?"
    echo "STDOUT {"; mask < out.txt | sed 's/^/    /'; echo "}"
}

fixture() {         # <body...> -- one directory, one app, run
    mkdir -p tree/suite/TEST/GOOD
    printf 'hwut {\n    on_entry = "true"\n    on_exit  = "true"\n}\n' \
        > tree/suite/TEST/hwut.conf
    { echo '#!/bin/bash'; printf '%s\n' "$@"; } > tree/suite/TEST/test-app.sh
    chmod +x tree/suite/TEST/test-app.sh
}

good_app() { fixture '# @hwut { title = "The steady one" }' \
                     'echo "steady line"' 'echo "<hwut-end>"'; }

mixed() {           # one standing, one differing
    good_app
    printf 'steady line\n<hwut-end>\n' > tree/suite/TEST/GOOD/test-app.sh.txt
    printf '#!/bin/bash\n# @hwut { title = "The differing one" }\necho "what the run says"\necho "<hwut-end>"\n' \
        > tree/suite/TEST/test-diff.sh
    chmod +x tree/suite/TEST/test-diff.sh
    printf 'what the GOOD expects\n<hwut-end>\n' \
        > tree/suite/TEST/GOOD/test-diff.sh.txt
    $RUN --directory=tree --silent > /dev/null 2>&1
}

flipping() {
    fixture '# @hwut { title = "The flip" }' \
            'n=0' '[ -f count.txt ] && n=$(cat count.txt)' \
            'echo $((n + 1)) > count.txt' \
            'if [ $((n % 2)) -eq 0 ]; then echo "steady line";' \
            'else echo "other"; fi' 'echo "<hwut-end>"'
    printf 'steady line\n<hwut-end>\n' > tree/suite/TEST/GOOD/test-app.sh.txt
}

# ---------------------------------------------------------------------------
case "$1" in

traditional)
    mixed
    masked --directory=tree --width=78
    ;;

width)
    #  The page fills what it is given; the verdicts stay in a line.
    mixed
    echo "--- 60 columns"
    masked --directory=tree --width=60
    echo "--- 100 columns"
    masked --directory=tree --width=100
    ;;

junit)
    mixed
    masked --directory=tree --format=junit
    echo "--- and it parses:"
    $FACE --directory=tree --format=junit --out=r.xml > /dev/null 2>&1
    python3 -c "
import xml.dom.minidom as m
d = m.parse('r.xml')
s = d.getElementsByTagName('testsuites')[0]
print('    testsuites tests=%s failures=%s'
      % (s.getAttribute('tests'), s.getAttribute('failures')))"
    ;;

tap)
    mixed
    masked --directory=tree --format=tap
    ;;

json)
    mixed
    masked --directory=tree --format=json
    ;;

stain)
    #  A STAIN IS A FAILURE IN EVERY FORMAT -- never a 'skipped'.
    flipping
    $STABILITY --directory=tree --repeat=4 > /dev/null 2>&1
    echo "--- traditional"
    masked --directory=tree --width=70
    echo "--- junit"
    masked --directory=tree --format=junit
    echo "--- tap"
    masked --directory=tree --format=tap
    ;;

never_run)
    #  The books never saw it: 'never run', verdict null, still counted.
    good_app
    echo "--- traditional"
    masked --directory=tree --width=70
    echo "--- json"
    masked --directory=tree --format=json
    ;;

refused)
    mixed
    face --directory=tree --format=yaml
    face --directory=tree --width=0
    face --directory=tree --sideways
    face --directory=nowhere
    ;;

*)
    echo "no such choice: $1"
    exit 1 ;;
esac
