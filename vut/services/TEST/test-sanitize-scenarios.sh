#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title      = "hwut.sanitize.propose: every scenario it reports, once"
#     choices    = ["catalogue"]
# }
#
# ---------------------------------------------------------------------------
#
# THE CATALOGUE OF WHAT SANITIZE REPORTS (services E-125, E-126). One
# tree, one directory per scenario, named after it; the GOOD is what
# 'hwut.sanitize.propose' says about the tree -- its proposal on stdout,
# its NOTEs on stderr. A scenario that stops being reported, or starts
# being reported where it must not, moves this page.
#
#   PROPOSED (stdout)
#     s01-session         'TMP/session/' outlived its run      remove
#     s02-lock-dead       a lock whose holder is gone          remove
#     s03-lock-nameless   a lock that names no holder          remove
#     s04-out             'OUT/' holding files                 remove
#     s05-transient       'OUT/' and 'TMP/' whole (--transient) remove
#                         -- its empty 'OUT/' is no product space
#     s06-orphan-test     records of an application gone       forget
#     s07-orphan-choice   records of a choice not offered      forget
#     s08-book-behind     a nominal, and no book row           book
#     s09-book-stale      the book says aspirant, a nominal    book
#     s10-constraint      a nominal breaks its constraint,     remark
#                         and one never binds a variable
#     s12-target          '--target clean', bound here         run
#   A MOVE IS AN ADD PLUS A REMOVE (E-131): what the other side holds
#   decides what is proposed for records whose application is gone.
#     s13-orphan-moved    it stands in 'c06-home', where       move
#                         nothing is recorded of it: the
#                         records are carried after it
#     s14-orphan-readded  it stands in 'c07-readded', and is   forget
#                         recorded there: '# recorded anew in'
#     s15-orphan-twice    it stands in 'c08-one' and           forget
#                         'c09-two': '# possibly moved to'
#                         (E-130; the note is never read)
#   SAID, NOT PROPOSED (stderr, NOTE)
#     n01-out-live        'OUT/' of a directory a live run holds
#     n02-choiceless      choice-less records of a test with choices
#     n03-fault           exploration faults: orphans not judged
#     n04-wish            the wish hides cases: orphans not judged
#     n05-register        the register cannot be read: books not judged
#   NEVER PROPOSED, NEVER SAID (controls)
#     c01-aspirant        an aspirant with no nominal (B-14)
#     c02-run-booked      a nominal the book knows by a run (B-25)
#     c03-live-lock       a lock whose holder lives
#     c04-remarked        a constraint finding already written
#     c05-unreachable     an application that stands, hidden by 'ignore'
#     c06-home            where the application of s13 stands now
#     c07-readded         where s14's stands, accepted there
#     c08-one, c09-two    where s15's stands twice
#
# Every directory but s08 and s09 holds one application, accepted: its
# nominal and its book row agree, so it adds nothing but its scenario.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
export PYTHONPATH="$ROOT"
PROPOSE="python3 -m vut.services.lib.sanitize.propose"
COMMAND="python3 -m vut.services.sanitize"
APPLY="python3 -m vut.services.lib.sanitize.apply"
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "hwut.sanitize.propose: every scenario it reports, once;"
        echo "CHOICES: catalogue;"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"

printf 'hwut {\n}\n' > hwut-root.conf
mkdir tree
printf 'hwut {\n}\n' > tree/hwut-root.conf

propose() {               #  <argument>...: status and both streams
    echo "\$ hwut.sanitize.propose $*"
    $PROPOSE "$@" > out.txt 2> err.txt
    echo "STATUS: $?"
    echo "STDOUT {"; sed 's|'"$WORK"'|<work>|g; s/pid [0-9]\+/pid <n>/' \
                    < out.txt | sed 's/^/    /'; echo "}"
    echo "STDERR {"; sed 's|'"$WORK"'|<work>|g; s/pid [0-9]\+/pid <n>/; s/^/    /' \
                    < err.txt; echo "}"
}

python_do() {             #  <python>: run with the tree's bookkeeper at hand
    python3 -c "import sys; sys.path.insert(0, '$ROOT'); $1"
}

live_lock() {             #  <dir>: a lock held by THIS very shell
    mkdir -p "$1/TMP/lock"
    python_do "
import json, os
from vut.auxiliary.directory_mutex import _process_start_time
json.dump({'pid': os.getppid(),
           'started': _process_start_time(os.getppid()),
           'acquired': 1.0},
          open('$1/TMP/lock/holder.json', 'w'))"
}

app() {                   #  <dir> [<hwut.conf body>]: one application
    mkdir -p "tree/$1/TEST/GOOD"
    printf 'hwut {\n    on_entry = "true"\n    on_exit  = "true"\n%b}\n' "$2" \
        > "tree/$1/TEST/hwut.conf"
    printf '#! /bin/bash\n# @hwut { title = "A" }\necho "line"\necho "<hwut-end>"\n' \
        > "tree/$1/TEST/test-app.sh"
    chmod +x "tree/$1/TEST/test-app.sh"
    printf 'line\n<hwut-end>\n' > "tree/$1/TEST/GOOD/test-app.sh.txt"
}

booked() {                #  <dir>: the application's nominal entered in the book
    $COMMAND book "tree/$1/TEST/test-app.sh" > /dev/null 2>&1
}

CONSTRAINED='#! /bin/bash
# @hwut {
#     title = "C"
#     choices {
#         a { }
#         b { tolerance { constraints = ["load <= 100"] } }
#         c { tolerance { constraints = ["twice == 2 * once"] } }
#     }
# }
echo "x"
echo "<hwut-end>"
'

constrained() {           #  <dir>: 'test-c.sh' whose b and c break their law
    printf '%s' "$CONSTRAINED" > "tree/$1/TEST/test-c.sh"
    chmod +x "tree/$1/TEST/test-c.sh"
    printf 'x\n<hwut-end>\n'             > "tree/$1/TEST/GOOD/test-c.sh--a.txt"
    printf 'x ((load: 150))\n<hwut-end>\n' > "tree/$1/TEST/GOOD/test-c.sh--b.txt"
    printf 'x ((once: 3))\n<hwut-end>\n'   > "tree/$1/TEST/GOOD/test-c.sh--c.txt"
    for choice in a b c; do
        $COMMAND book "tree/$1/TEST/test-c.sh" $choice > /dev/null 2>&1
    done
}

# ---------------------------------------------------------------------------
case "$1" in

catalogue)
    #  FIRST THE RECORDS: applications, nominals, books. Booking takes
    #  the directory's lock, which leaves 'TMP/' behind; it is swept
    #  before the transient scenarios are placed.
    for d in s01-session s02-lock-dead s03-lock-nameless s04-out \
             s05-transient s06-orphan-test s07-orphan-choice \
             s10-constraint n01-out-live n02-choiceless n04-wish \
             n05-register c01-aspirant c03-live-lock c04-remarked \
             s13-orphan-moved c06-home s14-orphan-readded c07-readded \
             s15-orphan-twice c08-one c09-two; do
        app $d; booked $d
    done

    printf 'stale\n<hwut-end>\n' > tree/s06-orphan-test/TEST/GOOD/test-gone.sh.txt
    printf 'stale\n<hwut-end>\n' \
        > tree/s07-orphan-choice/TEST/GOOD/test-app.sh--nochoice.txt

    far() {               #  <dir> <name>: the application, standing there
        printf '#! /bin/bash\n# @hwut { title = "F" }\necho "far"\necho "<hwut-end>"\n' \
            > "tree/$1/TEST/$2"
        chmod +x "tree/$1/TEST/$2"
    }
    printf 'far\n<hwut-end>\n' > tree/s13-orphan-moved/TEST/GOOD/test-far.sh.txt
    far c06-home test-far.sh

    printf 'far\n<hwut-end>\n' > tree/s14-orphan-readded/TEST/GOOD/test-re.sh.txt
    far c07-readded test-re.sh
    printf 'far\n<hwut-end>\n' > tree/c07-readded/TEST/GOOD/test-re.sh.txt
    $COMMAND book tree/c07-readded/TEST/test-re.sh > /dev/null 2>&1

    printf 'far\n<hwut-end>\n' > tree/s15-orphan-twice/TEST/GOOD/test-two.sh.txt
    far c08-one test-two.sh
    far c09-two test-two.sh

    app s08-book-behind

    app s09-book-stale
    rm tree/s09-book-stale/TEST/GOOD/test-app.sh.txt
    python_do "
from vut.engine.bookkeeper.api import Bookkeeper
Bookkeeper('tree/s09-book-stale/TEST').run_id_of('test-app.sh', allocate_f=True)"
    printf 'line\n<hwut-end>\n' > tree/s09-book-stale/TEST/GOOD/test-app.sh.txt

    constrained s10-constraint

    app s12-target '    target { clean = "./clean.sh" }\n'
    booked s12-target
    printf '#! /bin/bash\necho "cleaned"\n' > tree/s12-target/TEST/clean.sh
    chmod +x tree/s12-target/TEST/clean.sh

    printf '#! /bin/bash\n# @hwut { title = "B" choices = ["x"] }\necho "b"\necho "<hwut-end>"\n' \
        > tree/n02-choiceless/TEST/test-b.sh
    chmod +x tree/n02-choiceless/TEST/test-b.sh
    printf 'b\n<hwut-end>\n' > tree/n02-choiceless/TEST/GOOD/test-b.sh--x.txt
    $COMMAND book tree/n02-choiceless/TEST/test-b.sh x > /dev/null 2>&1
    printf 'b\n<hwut-end>\n' > tree/n02-choiceless/TEST/GOOD/test-b.sh.txt

    #  A LIST THAT MEETS '}' ENDS WITH A FAULT (hwut_hocon).
    app n03-fault '    ignore = [\n'

    #  IDS STAND IN THE ROWS, AND NO '# vut-register' BLOCK BOUNDS THEM.
    sed -i '/^# vut-register/d' tree/n05-register/TEST/GOOD/book.csv

    printf '#! /bin/bash\n# @hwut { title = "N" }\necho "n"\necho "<hwut-end>"\n' \
        > tree/c01-aspirant/TEST/test-new.sh
    chmod +x tree/c01-aspirant/TEST/test-new.sh
    python_do "
from vut.engine.bookkeeper.api import Bookkeeper
Bookkeeper('tree/c01-aspirant/TEST').run_id_of('test-new.sh', allocate_f=True)"

    app c02-run-booked
    ( cd tree/c02-run-booked/TEST && python3 -m vut.services.run test-app.sh \
          --silent > /dev/null 2>&1 )

    constrained c04-remarked
    $COMMAND remark tree/c04-remarked/TEST/test-c.sh b > /dev/null 2>&1
    $COMMAND remark tree/c04-remarked/TEST/test-c.sh c > /dev/null 2>&1

    app c05-unreachable '    ignore = ["test-hidden.sh"]\n'
    booked c05-unreachable
    printf '#! /bin/bash\necho "hi"\n' > tree/c05-unreachable/TEST/test-hidden.sh
    chmod +x tree/c05-unreachable/TEST/test-hidden.sh
    printf 'hi\n<hwut-end>\n' > tree/c05-unreachable/TEST/GOOD/test-hidden.sh.txt

    #  THEN THE TRANSIENT SCENARIOS, on a swept tree.
    find tree -depth \( -name TMP -o -name OUT \) -type d -exec rm -rf {} +

    mkdir -p tree/s01-session/TEST/TMP/session
    touch tree/s01-session/TEST/TMP/session/a.out
    mkdir -p tree/s02-lock-dead/TEST/TMP/lock
    printf '{"pid": 999999, "started": 1.0, "acquired": 1.0}\n' \
        > tree/s02-lock-dead/TEST/TMP/lock/holder.json
    mkdir -p tree/s03-lock-nameless/TEST/TMP/lock
    mkdir -p tree/s04-out/TEST/OUT
    touch tree/s04-out/TEST/OUT/a.txt
    mkdir -p tree/s05-transient/TEST/TMP/store tree/s05-transient/TEST/OUT
    echo x > tree/s05-transient/TEST/TMP/store/test-app.sh.stdout
    mkdir -p tree/n01-out-live/TEST/OUT
    touch tree/n01-out-live/TEST/OUT/a.txt
    live_lock tree/n01-out-live/TEST
    live_lock tree/c03-live-lock/TEST

    echo "=== EVERY ASPECT BUT '--transient', AND THE PROJECT'S VERB"
    propose --directory=tree --session --lock --out --orphans --books \
            --constraints --target clean
    echo "=== '--transient': THE TWO ROOTS WHOLE"
    propose --directory=tree --transient
    echo "=== A WISH THAT HIDES CASES"
    propose --directory=tree/n04-wish --orphans --glob "test-none*"
    echo "=== THE THREE ORPHANS APPLIED: one moved, two forgotten past their notes"
    $PROPOSE --directory=tree --orphans 2> /dev/null \
        | grep -E 's13-orphan-moved|s14-orphan-readded|s15-orphan-twice' > moved.txt
    sed 's/^/    /' moved.txt
    $APPLY moved.txt 2>&1 | grep -E '^ *(move|forget) |Done|REFUSED' \
        | sed 's/ \.\+ / /; s/^ */    /'
    here() { [ -f "tree/$1" ] && echo yes || echo NO; }
    echo "    s13: the nominal left          : $([ -f tree/s13-orphan-moved/TEST/GOOD/test-far.sh.txt ] && echo NO || echo yes)"
    echo "    s13: and stands in c06-home    : $(here c06-home/TEST/GOOD/test-far.sh.txt)"
    echo "    s14: the old nominal is gone   : $([ -f tree/s14-orphan-readded/TEST/GOOD/test-re.sh.txt ] && echo NO || echo yes)"
    echo "    s14: c07-readded keeps its own : $(here c07-readded/TEST/GOOD/test-re.sh.txt)"
    echo "    s15: the old nominal is gone   : $([ -f tree/s15-orphan-twice/TEST/GOOD/test-two.sh.txt ] && echo NO || echo yes)"
    echo "--- asked again"
    $PROPOSE --directory=tree --orphans 2> /dev/null \
        | grep -cE 's13-orphan-moved|s14-orphan-readded|s15-orphan-twice' | sed 's/^/    lines: /'
    ;;

*)
    echo "no such choice: $1"
    exit 1 ;;
esac

echo "<hwut-end>"
