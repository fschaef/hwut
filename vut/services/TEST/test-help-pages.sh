#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title   = "'--help' of every face: one manual page shape, examples that run."
#     choices = ["examples", "shape"]
# }
#
# ---------------------------------------------------------------------------
#
# EVERY FACE'S '--help' IS A MANUAL PAGE (services E-32, AMENDED r-11b):
# NAME first, USAGE in capitals right below it, then the DESCRIPTION, and
# an EXAMPLE at the end where the face has one ('_core.EXAMPLE_DB').
#
# shape     every launcher in 'bin/', asked '--help': the exit, the line
#           each section stands on being BELOW the one before, USAGE
#           naming the face itself, nothing on stderr. A face whose page
#           has another shape is named with what is missing.
# examples  every example line of every face that states one, TYPED in a
#           test directory of a fresh tree whose cases are run and
#           accepted: the exit, and what was refused. An example its own
#           face refuses is a page that lies. A line that needs a person
#           -- '$EDITOR', or a question a terminal must answer -- says so
#           and is not typed.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
VUT=$(cd "$HERE/../.." && pwd)

case "$1" in
    --hwut-info)
        echo "'--help' of every face: one manual page shape, examples that run.;"
        echo "CHOICES: examples, shape;"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

app() {     #  <name> <header line> <body line>: one test application
    { echo '#! /bin/bash'; echo '# @hwut {'; echo "#     $2"; echo '# }'
      echo "$3"; echo 'echo "<hwut-end>"'; } > "$1"
    chmod +x "$1"
}

tree() {    #  a fresh tree, run and accepted; the shell stands in its TEST
    rm -rf "$WORK/tree"; mkdir -p "$WORK/tree/TEST"; cd "$WORK/tree/TEST"
    printf 'hwut {\n    language-setup { bash { extensions = [".sh"] interpreter = "bash" } }\n}\n' \
        > ../hwut-root.conf
    app test-parse.sh 'title = "parse"' 'echo parsed'
    app test-old.sh   'title = "old"'   'echo old'
    app test-gone.sh  'title = "gone"'  'echo gone'
    app test-net1.sh  'title = "net"'   'echo net'
    app test-io.sh    'title = "io"  choices = ["big", "small"]' 'echo "$1"'
    "$VUT/bin/hwut.run" --silent                 > /dev/null 2>&1 < /dev/null
    "$VUT/bin/hwut.accept" --dont-ask --force    > /dev/null 2>&1 < /dev/null
}

case "$1" in
    shape)
        cd "$WORK"
        for face in "$VUT"/bin/hwut "$VUT"/bin/hwut.*; do
            name=$(basename "$face")
            "$face" --help > page.txt 2> err.txt < /dev/null
            status=$?
            n=$(grep -n -m1 '^NAME$'        page.txt | cut -d: -f1)
            u=$(grep -n -m1 '^USAGE$'       page.txt | cut -d: -f1)
            d=$(grep -n -m1 '^DESCRIPTION$' page.txt | cut -d: -f1)
            e=$(grep -n -m1 '^EXAMPLE$'     page.txt | cut -d: -f1)
            said=""
            [ "$status" = 0 ]  || said="$said exit=$status"
            [ -s err.txt ]     && said="$said stderr-spoke"
            [ "$n" = 1 ]       || said="$said NAME-not-first"
            [ -n "$u" ] && [ "$u" -le 10 ] || said="$said USAGE-not-near-top"
            [ -n "$d" ] && [ "$d" -gt "${u:-0}" ] || said="$said DESCRIPTION-missing"
            [ -z "$e" ] || [ "$e" -gt "${d:-0}" ] || said="$said EXAMPLE-not-last"
            #  'hwut' alone is 'hwut.run' under its short name.
            own=$name; [ "$name" = hwut ] && own=hwut.run
            sed -n "$((u + 1))p" page.txt | grep -q "^    $own\b" \
                || said="$said USAGE-names-another-face"
            printf '%-28s %-9s %s\n' "$name" \
                   "$([ -n "$e" ] && echo EXAMPLE || echo -)" "${said:- ok}"
        done ;;
    examples)
        export PYTHONPATH="$(dirname "$VUT")"
        export PATH="$VUT/bin:$PATH"
        python3 -c '
from vut.services._core import EXAMPLE_DB
for name in sorted(EXAMPLE_DB):
    for line in EXAMPLE_DB[name].split("\n"):
        print("%s\t%s" % (name, line.split("   ")[0].strip()))' > "$WORK/lines.txt"
        last=""
        while IFS=$'\t' read -r name line; do
            if [ "$name" != "$last" ]; then
                echo "-- $name"; tree; last=$name
            fi
            case "$line" in
                *EDITOR*)             echo "   \$ $line"
                                      echo "     (a person's step)"
                                      continue ;;
                "hwut.sanitize root") echo "   \$ $line"
                                      echo "     (asks at a terminal)"
                                      continue ;;
            esac
            echo "   \$ $line"
            #  '--dont-ask' IS THIS TEST'S, where the face would ask: no
            #  person stands here to answer.
            typed=$line
            case "$line" in
                "hwut.accept "*|"hwut.move "*|"hwut.rename "*|"hwut.remove "*)
                    typed="$line --dont-ask" ;;
            esac
            eval "timeout 100 $typed" > out.txt 2>&1 < /dev/null
            echo "     exit $?"
            grep -E "^(REFUSED|FAULT|usage:|MERGE|    (blessed|merge|undecided|skipped))" out.txt | sed "s/^/     | /"
        done < "$WORK/lines.txt" ;;
esac
echo "<hwut-end>"
