#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title      = "The hwut.run.play face: run one test, show the reading"
#     choices    = ["build", "pyped", "reading", "refused", "silent",
#                   "solo", "stderr"]
# }
#
# ---------------------------------------------------------------------------
#
# 'hwut.run.play <test-app> [<choice>]' -- run one test and display the
# READING of what it produced, under the TEST'S OWN setup (disc-4).
#
# pyped     THE THREE VIEWS. The default shows THE SUBJECT -- what
#           enters the comparator; '--raw' what the application
#           produced; '--pyped' what the pype made of it. Each is a
#           named region. A test WITH a pype shows three different
#           pictures; the middle one is what the filter did.
# reading   the test's declared tolerance governs, not the command
#           line's: a number is marked '{numeric}' where the
#           application declares a tolerance, and stands plain where
#           it declares none. THIS IS THE WHOLE POINT of the face.
# solo      an application offering ONE choice plays it unasked; one
#           offering SEVERAL and given none is REFUSED -- playing 'the
#           first' would run the author's program under a choice
#           nobody asked for.
# stderr    '--stderr' shows the error stream, MARKED as never tested
#           (E-5): seeing is not judging.
# build     a build that fails is the reason there is nothing to play;
#           its log is shown plainly and the face stops.
# silent    a choice producing nothing to read answers EMPTY.
# refused   by name: no such application, no such choice, an option
#           the face does not take, two words too many.
#
# PLAY RECORDS NOTHING, and the 'reading' choice proves it: the
# directory holds afterwards exactly what it held before.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
export PYTHONPATH="$ROOT"
export PATH="$ROOT/vut/bin:$PATH"    # '#! /usr/bin/env hwut.pype'
FACE="python3 -m vut.services.lib.run.play"
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "The hwut.run.play face: run one test, show the reading;"
        echo "CHOICES: reading, pyped, solo, stderr, build, silent, refused;"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"

printf 'hwut {\n}\n' > hwut-root.conf

face() {                # <args...> -- status, stdout, stderr
    $FACE "$@" --plain > out.txt 2> err.txt
    echo "STATUS: $?"
    echo "STDOUT {"; sed "s|$WORK|<work>|g" < out.txt \
                     | sed 's/^/    /'; echo "}"
    if [ -s err.txt ]; then
        echo "STDERR {"; sed "s|$WORK|<work>|g" < err.txt \
                         | sed 's/^/    /'; echo "}"
    fi
}

standing() {            # what the directory holds -- play writes none of it
    echo "STANDING {"
    ( cd suite/TEST && find . -not -name "." | sed 's|^\./||' | sort \
      | sed 's/^/    /' )
    echo "}"
}

fixture() {             # one directory, applications written per choice
    mkdir -p suite/TEST/GOOD
    printf 'hwut {\n    on_entry = "true"\n    on_exit  = "true"\n}\n' \
        > suite/TEST/hwut.conf
}

app() {                 # <name> <header-tail> <body>
    printf '#! /bin/bash\n# @hwut { %s }\n%s\necho "<hwut-end>"\n' \
        "$2" "$3" > "suite/TEST/$1"
    chmod +x "suite/TEST/$1"
}

# ---------------------------------------------------------------------------
case "$1" in

reading)
    #  THE TEST'S OWN SETUP GOVERNS.
    fixture
    app test-loose.sh 'title = "L"  tolerance { numeric_ratio = 0.01 }' \
        'echo "value 3.14159 done"'
    app test-exact.sh 'title = "E"' \
        'echo "value 3.14159 done"'
    echo "--- the application declares a tolerance: the number is marked"
    face --directory=suite/TEST test-loose.sh
    echo "--- the application declares none: it stands plain"
    face --directory=suite/TEST test-exact.sh
    echo "--- and PLAY RECORDED NOTHING:"
    standing
    ;;

pyped)
    #  THE VIEW THAT EARNS ITS KEEP: a pype is part of the test
    #  application, an artifact that may contain errors, and therefore
    #  part of the oracle. An author debugging one must see what it
    #  did to the stream.
    fixture
    printf '#! /bin/bash\n# @hwut { title = "P"  pype = "./tidy.pype" }\necho "pid 41288 started"\necho "value 7"\necho "<hwut-end>"\n' \
        > suite/TEST/test-pyped.sh
    chmod +x suite/TEST/test-pyped.sh
    {
      echo '#! /usr/bin/env hwut.pype'
      echo 'on: <bol> "pid" <int> => {'
      echo '    print("pid <n> started")'
      echo '}'
      echo 'on: <else> => {'
      echo '    print(pype.line())'
      echo '}'
    } > suite/TEST/tidy.pype
    chmod +x suite/TEST/tidy.pype
    echo "--- all three views of a pyped test"
    face --directory=suite/TEST test-pyped.sh --raw --pyped
    echo "--- and where NO pype stands, the view says so"
    app test-plainly.sh 'title = "N"' 'echo "nothing filters me"'
    face --directory=suite/TEST test-plainly.sh --pyped
    ;;

solo)
    fixture
    app test-one.sh   'title = "One"'                  'echo "only"'
    app test-many.sh  'title = "Many"  choices = ["a", "b"]' \
                      'echo "choice $1"'
    echo "--- one choice: played unasked"
    face --directory=suite/TEST test-one.sh
    echo "--- several, none named: refused, and they are listed"
    face --directory=suite/TEST test-many.sh
    echo "--- the selection is the WISH'S, so a glob works too"
    face --directory=suite/TEST "test-o*.sh"
    echo "--- named: played"
    face --directory=suite/TEST test-many.sh b
    ;;

stderr)
    fixture
    app test-noisy.sh 'title = "N"' \
        'echo "out"; echo "a warning" >&2'
    echo "--- by default the error stream is not shown"
    face --directory=suite/TEST test-noisy.sh
    echo "--- '--stderr' shows it, marked as never tested"
    face --directory=suite/TEST test-noisy.sh --stderr
    ;;

build)
    fixture
    printf '#! /bin/bash\n# @hwut { title = "B"  build { framework = "make"  executable = "app" } }\necho "never reached"\necho "<hwut-end>"\n' \
        > suite/TEST/test-built.sh
    chmod +x suite/TEST/test-built.sh
    printf 'app:\n\t@echo "compiling"; echo "error: no such header" >&2; exit 1\n' \
        > suite/TEST/Makefile
    face --directory=suite/TEST test-built.sh
    ;;

silent)
    fixture
    printf '#! /bin/bash\n# @hwut { title = "S" }\nexit 0\n' \
        > suite/TEST/test-mute.sh
    chmod +x suite/TEST/test-mute.sh
    face --directory=suite/TEST test-mute.sh
    ;;

refused)
    fixture
    app test-here.sh 'title = "H"' 'echo "hi"'
    echo "--- no such application"
    face --directory=suite/TEST test-nowhere.sh
    echo "--- no such choice"
    face --directory=suite/TEST test-here.sh nochoice
    echo "--- an option the face does not take"
    face --directory=suite/TEST test-here.sh --sideways
    echo "--- two words too many"
    face --directory=suite/TEST test-here.sh a b
    echo "--- no application named at all"
    face --directory=suite/TEST
    ;;

*)
    echo "no such choice: $1"
    exit 1 ;;
esac

#  THE CLOSING TOKEN, PRINTED BY THE SCRIPT ITSELF -- without it
#  'hwut.accept' refuses every candidate this suite ever produces.
echo "<hwut-end>"
