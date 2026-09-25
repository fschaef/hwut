#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title      = "adm/import_graph.py: who depends on whom, and the layering"
#     choices {
#         depth { }  formats { }  layering { }  refused { }  shared { }
#         unreadable { }
#         vut { tolerance { eq_pattern = ["STATUS: [0-9]",
#                                         "[0-9]+ module\\(s\\): .*",
#                                         "(--> .*|imports nothing of this tree)",
#                                         "LAYERING( VIOLATED --|:) .*"] } }
#     }
#     tolerance { eq_pattern = ["STATUS: [0-9]"] }
# }
#
# ---------------------------------------------------------------------------
#
# 'adm/import_graph.py' -- the import graph at a stated DEPTH, and the
# LAYERING check that makes the architecture executable.
#
# depth       THE DEPTH IS THE ZOOM: 1 names outer directories, 2 the
#             inner ones, 0 the modules themselves. The same tree,
#             three pictures.
# formats     'tree' for reading, 'edges' for grep and for diff, 'svg'
#             for a picture drawn HERE -- no graphviz, no browser --
#             'dot' for graphviz, 'mermaid' for a browser with nothing
#             installed. A MUTUAL PAIR is drawn with a head at both
#             ends, so a cycle shows itself.
# layering    A DECLARATION SAYS WHAT MAY HAPPEN; an edge no rule
#             permits is a VIOLATION, named by both ends. The check
#             passes on an obedient tree and BITES on a disobedient
#             one -- both shown, because a check that never fails
#             proves nothing.
# shared      WHICH NAMES DO SEVERAL COMPONENTS IMPORT? A name three
#             components reach for is no part of whichever one holds
#             it -- it is CONTRACT MATERIAL, and where it lives inside
#             one of its own readers it holds a cycle shut.
# unreadable  a module that cannot be parsed is REPORTED, never
#             silently dropped: a graph missing an edge it could not
#             read is a graph that lies.
# refused     by name: an unknown format, an unknown option, a
#             declaration that is not one.
# vut         THE REAL TREE: the tool reads all of it, draws the outer
#             picture, and JUDGES it against the declaration. What the
#             tree holds -- its modules, its edges, whether its layering
#             holds -- is no behaviour of the tool, and is tolerated:
#             the choice's own eq_patterns take any module list, any
#             edges, and either judgement. What is not tolerated: a
#             component missing or added, a refusal, a crash.
#
# THE FIXTURES ARE TINY TREES built in a work directory, so what this
# suite proves does not depend on the shape of the tree it lives in --
# except for the 'vut' choice, whose tolerances say which parts of the
# page are the tree's.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)      # the tree root: adm/TEST is two below
TOOL="$ROOT/adm/import_graph.py"
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "adm/import_graph.py: who depends on whom, and the layering;"
        echo "CHOICES: depth, formats, layering, shared, unreadable, refused, vut, door;"
        echo "HAPPY: STATUS: [0-9];"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"

face() {                # <args...> -- status and stdout
    python3 "$TOOL" "$@" > out.txt 2> err.txt
    echo "STATUS: $?"
    echo "STDOUT {"; sed "s|$WORK|<work>|g" < out.txt \
                     | sed 's/^/    /'; echo "}"
    if [ -s err.txt ]; then
        echo "STDERR {"; sed "s|$WORK|<work>|g" < err.txt \
                         | sed 's/^/    /'; echo "}"
    fi
}

fixture() {             # a tiny tree: faces -> engine -> base
    mkdir -p tree/faces tree/engine/plan tree/engine/store tree/base
    printf 'from tree.engine.plan.wish import Wish\nfrom tree.base.util import helper\n' \
        > tree/faces/run.py
    printf 'from tree.engine.store.book import Book\n' \
        > tree/faces/show.py
    printf 'from tree.engine.store.book import Book\nfrom tree.base.util import helper\n' \
        > tree/engine/plan/wish.py
    printf 'from tree.base.util import helper\n' \
        > tree/engine/store/book.py
    printf 'def helper(): pass\n' > tree/base/util.py
    for d in tree tree/faces tree/engine tree/engine/plan \
             tree/engine/store tree/base; do
        printf '' > "$d/__init__.py"
    done
}

# ---------------------------------------------------------------------------
case "$1" in

depth)
    fixture
    echo "--- depth 1: the outer directories"
    face tree --depth=1 --format=edges
    echo "--- depth 2: the inner ones"
    face tree --depth=2 --format=edges
    echo "--- depth 0: the modules themselves"
    face tree --depth=0 --format=edges
    echo "--- and the nested blocks a person reads"
    face tree --depth=2
    ;;

formats)
    fixture
    echo "--- dot"
    face tree --depth=1 --format=dot
    echo "--- mermaid"
    face tree --depth=1 --format=mermaid
    echo "--- svg: the shape of it, without the coordinates"
    #  THE NUMBERS ARE LAYOUT, not architecture: a GOOD holding pixel
    #  positions would move whenever a box grew a character. What is
    #  recorded is WHAT THE PICTURE CONTAINS.
    python3 "$TOOL" tree --depth=1 --format=svg > pic.svg 2>&1
    echo "STATUS: $?"
    echo "THE PICTURE {"
    echo "    elements:  $(grep -c '<rect' pic.svg) rect, \
$(grep -c '<path' pic.svg) path, $(grep -c '<text' pic.svg) text"
    echo "    boxes:     $(grep -o 'font-size="12"[^<]*>[^<]*' pic.svg \
| sed 's/.*>//' | sort | tr '\n' ' ')"
    echo "    mutual:    $(grep -c 'marker-start' pic.svg) pair(s)"
    echo "    editable:  $(grep -c 'inkscape:connection-start' pic.svg) \
connector(s) bound, $(grep -c 'connector-avoid' pic.svg) box(es) avoided"
    echo "    ids:       $(grep -o 'id=\"n_[a-z_]*\"' pic.svg | sort \
| tr '\n' ' ')"
    echo "}"
    ;;

shared)
    #  CONTRACT MATERIAL, measured.
    fixture
    printf 'from tree.base.util import helper, E_Kind\n' \
        > tree/faces/more.py
    printf 'from tree.base.util import E_Kind\n' \
        >> tree/engine/plan/wish.py
    printf 'from tree.base.util import E_Kind\n' \
        >> tree/engine/store/book.py
    echo "--- names three or more components import"
    face tree --depth=2 --shared=3
    echo "--- and two or more, which finds the rest"
    face tree --depth=2 --shared=2
    ;;

layering)
    fixture
    printf 'faces -> engine\nengine -> base\nfaces -> base\n' \
        > rules.txt
    echo "--- a tree that obeys its declaration"
    face tree --depth=1 --check=rules.txt
    echo "--- ONE edge the declaration does not permit"
    printf 'from tree.faces.show import thing\n' \
        >> tree/engine/store/book.py
    face tree --depth=1 --check=rules.txt
    echo "--- and a declaration permitting it makes the tree obedient"
    printf 'engine -> faces\n' >> rules.txt
    face tree --depth=1 --check=rules.txt
    echo "--- globs stand on either side"
    printf 'faces -> *\nengine -> *\n' > wide.txt
    face tree --depth=1 --check=wide.txt

    #  A SEAL IS ABOUT ONE COMPONENT, not a pair, and is judged at
    #  MODULE depth -- so it holds at a depth where the direction
    #  rules cannot see the component at all.
    echo "--- SEALED: a component that imports nothing of this tree"
    mkdir -p tree/base/contract
    printf '' > tree/base/contract/__init__.py
    printf 'E_Kind = 1\n' > tree/base/contract/enums.py
    printf 'faces -> *\nengine -> *\nbase -> *\nSEALED base/contract\n' \
        > sealed.txt
    face tree --depth=1 --check=sealed.txt
    echo "--- and one import out of it breaks the seal, at DEPTH 1,"
    echo "    where 'base/contract' is not even a component"
    printf 'from tree.engine.plan.wish import Wish\n' \
        >> tree/base/contract/enums.py
    face tree --depth=1 --check=sealed.txt

    #  A DOOR IS THE MIRROR OF A SEAL: a seal says NOTHING LEAVES, a
    #  door says NOTHING ENTERS BUT HERE. Judged at MODULE depth too,
    #  and a component's own modules are not callers.
    echo "--- DOOR: one module is a component's only entrance. Here"
    echo "    every caller already reaches PAST it, and each is named"
    printf 'from tree.engine.store.book import Book\n' \
        > tree/engine/plan/api.py
    printf 'faces -> *\nengine -> *\nbase -> *\nDOOR engine/plan/api\n' \
        > door.txt
    face tree --depth=1 --check=door.txt
    echo "--- every caller through the door instead, and the tree is"
    echo "    obedient -- while the component's OWN module still"
    echo "    reaches its parts freely: a door is for callers, and a"
    echo "    part is not a caller"
    printf 'from tree.engine.plan.api import Wish\n' > tree/faces/show.py
    printf 'from tree.engine.plan.api import Wish\n' > tree/faces/run.py
    printf 'E_Kind = 1\n' > tree/base/contract/enums.py
    printf 'from tree.engine.plan.wish import Wish\n' \
        >> tree/engine/plan/api.py
    face tree --depth=1 --check=door.txt
    ;;

unreadable)
    #  A GRAPH MISSING AN EDGE IT COULD NOT READ IS A GRAPH THAT LIES.
    fixture
    printf 'def broken(:\n' > tree/engine/plan/torn.py
    face tree --depth=1 --format=edges
    ;;

refused)
    fixture
    echo "--- a format that does not exist"
    face tree --format=sideways
    echo "--- an option the tool does not take"
    face tree --sideways
    echo "--- a declaration that is not one"
    printf 'faces and engine\n' > bad.txt
    face tree --check=bad.txt
    echo "--- a declaration that is not there"
    face tree --check=nowhere.txt
    ;;

vut)
    #  THE REAL TREE: the outer picture, and its own declaration.
    #  THE SUITES ARE EXCLUDED -- a test application imports whatever
    #  it tests, and is no part of the shape it examines.
    cd "$ROOT"
    python3 "$TOOL" . --depth=1 --exclude="*/TEST/*" \
        --exclude="*/test-*" --exclude="*/config.py" > "$WORK/o.txt" 2>&1
    echo "STATUS: $?"
    #  ONE LINE OF EDGES PER COMPONENT: their number is the tree's, so
    #  they stand on one line where one pattern takes them all.
    echo "THE OUTER PICTURE {"
    awk '/^ *--> / { sub(/^ *--> /, ""); e = e ? e ", " $0 : $0; next }
         e != ""   { print "    --> " e; e = "" }
                   { print }' < "$WORK/o.txt" | sed 's/^/    /'
    echo "}"
    python3 "$TOOL" . --depth=2 --check=adm/LAYERING.txt \
        --exclude="*/TEST/*" --exclude="*/test-*" \
        --exclude="*/config.py" > "$WORK/c.txt" 2>&1
    echo "STATUS: $?"
    #  THE JUDGEMENT LINE ALONE: what follows it lists what the tree
    #  holds (violations, seals, doors) -- the 'layering' choice shows
    #  that listing on fixtures. A refusal is its first line too, and
    #  no pattern takes it.
    echo "THE LAYERING {"; head -1 "$WORK/c.txt" | sed 's/^/    /'; echo "}"
    ;;

*)
    echo "no such choice: $1"
    exit 1 ;;
esac

#  THE CLOSING TOKEN, PRINTED BY THE SCRIPT ITSELF -- without it
#  'hwut.accept' refuses every candidate this suite ever produces.
echo "<hwut-end>"
