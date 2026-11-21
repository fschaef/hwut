#! /bin/bash
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title    = "The book's D-93, D-92 and the constraint module (ruled 2026-11-18)"
#     features = ["book-defects-round-4"]
#     choices  = ["unit-hex", "unit-word", "module-names", "module-replaces",
#                 "module-inherited", "module-faults", "maths-units",
#                 "maths-refused"]
# }
#
# ---------------------------------------------------------------------------
#
# The development requirements of 2026-11-18 (D-93) and the constraint
# module asked for with them -- services E-233, compare C-24.
#
# unit-hex        D-93: '0x14', '0X14', '0o17', '0b101', '-0x14' bind the
#                 integer a law reads; a unit may follow ('0x14 ms').
#                 MEASURED before (67bbf0f): the numeral took '0', the
#                 unit word 'x14', and "0 x14" was bound -- 'register % 4
#                 == 0' broken by a value the output never printed.
# unit-word       D-93: a number with a word pint does not know is refused
#                 where the binding is read, naming the word, the value
#                 as the line wrote it; no law over it is judged a second
#                 time. MEASURED before: "12 socks" bound as text, 'room
#                 == 12 ft' broken with no reason.
# module-names    'constraint_module = "laws.py"': every public name of the
#                 file enters flat -- a function called bare, a constant
#                 named; '_' names and imported modules do not; '__all__'
#                 where stated. A binding named like one of its constants
#                 is refused "(from laws.py)". The file is no wallflower.
# module-replaces A name of the file that is a fixed name replaces it, said
#                 once on stderr: the file's 'hypot' (the streets, 42.19 m)
#                 judges, not the fixed one (the flight, 32.38 m).
# module-inherited stated in 'hwut.conf''s 'app_defaults', the laws in the
#                 page's header: the run judges with it; a law calling a
#                 name neither holds is refused, 'spec [FAIL]', at the
#                 place of the list of laws.
# maths-units     D-92: the maths keep the unit -- 'hypot', 'sqrt', 'pow',
#                 'floor', 'ceil', 'trunc', 'fabs', 'fmod', 'copysign' --
#                 or compare in one ('isclose', 'atan2'), or take an angle
#                 ('sin(30 deg)', 'degrees'); 'abs', 'min', 'max', 'round'
#                 kept it already and still do. MEASURED before (67bbf0f):
#                 'hypot(east, north) <= radius' over metres refused as "a
#                 number without unit against a quantity -- write its
#                 unit"; so 'sqrt', 'pow', 'floor', 'ceil', 'fabs', 'fmod',
#                 'copysign', 'isclose', 'atan2'; 'trunc' a TypeError with
#                 no reason. A law the values break is broken, no reason
#                 attached (32.38 m against 32 m).
# maths-refused   D-92: a function given a dimension it cannot take is
#                 refused naming it, what it takes and the argument as the
#                 law writes it: "sin needs an angle or a plain number --
#                 'east' is [length]". MEASURED before: "write its unit".
# module-faults   a file missing, not '.py', raising on import, its
#                 '__all__' naming what it lacks: each a fault before
#                 any line is read, nothing played -- at the place it is
#                 written, a 'hwut.conf' named where it stands there.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
export PYTHONPATH="$ROOT"
BIN="$ROOT/hwut/bin"
export PATH="$BIN:$PATH"
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "The book's D-93, D-92 and the constraint module;"
        echo "CHOICES: unit-hex, unit-word, module-names, module-replaces, module-inherited, module-faults, maths-units, maths-refused;"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/TEST"
cd "$WORK"
mkdir -p HWUT_ROOT
printf 'hwut {\n    language-setup { bash { extensions = [".sh"] interpreter = "bash" } }\n}\n' \
       > HWUT_ROOT/setup.conf
cd TEST
shown() {
    sed -E "s|$WORK|\$WORK|g; s/[0-9]+\.[0-9]+ \[sec\]/<t> [sec]/g;
            s/, [0-9:]+$/, <t>/; s/ +\|\|[0-9]+$//;
            s/(by hwut.play), [0-9-]+ [0-9:]+/\1, <t>/;
            s/only calls to .* or string/only calls to <the namespace> or string/"
    #  The namespace's list grows with it; whether the file's names are
    #  in it is the 'fmean' and 'in_band' lines' to show.
}
page() {                # <file> <header> <body lines...>
    local file=$1 header=$2; shift 2
    { echo '#! /bin/bash'; echo "# @hwut { $header }"; printf '%s\n' "$@"
      echo 'echo "<hwut-end>"'; } > $file
    chmod +x $file
}
law() {                 # <tolerance body> <bindings printed>: what accept says
    page test-law.sh "tolerance { $1 }" "echo \"v $2\""
    rm -rf GOOD OUT
    printf -- '-- %s  over  %s\n' "$1" "$2"
    "$BIN/hwut.play" test-law.sh --plain 2>&1 | grep -E "^(NOTE|FAULT)" | shown
    "$BIN/hwut.accept" --whole test-law.sh 2>&1 \
        | grep -E "^(ACCEPTED|REFUSED|    (constraint|binding)|FAULT)" | shown
}
laws_py() {
    cat > laws.py <<'EOF'
from statistics import fmean
import math
LIMIT = 5
def in_band(x, low, high):
    return low <= x <= high
def _helper():
    return 0
EOF
}

case "$1" in
    unit-hex)
        law 'constraints = ["register % 4 == 0"]' '((register: 0x14))'
        law 'constraints = ["register == 20"]'    '((register: 0X14))'
        law 'constraints = ["register % 4 == 0"]' '((register: 0x15))'
        law 'constraints = ["x == 15 and y == 5"]' '((x: 0o17)) ((y: 0b101))'
        law 'constraints = ["x == -20"]'          '((x: -0x14))'
        law 'constraints = ["t < 1 s"]'           '((t: 0x14 ms))' ;;
    unit-word)
        law 'constraints = ["room == 12 ft"]'     '((room: 12 socks))'
        law 'constraints = ["room == 12 ft"]'     '((room: 12 ft))'
        law 'constraints = ["a < b"]'             '((a: 3 socks)) ((b: 4))'
        law 'constraints = ["x > 0"]'             '((x: 0xg1)) ((y: 12  feet_of_clay))' ;;
    module-names)
        laws_py
        law 'constraint_module = "laws.py" constraints = ["in_band(level, 1 V, 5 V)"]' '((level: 3 V))'
        law 'constraint_module = "laws.py" constraints = ["in_band(level, 1 V, 5 V)"]' '((level: 7 V))'
        law 'constraint_module = "laws.py" constraints = ["fmean((a, b)) < LIMIT"]' '((a: 3)) ((b: 4))'
        law 'constraint_module = "laws.py" constraints = ["a < 1"]' '((LIMIT: 3))'
        law 'constraint_module = "laws.py" constraints = ["_helper(a) < 1"]' '((a: 3))'
        law 'constraint_module = "laws.py" constraints = ["math(a) < 1"]' '((a: 3))'
        printf '__all__ = ["in_band"]\nLIMIT = 5\ndef in_band(x, low, high): return low <= x <= high\n' > laws.py
        law 'constraint_module = "laws.py" constraints = ["a < LIMIT"]' '((a: 3))'
        laws_py
        law 'constraint_module = "laws.py" constraints = ["in_band(level, 1, 5)"]' '((level: 3))'
        echo "-- the run, its wallflowers"
        "$BIN/hwut.run" --plain 2>&1 | grep -E "^(NOTE|END|RESULTS)" | shown ;;
    module-replaces)
        #  The file's 'hypot' walks the streets: 30 m + 40 ft = 42.19 m;
        #  the fixed one flies, 32.38 m. '> 40 m' tells which judged.
        printf 'def hypot(*q):\n    return sum(abs(v) for v in q[1:]) + abs(q[0])\n' > laws.py
        law 'constraints = ["hypot(east, north) > 40 m"]' '((east: 30 m)) ((north: 40 ft))'
        law 'constraint_module = "laws.py" constraints = ["hypot(east, north) > 40 m"]' '((east: 30 m)) ((north: 40 ft))'
        law 'constraint_module = "laws.py" constraints = ["hypot(east, north) > 50 m"]' '((east: 30 m)) ((north: 40 ft))' ;;
    module-inherited)
        laws_py
        printf 'hwut {\n    app_defaults { tolerance { constraint_module = "laws.py" } }\n}\n' > hwut.conf
        page test-law.sh 'tolerance { constraints = ["in_band(level, 1 V, 5 V)"] }' \
             'echo "v ((level: ${LEVEL:-3} V))"'
        "$BIN/hwut.play" test-law.sh --plain > /dev/null 2>&1
        "$BIN/hwut.accept" --whole test-law.sh 2>&1 | grep -E "^ACCEPTED" | shown
        echo "-- level 3 V"
        "$BIN/hwut.run" --plain 2>&1 | grep -E "^(NOTE|END|RESULTS)" | shown
        echo "-- level 9 V"
        LEVEL=9 "$BIN/hwut.run" --plain 2>&1 | grep -E "^(NOTE|END|RESULTS)" | shown
        LEVEL=9 "$BIN/hwut.diff" test-law.sh --plain 2>&1 | grep -E "BROKEN" | shown
        echo "-- a name neither holds"
        page test-law.sh 'tolerance { constraints = ["in_bnd(level, 1 V, 5 V)"] }' \
             'echo "v ((level: 3 V))"'
        "$BIN/hwut.run" --plain 2>&1 | grep -E "^(END|RESULTS)|in_bnd" | shown ;;
    maths-units)
        law 'constraints = ["hypot(east, north) <= radius"]' '((east: 30 m)) ((north: 40 m)) ((radius: 60 m))'
        law 'constraints = ["hypot(east, north) <= 33 m"]'   '((east: 30 m)) ((north: 40 ft))'
        law 'constraints = ["hypot(east, north) <= 32 m"]'   '((east: 30 m)) ((north: 40 ft))'
        law 'constraints = ["sqrt(area) < 20 m"]'            '((area: 144 m**2))'
        law 'constraints = ["pow(side, 2) == area"]'         '((side: 3 m)) ((area: 9 m**2))'
        law 'constraints = ["floor(t) == 3 s and ceil(t) == 4 s and trunc(t) == 3 s"]' '((t: 3.7 s))'
        law 'constraints = ["fabs(u) == 3 V and copysign(w, u) == -2 V"]' '((u: -3 V)) ((w: 2 V))'
        law 'constraints = ["fmod(a, b) == 1 m"]'            '((a: 7 m)) ((b: 300 cm))'
        law 'constraints = ["isclose(a, b)"]'                '((a: 1 m)) ((b: 100 cm))'
        law 'constraints = ["atan2(north, east) > 0.9"]'     '((east: 30 m)) ((north: 40 m))'
        law 'constraints = ["sin(phi) > 0.49 and degrees(phi) == 30"]' '((phi: 30 deg))'
        law 'constraints = ["abs(u) == 3 V and round(w) == 2 V and min(a, b) == b and max(a, b) == a"]' '((u: -3 V)) ((w: 2.4 V)) ((a: 30 m)) ((b: 40 ft))'
        law 'constraints = ["hypot(east, north) < 5 and sin(x) < 1"]' '((east: 3)) ((north: 3)) ((x: 0.5))' ;;
    maths-refused)
        law 'constraints = ["sin(east) < 1"]'                '((east: 30 m))'
        law 'constraints = ["exp(t) > 1"]'                   '((t: 2 s))'
        law 'constraints = ["atan2(north, dt) > 0"]'         '((north: 3 m)) ((dt: 2 s))'
        law 'constraints = ["hypot(east, 3) < 5 m"]'         '((east: 3 m))'
        law 'constraints = ["asin(phi) < 1"]'                '((phi: 30 deg))'
        law 'constraints = ["pow(x, n) < 1 m"]'              '((x: 3 m)) ((n: 2 s))'
        law 'constraints = ["gcd(a, 2) == 2"]'               '((a: 4 m))' ;;
    module-faults)
        law 'constraint_module = "missing.py" constraints = ["a < 1"]' '((a: 3))'
        law 'constraint_module = "laws.txt" constraints = ["a < 1"]' '((a: 3))'
        printf 'raise RuntimeError("boom")\n' > bad.py
        law 'constraint_module = "bad.py" constraints = ["a < 1"]' '((a: 3))'
        printf '__all__ = ["f", "g"]\ndef f(x):\n    return x\n' > all.py
        law 'constraint_module = "all.py" constraints = ["f(a) < 1"]' '((a: 0))'
        printf 'def f(x:\n' > broken.py
        law 'constraint_module = "broken.py" constraints = ["f(a) < 1"]' '((a: 0))'
        echo "-- stated in hwut.conf: the conf is named"
        printf 'hwut {\n    app_defaults {\n        tolerance { constraint_module = "gone.py" }\n    }\n}\n' > hwut.conf
        law 'constraints = ["a < 1"]' '((a: 0))' ;;
esac
echo "<hwut-end>"
