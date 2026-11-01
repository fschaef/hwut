#! /usr/bin/env bash
#
# @hwut {
#     title      = "HOCON parser: subset (A), annotated tree"
#     choices {
#         comments  { features = ["bash-hocon"] }
#         faults    { features = ["bash-hocon"] }
#         fuzz      { features = ["bash-hocon"] }
#         numbers   { features = ["bash-hocon"] }
#         oneline   { features = ["bash-hocon"] }
#         positions { features = ["bash-hocon"] }
#         quoting   { features = ["bash-hocon"] }
#         refused   { features = ["bash-hocon"] }
#         scalars   { features = ["bash-hocon"] }
#         structure { features = ["bash-hocon"] }
#         triple    { features = ["bash-hocon"] }
#         unclosed  { features = ["bash-hocon"] }
#     }
#     interactive = true
# }
#
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# PURPOSE: The bash port of 'python/TEST/test-hwut_hocon.py', choice for
#          choice, held against its GOOD files by '.link'. 'fuzz' draws its
#          3000 mutated headers from the same stream as Python's, and owes
#          the same counts.
#______________________________________________________________________________
source "$(dirname "$0")/../hwut_runner.sh"
source "$(dirname "$0")/../hwut_hocon.sh"
source "$(dirname "$0")/../deterministic_random.sh"

banner() { echo; echo "--- $1 ---"; }

show() {
    #  RETURN: 0; the node '$1' of the tree 'doc' printed, positions
    #          included, indented by '$2' levels.
    local node=$1 indent=${2:-0} pad child
    printf -v pad '%*s' $(( 4 * indent )) ''
    case ${doc_kind[node]} in
        object)
            echo "$pad{ at ${doc_position[node]}"
            for child in ${doc_children[node]}; do
                echo "$pad  key '${doc_key[child]}' at ${doc_key_position[child]} ->"
                show "$child" $(( indent + 1 ))
            done
            echo "$pad}" ;;
        list)
            echo "$pad[ at ${doc_position[node]}"
            for child in ${doc_children[node]}; do show "$child" $(( indent + 1 )); done
            echo "$pad]" ;;
        *)
            hocon_value_repr doc "$node"
            echo "$pad$REPLY (${doc_kind[node]}) at ${doc_position[node]}" ;;
    esac
}

run() {
    #  RETURN: 0; the text '$2' parsed -- its lines numbered from 1 + '$3',
    #          offset by '$4' columns -- and tree and faults printed under
    #          the banner '$1'.
    banner "$1"
    hocon_source_lines src "$2" "${3:-0}" "${4:-0}"
    hocon_parse doc src f.hocon
    show "${doc[root]}"
    local i
    for (( i = 0; i < ${#doc_fault_message[@]}; ++i )); do
        hocon_fault_text doc $i; echo "FAULT $REPLY"
    done
}

test_scalars() {
    run "scalars" \
'a = bare
b = "quoted \"x\" and \n"
c = 42
d = -3.14
e = 1e-6
f = true
g = no
h = make %.exe
i: "colon-bound"
j = null
k = nihil
l =
'
}

test_numbers() {
    run "decimal, with sign and exponent" \
$'a = 42\nb = -0.12\nc = +7e212\nd = 6.02e23\ne = .5\n'
    run "the visual helper enters no value" \
$'a = 1_000\nb = 7_000.5_5\n'
    run "hexadecimal, binary, octal" \
$'a = 0xDEAD_BEEF\nb = 0b0111_11_01\nc = 0o3124\nd = 0XFF\ne = -0b1010\n'
    run "roman" \
$'a = 0rIV\nb = 0rMCMLXXXIV\nc = -0rX\n'
    run "a sign standing apart from its digits" \
$'a = - 0.12\nb = + 7\nc = - 0xFF\nd = - -1.5e3\n'
    run "what spells no number is a string, and carries quotes" \
$'a = 1.2.3\nb = 0x\nc = 0b012\nd = 1__0\ne = 0rIIII\nf = 0rVX\n'
    run "no arithmetic: this language computes nothing" \
$'a = 5 - 1\n'
}

test_quoting() {
    run "quoted: blanks, comment markers and binders are content" \
$'a = "make %.exe"\nb = "not # a comment"\nc = "x = y"\nd = "yes"\n'
    run "unquoted: refused, and shown in the quotes it wants" \
$'a = make\nb = strip.pype\nc = [one, two]\nd = 1\n'
}

test_structure() {
    run "nesting and key-brace" \
$'outer {\n    inner = { deep = 1 }\n    braced { x = 2 }\n}\n'
    run "lists" \
$'commas   = [one, two, three]\nnewlines = [\n    1\n    2\n]\nobjects  = [ { a = 1 }, { a = 2 } ]\nempty    = []\n'
}

test_oneline() {
    run "two entries, one line, no comma" \
$'caps { timeout_sec = 30  network = false }\n'
    run "a quoted value with blanks, beside a following key" \
$'a { build = "make %.exe"  timeout_sec = 5 }\n'
    run "three entries, one line" \
$'x { a = 1  b = "two"  c = { d = 3 } }\n'
}

test_comments() {
    run "comments" \
$'# whole line\na = 1   # trailing\n// slashes too\nb = 2   // trailing slashes\nc = bare value # comment cut\n'
}

test_refused() {
    run "refused, each by name" \
$'include "other.conf"\na = ${outside.value}\nb += appended\nd = survives\n'
}

test_triple() {
    local q='"""'
    run "several lines: indentation and blank ends go" \
"doc = $q
    First line.

      indented more
    last line
    $q
after = 1
"
    run "on one line; beside another entry; in a list" \
"a = ${q}one line$q  b = 2
c = [${q}x$q, \"y\"]
"
    run "as written: a quote, a backslash-n, a comment marker" \
"a = ${q}says \"no\" \\n # not a comment$q
"
    run "never closed: a fault, at its beginning" \
"a = 1
b = ${q}open
c = 2
"
}

test_faults() {
    run "faults accumulate" \
$'a = 1\na = 2\nb = "unterminated\n}\nc {\n    d = 3\n'
}

test_unclosed() {
    run "a list closed by the object's brace" \
$'@hwut { title = "B" choices = [ }\nafter = 1\n'
    run "a stray character in a list" \
$'a = [1, ; 2]\n'
}

FUZZ_SEED_TUPLE=(
$'@hwut {\n    title    = "T"\n    choices  = ["a", "b"]\n    tolerance { eq_pattern = ["x.*"] }\n    n        = -1.5e3\n    f        = true\n}\n'
$'hwut {\n    target     { clean = "./c.sh" }\n    dependency { "a.py" = ["b.py one"] }\n    ignore     = ["x"]   // comment\n    # comment\n}\n'
)
#  WHAT A TYPO IS MADE OF: the characters HOCON gives meaning to, a few
#  that it refuses by name, and some ordinary ones.
FUZZ_ALPHABET=('{' '}' '[' ']' '"' ',' '=' ':' '#' '/' '\' '$' ' ' $'\n' $'\t' '-' '+' '.' 'e' 'E' '0' 'a'
               '"""' '${' '//' '+=')
FUZZ_INPUT_N=3000
FUZZ_BOUND_S=0.5                 # one parse takes a few milliseconds

mutated() {
    #  RETURN: 0, REPLY = the text '$2' edited by one to four random
    #             insertions, deletions and duplications of a short stretch,
    #             drawn from the stream '$1'.
    local stream_name=$1 text=$2 n k i j
    dr_stream_next_int "$stream_name" 1 4; n=$REPLY
    for (( k = 0; k < n; ++k )); do
        dr_stream_next_int "$stream_name" 0 ${#text}; i=$REPLY
        dr_stream_next_int "$stream_name" 0 2
        case $REPLY in
            0) dr_stream_select "$stream_name" FUZZ_ALPHABET
               text=${text:0:i}$REPLY${text:i} ;;
            1) text=${text:0:i}${text:i+1} ;;
            *) dr_stream_next_int "$stream_name" 0 ${#text}; j=$REPLY
               text=${text:0:i}${text:j:5}${text:i} ;;
        esac
    done
    REPLY=$text
}

test_fuzz() {
    local LC_ALL=C
    local -A tally=([clean]=0 [with faults]=0 [hang]=0 [exception]=0) example=()
    local k text status
    dr_stream_new fuzz_stream 4711
    for (( k = 0; k < FUZZ_INPUT_N; ++k )); do
        dr_stream_select fuzz_stream FUZZ_SEED_TUPLE
        mutated fuzz_stream "$REPLY"; text=$REPLY
        hocon_source_lines src "$text"
        hocon_parse doc src f.hocon bound_s=$FUZZ_BOUND_S; status=$?
        if (( status == 2 )); then
            (( ++tally[hang] ))
            [[ -n ${example[hang]+x} ]] || example[hang]=$text
        elif (( status != 0 )); then
            (( ++tally[exception] ))
            [[ -n ${example[exception]+x} ]] || example[exception]="status $status"$'\n'$text
        elif (( ${#doc_fault_message[@]} )); then
            (( ++tally[with faults] ))
        else
            (( ++tally[clean] ))
        fi
    done
    banner "$FUZZ_INPUT_N mutated headers"
    for k in clean "with faults" hang exception; do printf '    %-12s %d\n' "$k" "${tally[$k]}"; done
    for k in hang exception; do
        [[ -n ${example[$k]+x} ]] && printf 'FIRST %s:\n%s\n' "${k^^}" "${example[$k]}"
    done
}

test_positions() {
    local text=$'@hwut {\n    title = "T"\n}'
    run "plain: as its own file" "$text"
    run "offset: same text, region begins at line 40, 3 columns stripped" "$text" 39 3
}

declare -A choice_map=(
    [scalars]=test_scalars [numbers]=test_numbers [quoting]=test_quoting
    [structure]=test_structure [oneline]=test_oneline [comments]=test_comments
    [refused]=test_refused [triple]=test_triple [unclosed]=test_unclosed
    [fuzz]=test_fuzz [faults]=test_faults [positions]=test_positions
)
hwut_runner_new runner "HOCON parser: subset (A), annotated tree;" choice_map
hwut_runner_run runner "$@"
