#! /bin/bash
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title    = "a test links a feature of another directory by internal id"
#     features = ["cross-directory-link"]
#     choices  = ["link", "external", "unresolved", "repoint", "move"]
# }
#
# ---------------------------------------------------------------------------
#
# THE BOOK'S D-8 (REQUIREMENT-cross-directory-links-2026-10-16): a link in
# 'features = [...]' is a name of the test's own TEST directory, or an
# INTERNAL ID '<directory id>:<name>' of any directory. A scratch tree:
# 'physics' defines bounce, stop, materials, move; 'world' defines terrain;
# the top TEST directory defines nothing and links 'physics' by id.
#
# link        A-1, A-2: '-l f/physics.bounce' lists the top's run beside
#             physics' own; the report lists it under the leaf; the matrix
#             names the foreign leaf by its external id.
# external    A-3: 'physics.bounce' is an external id, no link: OUTSIDE,
#             with the internal id to write.
# unresolved  A-4, A-9: an id whose name its directory does not define, a
#             retired one: OUTSIDE, by why; the verdicts unchanged.
# repoint     A-5: 'stop' renamed 'halt' by hand; register, propose, apply:
#             the repoint rewrites the top's link and names the file.
# move        A-6, A-7: 'test-roll.sh' moved to 'world': 'materials' is
#             carried, and the id link of 'world/TEST/test-terrain.sh'
#             follows; 'bounce', still linked in 'physics', is not copied --
#             the moved test links it by id.
#
# MEASURED 2026-10-19 before: an id link was 'names a feature its TEST
# directory does not define', and 'hwut.move' copied 'bounce'.
#
# THE IDS ARE GENERATED: shown as '<physics>', '<world>'.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
export PYTHONPATH="$ROOT"
BIN="$ROOT/hwut/bin"
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "a test links a feature of another directory by internal id;"
        echo "CHOICES: link, external, unresolved, repoint, move;"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"
mkdir -p TEST physics/TEST world/TEST

face() { "$BIN/$@"; }
shown() {               # stdin -> stdout: no generated id, no scratch path
    sed "s|$WORK|\$WORK|g; s/$PH/<physics>/g; s/$WD/<world>/g"
}
page() {                # <path> <title> <choices line>
    printf '#! /bin/bash\n# @hwut {\n#     title = "%s"\n#     choices { %s }\n# }\necho "$1"; echo "<hwut-end>"\n' \
           "$2" "$3" > "$1"
    chmod +x "$1"
}

printf 'hwut {\n    language-setup { bash { extensions = [".sh"] interpreter = "bash" } }\n}\n' \
       > hwut-root.conf
cat > physics/TEST/hwut-features.conf <<'E'
features { childs { bounce { title = "bounces" }  stop { title = "stops" }  materials { title = "materials" }  move { title = "moves" } } }
E
cat > world/TEST/hwut-features.conf <<'E'
features { childs { terrain { title = "terrain" } } }
E
page physics/TEST/test-roll.sh roll \
     'off-wall { features = ["bounce", "materials"] } over-ice { features = ["bounce"] }'
page physics/TEST/test-push.sh push \
     'a { features = ["move", "stop", "bounce"] } b { features = ["move"] }'
face hwut.features.init > /dev/null
PH=$(grep '= "physics"' hwut-root-features.conf | cut -d'"' -f2)
WD=$(grep '= "world"'   hwut-root-features.conf | cut -d'"' -f2)
page world/TEST/test-terrain.sh terrain \
     "seed-4 { features = [\"terrain\", \"$PH:materials\"] }"
page TEST/test-shot.sh shot \
     "left { features = [\"$PH:bounce\"] } right { features = [\"$PH:stop\"] }"
case "$1" in
    external)   sed -i "s/\"$PH:bounce\"/\"physics.bounce\"/" TEST/test-shot.sh ;;
    unresolved) sed -i "s/\"$PH:bounce\"/\"$PH:gone\"/" TEST/test-shot.sh ;;
esac
for d in TEST physics/TEST world/TEST; do
    (cd $d && face hwut.play --all --plain > /dev/null 2>&1; face hwut.accept --whole > /dev/null 2>&1)
done
face hwut.run > /dev/null 2>&1

case "$1" in
    link)
        echo "== hwut.report.list -l f/physics.bounce"
        face hwut.report.list -l f/physics.bounce 2>&1 | shown
        echo "== hwut.report.features"
        face hwut.report.features 2>&1 | shown
        echo "== hwut.report.features --matrix"
        face hwut.report.features --matrix 2>&1 | shown ;;
    external)
        face hwut.report.features 2>&1 | sed -n '/OUTSIDE/,$p' | shown ;;
    unresolved)
        face hwut.features.retire physics.stop 2>&1 | head -1 | shown
        face hwut.report.features 2>&1 | sed -n '/OUTSIDE/,$p' | shown
        face hwut.run 2>&1 | grep -c "\[OK\]" | sed 's/^/runs ok: /' ;;
    repoint)
        sed -i 's/stop {/halt {/' physics/TEST/hwut-features.conf
        sed -i 's/"stop"/"halt"/' physics/TEST/test-push.sh
        face hwut.features.register > /dev/null 2>&1
        face hwut.sanitize.propose --relations -o heal.txt > /dev/null 2>&1
        face hwut.sanitize.apply heal.txt 2>&1 | grep -v "^=\|^-\|^EXECUTION" | shown
        grep "features" TEST/test-shot.sh | shown
        echo "== hwut.report.list -l f/physics.stop"
        face hwut.report.list -l f/physics.stop 2>&1 | shown ;;
    move)
        mv physics/TEST/test-roll.sh world/TEST/test-roll.sh
        face hwut.move physics/TEST/test-roll.sh world/TEST --dont-ask 2>&1 \
            | grep "feature\|binds\|link" | shown
        grep "features" world/TEST/test-roll.sh world/TEST/test-terrain.sh | shown
        cat world/TEST/hwut-features.conf
        face hwut.run 2>&1 | tail -1
        face hwut.features.register 2>&1 | grep -v "aggregate\|HINTS"
        echo "== hwut.report.list -l f/physics.bounce"
        face hwut.report.list -l f/physics.bounce 2>&1 | shown ;;
esac
echo "<hwut-end>"
