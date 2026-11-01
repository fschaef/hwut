# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# PURPOSE: FRONT END OF A HWUT TEST APPLICATION IN BASH -- the port of
#          'python/hwut_runner.py': the same modes, the same words.
#
#     app --hwut-info      the info block; exit 0.
#     app <choice>         one choice; test output on stdout and stderr,
#                          '<hwut-end>' after it. '-' runs a choice-less test.
#     app --interactive    choices started over stdin, output into two named
#                          sink files per choice, 'done' on the original stdout.
#     app                  the choice-less test; where the application has
#                          choices, refused, naming them.
#
# USAGE:
#
#     source "$(dirname "$0")/../hwut_runner.sh"
#     run_plain()  { ...; }
#     run_tricky() { ...; }
#     declare -A choice_map=([plain]=run_plain [tricky]=run_tricky)
#     hwut_runner_new runner "What this tests" choice_map
#     hwut_runner_run runner "$@"
#
# THE OBJECT is an associative array named by the caller; the choice map is
# another, choice name -> function name. A choice-less test maps '-'. Before
# 'hwut_runner_run' a test may set 'runner[same_f]=1', 'runner[parallel]=
# process' (interactive: choices run concurrently) and append HAPPY patterns
# to the array named in 'runner[happy]' (default '<runner>_happy').
#
# THE INTERACTIVE PROTOCOL is Python's, line for line:
#     DOWN  run <choice> <sink-out> <sink-err> | info | quit | q | exit
#     UP    done <choice> <status> | fail <choice> <reason> | info: <line> | bye
# EVERY CHOICE RUNS IN A SUBSHELL of its own: an 'exit' in a choice ends that
# choice, not the session -- what Python gets by catching SystemExit -- and
# no choice inherits another's variables.
#______________________________________________________________________________
[[ -n ${_HWUT_RUNNER_SH:-} ]] && return 0
_HWUT_RUNNER_SH=1
source "${BASH_SOURCE[0]%/*}/hwut_pytext.sh"

hwut_runner_new() {
    #  RETURN: 0, the global associative array named '$1' is a runner, ready
    #             for 'hwut_runner_run': title '$2', choice map '$3' (the
    #             name of an associative array choice -> function).
    local -n _hr_self=$1
    declare -gA "$1"
    declare -ga "$1_happy" "$1_sorted"
    _hr_self=([title]=$2 [choice_map]=$3 [happy]="$1_happy" [same_f]=0 [parallel]=""
              [sorted]="$1_sorted")
    local -n _hr_map=$3 _hr_sorted="$1_sorted"
    local _hr_keys=("${!_hr_map[@]}")
    pytext_sorted _hr_keys
    _hr_sorted=("${REPLY_LIST[@]}")
}

_hwut_runner_none_f() {
    #  RETURN: 0, where the runner '$1' is choice-less ('-' its one choice);
    #          1, else.
    local -n _hr_self=$1
    local -n _hr_map=${_hr_self[choice_map]}
    (( ${#_hr_map[@]} == 1 )) && [[ -n ${_hr_map[-]+x} ]]
}

_hwut_runner_info_lines() {
    #  RETURN: 0, REPLY_LIST = the lines of the runner '$1's info block:
    #             title, CHOICES, HAPPY patterns, SAME, INTERACTIVE.
    local -n _hr_self=$1
    local -n _hr_happy=${_hr_self[happy]} _hr_sorted=${_hr_self[sorted]}
    local title=${_hr_self[title]} pattern list
    [[ $title == *";" ]] || title+=";"
    local lines=("$title")
    if ! _hwut_runner_none_f "$1"; then
        printf -v list '%s, ' "${_hr_sorted[@]}"
        lines+=("CHOICES: ${list%, };")
    fi
    for pattern in "${_hr_happy[@]}"; do lines+=("HAPPY: $pattern;"); done
    (( ${_hr_self[same_f]} )) && lines+=("SAME;")
    lines+=("INTERACTIVE;")
    REPLY_LIST=("${lines[@]}")
}

_hwut_runner_choice_list_text() {
    #  RETURN: 0, REPLY = the sorted choices of runner '$1', joined by ', '.
    local -n _hr_self=$1
    local -n _hr_sorted=${_hr_self[sorted]}
    printf -v REPLY '%s, ' "${_hr_sorted[@]}"
    REPLY=${REPLY%, }
}

hwut_runner_run() {
    #  RETURN: never; exits with the status of the mode the command line
    #          '$2' selects (see the head): 0 for the info block and a choice
    #          that ran, 1 for a refusal.
    local self=$1 word=${2-} have_word_f=$(( $# >= 2 ))
    local -n _hr_self=$1
    local -n _hr_map=${_hr_self[choice_map]}
    case $word in
        -h|--hi|--hwut-info|--sos|--wtf)
            _hwut_runner_info_lines "$self"
            printf '%s\n' "${REPLY_LIST[@]}"
            exit 0 ;;
        --interactive)
            _hwut_runner_interactive "$self"
            exit 0 ;;
    esac
    _hwut_runner_choice_list_text "$self"
    if (( ! have_word_f )); then
        if _hwut_runner_none_f "$self"; then _hwut_runner_run_one "${_hr_map[-]}"; exit 0; fi
        echo "error: a choice is required: $REPLY -- name one, or let 'hwut.play' ask."
        exit 1
    fi
    if [[ -n ${_hr_map[$word]+x} ]]; then _hwut_runner_run_one "${_hr_map[$word]}"; exit 0; fi
    if _hwut_runner_none_f "$self"; then
        echo "error: '$word': this application has no choices -- call it without one."
        exit 1
    fi
    echo "error: choice '$word' not available."
    echo "error: available: $REPLY."
    local -n _hr_sorted=${_hr_self[sorted]}
    if hwut_runner_levenshtein_best_match "$word" "${_hr_sorted[@]}"; then
        echo "error: did you mean '$REPLY'?"
    fi
    exit 1
}

_hwut_runner_run_one() {
    #  RETURN: 0; the choice's function '$1' ran, then '<hwut-end>' (R-70).
    #          A choice that calls 'exit' ends the application there.
    "$1"
    echo "<hwut-end>"
}

# ------------------------------------------------------------ interactive mode
_hwut_runner_up() {
    #  RETURN: 0; '$1' and a newline are written on the UP channel -- one
    #          write, so lines of concurrent choices never interleave.
    printf '%s\n' "$1" >&"$_hwut_runner_control"
}

_hwut_runner_find_choice() {
    #  RETURN: 0, REPLY = the function of the choice the token '$2' names --
    #             by name, by its index into the sorted list, or '-' for
    #             the choice-less test;
    #          1, no choice of runner '$1' is named.
    local -n _hr_self=$1
    local -n _hr_map=${_hr_self[choice_map]} _hr_sorted=${_hr_self[sorted]}
    local token=$2
    if [[ -n ${_hr_map[$token]+x} ]]; then REPLY=${_hr_map[$token]}; return 0; fi
    if [[ $token =~ ^[0-9]+$ ]] && (( 10#$token < ${#_hr_sorted[@]} )); then
        REPLY=${_hr_map[${_hr_sorted[10#$token]}]}; return 0
    fi
    return 1
}

_hwut_runner_into_sinks() {
    #  RETURN: the status the choice's function '$1' ended with -- 0 where
    #          it returned ('<hwut-end>' then written, unless
    #          HWUT_NO_TERMINAL), n where it called 'exit n'. It runs in a
    #          subshell with fd 1 on '$2' and fd 2 on '$3'; both are closed
    #          upon the return -- the 'done' barrier for the choice's own
    #          writes.
    ( exec {_hwut_runner_control}>&-
      "$1"
      [[ -z ${HWUT_NO_TERMINAL:-} ]] && echo "<hwut-end>"
      exit 0 ) >"$2" 2>"$3"
}

_hwut_runner_interprete() {
    #  RETURN: 0, the session goes on; 1, it ends ('quit', 'q', 'exit').
    #          Replies on the UP channel; a parallel runner's choice is
    #          reported 'done' by its own background job when it ends.
    local self=$1 line=$2 fields
    local -n _hr_self=$1
    read -ra fields <<< "$line"
    case ${#fields[@]}:${fields[0]} in
        1:quit|1:q|1:exit)
            return 1 ;;
        1:info)
            _hwut_runner_info_lines "$self"
            local info_line
            for info_line in "${REPLY_LIST[@]}"; do _hwut_runner_up "info: $info_line"; done
            _hwut_runner_up "done - 0" ;;
        4:run)
            if ! _hwut_runner_find_choice "$self" "${fields[1]}"; then
                _hwut_runner_up "fail ${fields[1]} unknown-choice"
            elif [[ ${_hr_self[parallel]} == process ]]; then
                { _hwut_runner_into_sinks "$REPLY" "${fields[2]}" "${fields[3]}"
                  _hwut_runner_up "done ${fields[1]} $?"; } &
            else
                _hwut_runner_into_sinks "$REPLY" "${fields[2]}" "${fields[3]}"
                _hwut_runner_up "done ${fields[1]} $?"
            fi ;;
        *)
            _hwut_runner_up "fail - bad-command" ;;
    esac
    return 0
}

_hwut_runner_interactive() {
    #  RETURN: 0, once the session ended ('quit' or end of input) and every
    #             choice still running was waited for. The original stdout
    #             is the UP channel; fd 1 and fd 2 point at a stray sink.
    local self=$1 line stray
    stray=$(mktemp "${TMPDIR:-/tmp}/hwut_stray_XXXXXX")
    exec {_hwut_runner_control}>&1
    exec >"$stray" 2>&1
    while IFS= read -r line || [[ -n $line ]]; do
        line=${line#"${line%%[![:space:]]*}"}
        line=${line%"${line##*[![:space:]]}"}
        [[ -z $line ]] && continue
        _hwut_runner_interprete "$self" "$line" || break
    done
    wait
    _hwut_runner_up "bye"
}

# ------------------------------------------------------------------ distance
hwut_runner_levenshtein_distance() {
    #  RETURN: 0, REPLY = the Levenshtein distance between '$1' and '$2',
    #             >= 0.
    local a=$1 b=$2 i j ins del sub
    if [[ $a == "$b" ]]; then REPLY=0; return 0; fi
    if [[ -z $a ]]; then REPLY=${#b}; return 0; fi
    if [[ -z $b ]]; then REPLY=${#a}; return 0; fi
    if (( ${#a} < ${#b} )); then local t=$a; a=$b; b=$t; fi
    local -a prev cur
    for (( j = 0; j <= ${#b}; ++j )); do prev[j]=$j; done
    for (( i = 1; i <= ${#a}; ++i )); do
        cur=([0]=$i)
        for (( j = 1; j <= ${#b}; ++j )); do
            ins=$(( cur[j-1] + 1 )); del=$(( prev[j] + 1 ))
            [[ ${a:i-1:1} == "${b:j-1:1}" ]] && sub=$(( prev[j-1] )) || sub=$(( prev[j-1] + 1 ))
            (( ins < del )) && cur[j]=$ins || cur[j]=$del
            (( sub < cur[j] )) && cur[j]=$sub
        done
        prev=("${cur[@]}")
    done
    REPLY=${prev[${#b}]}
}

hwut_runner_levenshtein_best_match() {
    #  RETURN: 0, REPLY = the element of '$2...' least distant from '$1'
    #             (the first among equals);
    #          1, no elements are given.
    local needle=$1 key best="" best_d=-1; shift
    (( $# == 0 )) && return 1
    for key; do [[ $key == "$needle" ]] && { REPLY=$needle; return 0; }; done
    for key; do
        hwut_runner_levenshtein_distance "$needle" "$key"
        if (( best_d < 0 || REPLY < best_d )); then best_d=$REPLY; best=$key; fi
    done
    REPLY=$best
}
