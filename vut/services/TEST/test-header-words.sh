#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title   = "A word in a test's header, through the face: what the validator admits, the run does."
#     choices = ["budget_spent", "build", "carrier", "climb",
#                "constraint", "constraint_refused", "cycle", "directory",
#                "execute", "namespace", "pattern_first", "printed",
#                "pype_fails", "region", "same", "session", "tolerance",
#                "values"]
# }
#
# ---------------------------------------------------------------------------
#
# ONE PAGE THROUGH THE FACE (audit r10, G-10) for words a header may
# state: the word written in a fixture's '@hwut { }', the launcher
# called, the outcome printed. Each was green by a page that exercised
# a function while the face took another road.
#
# constraint          'constraints = ["glob(name, \"build-*.log\")"]'
#                     (exploration R-66, G-3): 'hwut.run.play' reads the
#                     stream under it and 'hwut.accept' judges it --
#                     once holding, once broken.
# constraint_refused  a name the namespace does not hold: a FAULT with
#                     file, line and column, from 'hwut.run' and from
#                     'hwut.run.play' -- no traceback.
# execute             'execute' with '$file', '$filestem', '$choice'
#                     (exploration R-68, G-4): expanded in the call; a
#                     placed '$choice' is not appended again; an
#                     unplaced one is the last argument; the choice-less
#                     call drops the empty word.
# same                'same = true' (exploration R-45, bookkeeper B-30,
#                     G-2): 'hwut.accept' writes ONE nominal for the
#                     test, 'hwut.run' judges every choice by it,
#                     'hwut.report.details' finds it, a choice's removal
#                     leaves it, the test's rename takes it along and
#                     the test's removal takes it away.
#
# THE WORDS OF EXPLORATION'S RULINGS (audit D-9, 2026-10-08), each
# written in a fixture and read back by 'hwut.config.show', or run:
#
# namespace  lower case alone ('Title' refused); a user's name stands
#            only inside 'choices' (R-4); the root is the default and a
#            choice overwrites (R-5); no 'args' beside a choice (R-6);
#            'timeout' lives in 'caps' (R-22) and an unknown cap is a
#            fault with line and column (R-47); 'interactive' at the
#            root alone (R-46); a lacking title stands in (X-TITLE).
# carrier    one file, one carrier: a header AND an 'apps' entry is a
#            DIRECTORY error; the conf's root takes no test parameter
#            (R-7); 'app_defaults' reach every application and do not
#            overwrite, each value naming 'hwut.conf:<line>' (R-52,
#            R-53); only 'hwut.conf' is read (R-28).
# region     the block is found in '--', '//' and '/* */' comments and
#            deep in a file, with no table of comment syntaxes (R-9);
#            the sigil is '@hwut {' and a bare 'hwut {' in a source
#            file is not one (R-72).
# tolerance  the lexical tolerances stand in the one scope (R-77,
#            services E-42): the pattern, the analogy pair with its
#            five spellings of OFF and 'true' refused (R-12, R-24), the
#            constraints (R-25), the comment pair (R-64), whitespace
#            (R-65); the old root keys are unknown, not aliased (R-54).
# values     a string wears double quotes (R-49); numbers in five
#            radices with '_' between digits (R-62).
# build      'build' is the framework alone or the scope; 'app' is
#            struck (R-21, R-11).
# printed    what is printed is the specification language and reads
#            back (R-50); '--no-default' drops what nobody stated
#            (R-51); '--provenance' and '--gnu' name the place (R-67);
#            the caps' defaults are the supervisor's (R-78).
# directory  'on_entry' and 'on_exit' frame the run (R-31);
#            'collision' is an exclusion set (R-32); 'dependency' takes
#            targets (R-34), orders (R-33) and does not ask for success
#            (R-36): the dependant of a FAILING test runs, after it.
# cycle      a dependency cycle is the directory's failure, named; its
#            members and their dependant read 'no-dep [FAIL]'; the rest
#            of the directory runs (R-33, R-35). MEASURED BEFORE: an
#            AssertionError out of 'hwut.run' and 'hwut.plan' (G-18).
# climb      under 'TEST/TMP' the climb ends: no tree (R-76).
# pattern_first  an 'eq_pattern' claims its text BEFORE a number is a
#            number (compare C-14): 'v1.00' against 'v2.50' under the
#            pattern is equivalent; without it, a difference.
# budget_spent   'diff_display_parameters { search_budget }' (compare
#            C-16): a pair whose alignment spends the budget shows as
#            the line gone and the line come, WHOLE. MEASURED BEFORE
#            (G-20): an empty row, read as two blank, equal lines.
# pype_fails a pype that does not parse, and one that is not there, are
#            defects in the TEST and fail it by the word 'pype' (run
#            O-18); nothing is compared.
# session    'interactive = true' gives ONE SESSION node that SUPPORTS
#            its choices, each still a TEST node (plan P-5).
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
export PYTHONPATH="$ROOT"
RUN="python3 -m vut.services.run --jobs=1 --deterministic --no-colour --quiet"
PLAY="python3 -m vut.services.lib.run.play --plain"
SHOW="python3 -m vut.services.lib.config.show"
PLAN="python3 -m vut.services.plan"
ACCEPT="python3 -m vut.services.accept --whole --dont-ask"
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "A word in a test's header, through the face.;"
        echo "CHOICES: budget_spent, build, carrier, climb, constraint, constraint_refused, cycle, directory, execute, namespace, pattern_first, printed, pype_fails, region, same, session, tolerance, values;"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
mkdir "$WORK/TEST"
cd "$WORK/TEST"
printf 'hwut {\n    language-setup { bash { extensions = [".sh"] interpreter = "bash" } }\n}\n' \
       > ../hwut-root.conf

page() {                # <file> <header lines> <body line>
    printf '#! /bin/bash\n# @hwut {\n%b# }\n%s\necho "<hwut-end>"\n' "$2" "$3" > "$1"
    chmod +x "$1"
}
shown() { sed "s|$WORK|\$WORK|g"; }

#  ONE WORD, ONE LINE: the word in a header, and the first line of what
#  'hwut.config.show --no-default' says of it -- the fault, or the key.
word() {                # <header line> <grep pattern of the telling line>
    page test-w.sh "#     title = \"w\"\n#     $1\n" 'echo w'
    printf '%-52s => ' "$1"
    $SHOW test-w.sh --no-default < /dev/null 2>&1 | grep -m1 "$2" \
        | tr -s ' ' | sed 's/^ //' | cut -c1-70
}

case "$1" in
    constraint)
        HEAD='#     title = "glob"\n#     tolerance { constraints = ["glob(name, \\"build-*.log\\")"] }\n'
        #  A STRING BINDING IS QUOTED: '((name: "text"))'. Unquoted it
        #  reads as an analogy and binds nothing.
        page test-holds.sh  "$HEAD" "echo 'file ((name: \"build-7.log\"))'"
        page test-breaks.sh "$HEAD" "echo 'file ((name: \"debug-7.log\"))'"
        for t in test-holds.sh test-breaks.sh; do
            echo "== hwut.run.play $t"
            $PLAY $t 2>&1 | shown | sed -n '/^===== OUTPUT/,$p' | grep -v "^=*$"
            echo "STATUS: ${PIPESTATUS[0]}"
            echo "== hwut.accept --whole $t"
            python3 -m vut.services.accept --whole $t --dont-ask 2>&1 | shown \
                | grep "blessed\|REFUSED\|constraint\|Traceback"
        done ;;
    constraint_refused)
        page test-typo.sh \
             '#     title = "typo"\n#     tolerance { constraints = ["globb(name, \\"x\\")"] }\n' \
             'echo "file ((name: x))"'
        echo "== hwut.run"
        $RUN 2>&1 | shown | grep "ERROR\|Traceback" | cut -c1-74
        echo "STATUS: ${PIPESTATUS[0]}"
        echo "== hwut.run.play test-typo.sh"
        $PLAY test-typo.sh 2>&1 | shown | grep "FAULT\|Traceback\|nothing played" | cut -c1-74
        echo "STATUS: ${PIPESTATUS[0]}" ;;
    execute)
        page test-placed.sh \
             '#     title   = "placed"\n#     choices = ["one", "two"]\n#     execute = "bash $file --stem=$filestem --pick $choice tail"\n' \
             'echo "args: $*"'
        page test-unplaced.sh \
             '#     title   = "unplaced"\n#     choices = ["one"]\n#     execute = "bash $file head"\n' \
             'echo "args: $*"'
        page test-none.sh \
             '#     title   = "no choice"\n#     execute = "bash $file $choice end"\n' \
             'echo "args: $*"'
        for t in "test-placed.sh one" "test-placed.sh two" \
                 "test-unplaced.sh one" "test-none.sh"; do
            echo "== hwut.run.play $t --raw"
            $PLAY $t --raw 2>&1 | shown | grep "args:\|EMPTY\|FAULT" | head -1
        done ;;
    same)
        page test-same.sh \
             '#     title   = "same"\n#     choices = ["a", "b"]\n#     same    = true\n' \
             'echo "one behaviour"'
        good() { ls GOOD | grep -v book.csv | sed 's/^/    GOOD: /'; }
        echo "== hwut.accept --whole"
        python3 -m vut.services.accept --whole --dont-ask 2>&1 | grep "blessed\|REFUSED"
        good
        echo "== hwut.run"
        $RUN 2>&1 | grep "RESULTS" | sed 's/, [0-9.]* \[sec\].*//'
        echo "== hwut.report.details test-same.sh a"
        python3 -m vut.services.lib.report.details test-same.sh a 2>&1 \
            | grep "status report"
        echo "== hwut.remove test-same.sh b"
        python3 -m vut.services.remove test-same.sh b --dont-ask > /dev/null 2>&1
        good
        echo "== hwut.rename test-same.sh -to test-other.sh"
        python3 -m vut.services.rename test-same.sh -to test-other.sh \
                --dont-ask > /dev/null 2>&1
        good
        echo "== hwut.remove test-other.sh"
        python3 -m vut.services.remove test-other.sh --dont-ask > /dev/null 2>&1
        good
        echo "    (GOOD holds no nominal)" ;;
    namespace)
        P=":[0-9]*:\|timeout_sec\|interactive"
        word 'Title = "x"' "$P"
        word 'timeout = 3' "$P"
        word 'caps { timeout_sec = 3 }' "$P"
        word 'caps { timeout_sec = 3 nosuch_cap = 1 }' "$P"
        word 'interactive = true' "interactive\|:[0-9]*:"
        word 'choices { a { interactive = true } }' ":[0-9]*:"
        word 'choices { a { args = "x y" } }' ":[0-9]*:"
        echo "== a user's name stands inside 'choices', whatever it is"
        page test-n.sh '#     title = "n"\n#     caps { timeout_sec = 7 }\n#     choices { Upper { } title { caps { timeout_sec = 9 } } }\n' 'echo n'
        $SHOW test-n.sh --no-default 2>&1 | shown
        echo "== no title"
        page test-t.sh '#     choices = ["a"]\n' 'echo t'
        $SHOW test-t.sh --no-default 2>&1 | grep "title\|:[0-9]*:"
        echo "STATUS: ${PIPESTATUS[0]}" ;;
    carrier)
        page test-a.sh '#     title = "a"\n#     caps { timeout_sec = 3 }\n' 'echo a'
        page test-b.sh '#     title = "b"\n' 'echo b'
        printf 'echo bare\necho "<hwut-end>"\n' > bare.sh
        printf 'hwut {\n    app_defaults {\n        caps { timeout_sec = 11 memory_mb = 99 }\n    }\n    apps {\n        "bare.sh" { title = "conf only" }\n    }\n}\n' > hwut.conf
        echo "== app_defaults, and who said what"
        $SHOW --no-default --provenance 2>&1 | shown | grep -v "^$"
        echo "== a header AND an 'apps' entry"
        printf 'hwut {\n    apps {\n        "test-a.sh" { title = "also in conf" }\n    }\n}\n' > hwut.conf
        $SHOW --no-default 2>&1 | shown | grep "DIRECTORY\|VOCABULARY"
        echo "== a test parameter at the conf's root"
        printf 'hwut {\n    caps { timeout_sec = 5 }\n}\n' > hwut.conf
        $SHOW --no-default 2>&1 | shown | grep "DIRECTORY\|VOCABULARY" | cut -c1-76
        echo "== only 'hwut.conf' is read"
        printf 'hwut {\n    app_defaults { caps { timeout_sec = 11 } }\n}\n' > hwut.hocon
        rm hwut.conf
        $SHOW test-b.sh --no-default 2>&1 | grep -c "timeout_sec" ;;
    region)
        printf 'hwut {\n    language-setup { bash { extensions = [".sh", ".sql", ".c", ".txt"] interpreter = "bash" } }\n}\n' \
               > ../hwut-root.conf
        printf -- '-- @hwut {\n--     title = "two dashes"\n-- }\n'       > a.sql
        printf '// @hwut {\n//     title = "two slashes"\n// }\n'         > b.c
        printf '/* @hwut {\n *     title = "a star block"\n * } */\n'     > c.c
        printf 'one\ntwo\n    @hwut { title = "one line, deep" }\n'       > d.txt
        printf '#! /bin/bash\n# hwut {\n#     title = "no sigil"\n# }\n'  > e.sh
        for file in a.sql b.c c.c d.txt e.sh; do
            printf '%-6s => %s\n' $file \
                   "$($SHOW $file --no-default 2>&1 | grep -m1 'title\|:[0-9]*:' | tr -s ' ')"
        done ;;
    tolerance)
        P=":[0-9]*:\|eq_pattern\|analogy\|constraints\|comment\|whitespace"
        word 'happy = "a|b"' "$P"
        word 'eq-pattern = ["a|b"]' "$P"
        word 'analogy = ["<<", ">>"]' "$P"
        word 'whitespace_eqv = false' "$P"
        word 'tolerance { eq_pattern = ["a|b"] }' "$P"
        word 'tolerance { analogy = ["<<", ">>"] }' "$P"
        for off in '[]' 'false' 'no' 'null' ''; do
            word "tolerance { analogy = $off }" "$P"
        done
        word 'tolerance { analogy = true }' "$P"
        word 'tolerance { analogy = ["(("] }' "$P"
        word 'tolerance { constraints = ["x < y + 2"] }' "$P"
        word 'tolerance { constraints = false }' "$P"
        word 'tolerance { comment = ["%%", "%%"] }' "$P"
        word 'tolerance { comment = [] }' "$P"
        word 'tolerance { whitespace = false }' "$P"
        word 'tolerance { strip = false }' "$P" ;;
    values)
        P=":[0-9]*:\|timeout_sec\|numeric_ratio"
        word 'language = bash' "$P"
        for number in 16 0x10 0b1_0000 0o20 0rXVI 1_6 1__6 _16; do
            word "caps { timeout_sec = $number }" "$P"
        done
        word 'tolerance { numeric_ratio = - 0.12 }' "$P"
        word 'tolerance { numeric_ratio = + 0.12 }' "$P" ;;
    build)
        word 'build = "make"' "framework\|:[0-9]*:"
        word 'app = "x.exe"' "framework\|:[0-9]*:"
        page test-s.sh '#     title = "s"\n#     build { framework = "make" executable = "s.exe" }\n' 'echo s'
        $SHOW test-s.sh --no-default 2>&1 | shown ;;
    printed)
        page test-p.sh '#     title = "p"\n#     caps { timeout_sec = 7 }\n#     choices = ["a"]\n' 'echo p'
        echo "== hwut.config.show test-p.sh"
        $SHOW test-p.sh 2>&1 | sed -n '/caps {/,/}/p'
        for option in "--no-default" "--no-default --provenance" "--no-default --gnu"; do
            echo "== hwut.config.show test-p.sh $option"
            $SHOW test-p.sh $option 2>&1 | shown
        done
        echo "== what was printed, written as a header, reads back"
        { echo '#! /bin/bash'; echo '# @hwut {'
          $SHOW test-p.sh --no-default | sed '1d;$d' | sed 's/^/# /'
          echo '# }'; echo 'echo q'; } > test-q.sh
        $SHOW test-q.sh --no-default 2>&1 | sed '1d' > q.txt
        $SHOW test-p.sh --no-default 2>&1 | sed '1d' > p.txt
        diff <(sed 's/ *#.*//' p.txt) <(sed 's/ *#.*//' q.txt) > /dev/null \
            && echo "the same specification" || echo "DIFFERS" ;;
    directory)
        page test-a.sh '#     title = "a"\n' 'echo a; echo "a ran" >> log.txt'
        page test-b.sh '#     title = "b"\n#     choices = ["one", "two"]\n' \
             'echo "b $1"; echo "b $1 ran" >> log.txt'
        page test-c.sh '#     title = "c"\n' 'echo c; echo "c ran" >> log.txt'
        printf 'hwut {\n    on_entry = "echo ENTRY >> log.txt"\n    on_exit  = "echo EXIT >> log.txt"\n    collision = ["test-a.sh", "test-b.sh two"]\n    dependency {\n        "test-a.sh" = ["test-c.sh"]\n        "test-b.sh one" = ["test-a.sh", "test-b.sh two"]\n    }\n}\n' > hwut.conf
        $ACCEPT > /dev/null 2>&1 < /dev/null
        echo "== hwut.plan"
        $PLAN 2>&1 | shown
        echo "== hwut.plan test-b.sh one: what it requires enters, marked"
        $PLAN test-b.sh one 2>&1 | sed -n '/^NODES/,/^LINKS/p'
        echo "== hwut.run, 'test-a.sh' made to fail: order, not success"
        printf 'a DIFFERENT\n<hwut-end>\n' > GOOD/test-a.sh.txt
        rm -f log.txt
        $RUN 2>&1 | grep "RESULTS" | sed 's/, [0-9.]* \[sec\].*//'
        #  'test-b.sh two' and 'test-c.sh' are unordered between them:
        #  the log is read for what the rulings order, and no more.
        echo "first:  $(head -1 log.txt)"
        echo "last:   $(tail -1 log.txt)"
        order() { grep -n "^$1 ran" log.txt | cut -d: -f1; }
        [ "$(order c)" -lt "$(order a)" ] && echo "c before a"
        [ "$(order a)" -lt "$(order 'b one')" ] && echo "a before b one"
        [ "$(order 'b two')" -lt "$(order 'b one')" ] && echo "b two before b one"
        echo "== on_entry fails: nothing is dispatched"
        printf 'hwut {\n    on_entry = "false"\n    on_exit  = "echo EXIT >> log.txt"\n}\n' > hwut.conf
        rm -f log.txt
        python3 -m vut.services.run --jobs=1 --deterministic --no-colour --plain 2>&1 \
            | grep "FRAME\|START\|END"
        cat log.txt ;;
    cycle)
        for name in a b c d e; do
            page test-$name.sh "#     title = \"$name\"\n" "echo $name"
        done
        $ACCEPT > /dev/null 2>&1 < /dev/null
        printf 'hwut {\n    dependency {\n        "test-a.sh" = ["test-c.sh"]\n        "test-c.sh" = ["test-a.sh"]\n        "test-d.sh" = ["test-a.sh"]\n        "test-e.sh" = ["test-b.sh"]\n    }\n}\n' > hwut.conf
        echo "== hwut.plan"
        $PLAN 2>&1 | shown | grep -v "^Traceback\|^  File "
        echo "STATUS: ${PIPESTATUS[0]}"
        echo "== hwut.run"
        python3 -m vut.services.run --jobs=1 --deterministic --no-colour --plain 2>&1 \
            | shown | grep "ERROR\|\[OK\]\|\[FAIL\]\|Traceback\|AssertionError" \
            | grep -v " \. \. \. "
        echo "== hwut.report"
        python3 -m vut.services.report --plain --width=60 2>&1 \
            | grep "test-[a-e].sh" ;;
    pattern_first)
        page test-p.sh '#     title = "p"\n#     tolerance { eq_pattern = ["v[0-9]+\\\\.[0-9]+"] }\n' \
             'echo "release v2.50 built 7 files"'
        page test-n.sh '#     title = "n"\n' 'echo "release v2.50 built 7 files"'
        mkdir GOOD
        for name in test-p.sh test-n.sh; do
            printf 'release v1.00 built 7 files\n<hwut-end>\n' > GOOD/$name.txt
        done
        python3 -m vut.services.run --jobs=1 --deterministic --no-colour --plain 2>&1 \
            | grep "^END" ;;
    budget_spent)
        printf 'hwut {\n    language-setup { bash { extensions = [".sh"] interpreter = "bash" } }\n    app_defaults { diff_display_parameters { search_budget = 3 } }\n}\n' \
               > ../hwut-root.conf
        page test-d.sh '#     title = "d"\n' \
             'for i in 1 2 3; do echo "line $i of the new text"; done'
        mkdir GOOD
        { for i in 1 2; do echo "line $i of the old text"; done
          echo "<hwut-end>"; } > GOOD/test-d.sh.txt
        echo "== the budget, as the configuration shows it"
        $SHOW test-d.sh --no-default 2>&1 | grep "search_budget" | tr -s ' '
        echo "== hwut.run.diff test-d.sh --console"
        python3 -m vut.services.lib.run.diff test-d.sh --console 2>&1 \
            | grep "^[SN ] *[0-9]"
        echo "== hwut.run.diff test-d.sh -y --width 70"
        python3 -m vut.services.lib.run.diff test-d.sh -y --width 70 2>&1 \
            | grep "^ *[0-9]" ;;
    pype_fails)
        page test-p.sh '#     title = "p"\n#     pype  = "bad.pype"\n' 'echo x'
        page test-m.sh '#     title = "m"\n#     pype  = "missing.pype"\n' 'echo x'
        printf 'on: "x" =>\n' > bad.pype
        mkdir GOOD
        for name in test-p.sh test-m.sh; do
            printf 'x\n<hwut-end>\n' > GOOD/$name.txt
        done
        python3 -m vut.services.run --jobs=1 --deterministic --no-colour --plain 2>&1 \
            | grep "^END\|^SKIP\|^      test" ;;
    session)
        page test-i.sh '#     title = "i"\n#     interactive = true\n#     choices = ["a", "b"]\n' 'echo i'
        mkdir GOOD
        for choice in a b; do
            printf 'i\n<hwut-end>\n' > GOOD/test-i.sh--$choice.txt
        done
        $PLAN 2>&1 | shown ;;
    climb)
        page test-a.sh '#     title = "a"\n' 'echo a'
        $ACCEPT > /dev/null 2>&1 < /dev/null
        mkdir -p TMP/deep
        cd TMP/deep
        python3 -m vut.services.run --quiet 2>&1 | shown
        echo "STATUS: ${PIPESTATUS[0]}" ;;
esac
echo "<hwut-end>"
