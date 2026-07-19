#!/bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#
# tool/hwut_compare.py: colorized tolerance-lexing preview (CLI).
#
# Pins the tool's contract: per-element styling (analogy ORANGE-on-WHITE,
# number BLUE, equivalence pattern GREEN-on-GREY, constraint binding
# MAGENTA/bold, region framing bold CYAN, blank/ignored/separator dim);
# stdin and <file> usage identical; not-lexed regions (verbatim, ignore,
# point-cloud, table) shown plain with a note; '--config' overrides;
# '--no-color'/NO_COLOR suppression; the 'hwut.compare' wrapper; clean
# error paths (no tracebacks).
#
# The tool is exercised exactly as a user would call it -- the golden pins
# the actual command-line behavior, escape codes made printable as '\e'.
#
# Scratch files live in a private mktemp directory, removed on exit. The
# tmp path is nondeterministic, so 'printable' masks it as '<tmp>' --
# error messages that embed the path stay stable in the golden.

if [ "$1" == "--hwut-info" ]; then
    echo "Tool hwut_compare.py: colorized lexing preview;"
    echo "CHOICES: lexing, stdin-and-wrapper, config, errors;"
    exit 0
fi

cd "$(dirname "$0")" || exit 1
TOOL=../hwut_compare.py
WRAPPER=../hwut.compare
unset NO_COLOR

TMP=$(mktemp -d) || exit 1
trap 'rm -rf "$TMP"' EXIT

# Escape codes printable: ESC -> '\e'; tmp path masked as '<tmp>'
# (goldens stay readable, deterministic text).
printable() { sed "s|$TMP|<tmp>|g; s/\x1b/\\\\e/g"; }

# run <title> <args...>: print title + exit code, stdout, stderr -- the
# same frame for every probe, so the golden reads uniformly.
run() {
    local title="$1"; shift
    local out err code
    out=$("$@" 2>"$TMP"/hct-stderr.txt); code=$?
    err=$(printable < "$TMP"/hct-stderr.txt)
    echo "::::: $title (exit $code)"
    [ -n "$out" ] && echo "$out" | printable
    [ -n "$err" ] && echo "STDERR: $err"
    echo
}

write_sample() {
    cat > "$TMP"/hct-sample.txt <<'EOF'
Ordinary line with text and 42 and 3.14
created ((obj))
using   ((obj))
start ((t: 12.5))
##! potpourri
z 7
a 1
####
##! verbatim
byte  exact    line
####
##! ignore
whatever 99 ((x))
####
##! point-cloud limit=0.5
1.0 2.0
####
##! table
a 1
####
## a pure comment line

tail 7
EOF
}

# ------------------------------------------------------------------------------
if [ "$1" == "lexing" ]; then
    write_sample
    echo "## Element styling, forced on with --color; '\e' == ESC."
    echo "## analogy=38;5;208+48;5;255  number=38;5;33  binding=1+38;5;201"
    echo "## region framing=1+38;5;51   blank/ignored/separator=2 (dim)"
    echo
    run "file argument, --color" python3 $TOOL --color "$TMP"/hct-sample.txt
fi

# ------------------------------------------------------------------------------
if [ "$1" == "stdin-and-wrapper" ]; then
    write_sample
    echo "## The three invocation forms must agree byte-for-byte."
    python3 $TOOL --color "$TMP"/hct-sample.txt   > "$TMP"/hct-by-file.txt
    python3 $TOOL --color < "$TMP"/hct-sample.txt > "$TMP"/hct-by-stdin.txt
    $WRAPPER      --color "$TMP"/hct-sample.txt   > "$TMP"/hct-by-wrap.txt
    cmp -s "$TMP"/hct-by-stdin.txt "$TMP"/hct-by-file.txt \
        && echo "stdin  == file argument: True"  \
        || echo "stdin  == file argument: FALSE"
    cmp -s "$TMP"/hct-by-wrap.txt "$TMP"/hct-by-file.txt \
        && echo "wrapper == file argument: True"  \
        || echo "wrapper == file argument: FALSE"
    echo
    echo "## Suppression: --no-color and NO_COLOR both yield escape-free"
    echo "## output (a piped stdout is already non-tty, so the flag is"
    echo "## what carries the intent)."
    python3 $TOOL --no-color "$TMP"/hct-sample.txt > "$TMP"/hct-plain-flag.txt
    NO_COLOR=1 python3 $TOOL "$TMP"/hct-sample.txt > "$TMP"/hct-plain-env.txt
    grep -q $'\x1b' "$TMP"/hct-plain-flag.txt \
        && echo "--no-color escape-free: FALSE" \
        || echo "--no-color escape-free: True"
    grep -q $'\x1b' "$TMP"/hct-plain-env.txt \
        && echo "NO_COLOR   escape-free: FALSE" \
        || echo "NO_COLOR   escape-free: True"
    cmp -s "$TMP"/hct-plain-flag.txt "$TMP"/hct-plain-env.txt \
        && echo "both plain outputs equal: True" \
        || echo "both plain outputs equal: FALSE"
fi

# ------------------------------------------------------------------------------
if [ "$1" == "config" ]; then
    cat > "$TMP"/hct-config-sample.txt <<'EOF'
mood happy
mood glad
nix
value 42
[[Q]] and [[Q]]
EOF
    echo "## --config overrides: equivalence pattern, visible-nothing,"
    echo "## numeric OFF, analogy markers '[[' ']]'."
    cat > "$TMP"/hct-config.py <<'EOF'
equivalent_pattern_list      = [r"happy|glad"]
visible_nothing_pattern_list = ["nix"]
numeric_tolerance_ratio      = 0
analogy_begin_marker         = "[["
analogy_end_marker           = "]]"
EOF
    run "with config (pattern green/grey, 'nix' dim, 42 plain, [[Q]] analogy)" \
        python3 $TOOL --color --config "$TMP"/hct-config.py "$TMP"/hct-config-sample.txt
    run "same input, preview defaults (patterns plain, 42 blue, [[Q]] plain)" \
        python3 $TOOL --color "$TMP"/hct-config-sample.txt
fi

# ------------------------------------------------------------------------------
if [ "$1" == "errors" ]; then
    write_sample
    echo "## Error paths exit 1 with a one-line message -- NO traceback."
    run "missing input file" \
        python3 $TOOL "$TMP"/hct-no-such-file.txt
    run "missing config file" \
        python3 $TOOL --config "$TMP"/hct-no-such-cfg.py < /dev/null

    echo "## --help prints the module docstring (PURPOSE line shown)."
    HELP_OUT=$(python3 $TOOL --help); HELP_CODE=$?
    PURPOSE=$(echo "$HELP_OUT" | grep -m1 "PURPOSE:" | sed 's/^ *//;s/ *$//')
    echo "help exit: $HELP_CODE; $PURPOSE"

    echo "## Broken pipe (| head -2) is quiet -- no traceback on stderr."
    HEAD_OUT=$(python3 $TOOL --no-color "$TMP"/hct-sample.txt 2>"$TMP"/hct-stderr.txt | head -2)
    LINE_N=$(echo "$HEAD_OUT" | wc -l)
    [ -s "$TMP"/hct-stderr.txt ] \
        && echo "head output lines: $LINE_N; stderr empty: FALSE" \
        || echo "head output lines: $LINE_N; stderr empty: True"
fi
