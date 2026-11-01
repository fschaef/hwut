#! /usr/bin/env bash
#
# @hwut {
#     title      = "hwut_fsm: a state machine as the test's model of the system"
#     choices {
#         syntax    { features = ["bash-fsm"] }
#         refused   { features = ["bash-fsm"] }
#         dfa       { features = ["bash-fsm"] }
#         nfa       { features = ["bash-fsm"] }
#         forbidden { features = ["bash-fsm"] }
#         model     { features = ["bash-fsm"] }
#         report    { features = ["bash-fsm"] }
#         masks     { features = ["bash-fsm"] }
#     }
#     interactive = true
# }
#
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# PURPOSE: The bash port of 'python/TEST/test-hwut_fsm.py', choice for choice,
#          held against its GOOD files by '.link'. Where Python raises
#          FsmError, a function returns 1 and the text is in FSM_ERROR.
#______________________________________________________________________________
source "$(dirname "$0")/../hwut_runner.sh"
source "$(dirname "$0")/../hwut_fsm.sh"

#  THE PROTOCOL OF EVERY CHOICE: a request is waited on, granted, released;
#  a fault while busy crashes it -- which must never happen.
PROTOCOL='
    initial:   idle
    forbidden: crashed
    final:     idle
    idle    ---( request )---> waiting ---( grant )---> busy
    busy    ---( release )---> idle
    :       ---( fault )--->   crashed       # the state that began line 6
    waiting ---( cancel )---> idle
'

banner() { echo; echo "--- $1 ---"; }

said() {
    #  RETURN: 0, REPLY = 'True' where the command '$@' succeeds, 'False'.
    if "$@"; then REPLY=True; else REPLY=False; fi
}

path_text() {
    #  RETURN: 0, REPLY = the path to state '$2' of machine '$1' (options
    #             '$3...') as Python prints the tuple -- or 'None'.
    if fsm_machine_path_to "$@"; then pytext_tuple_repr str "${REPLY_LIST[@]}"
    else                               REPLY=None
    fi
}

run_syntax() {
    banner "the protocol, written back"
    fsm_machine_from_string m "$PROTOCOL"
    fsm_machine_to_string m; echo "$REPLY"
    banner "the author's form: 'state', a chain, ':', blanks around '-->'"
    fsm_machine_from_string m '
        state A ---( event )---> state B
        :                ---(event2)---> state C ---(event) --> state D
        state E          # no transition yet
    '
    fsm_machine_to_string m; echo "$REPLY"
}

run_refused() {
    local text
    for text in $'A ---( x )---> B\n: ---( x )---> C' \
                "A ---(  )---> B" \
                ": ---( x )---> B" \
                "A B ---( x )---> C" \
                $'initial: A, B\nA ---( x )---> B' \
                $'forbidden: Q\nA ---( x )---> B' \
                "# nothing but a comment"; do
        banner "${text//$'\n'/ | }"
        if fsm_machine_from_string m "$text"; then echo "accepted"
        else                                       echo "FsmError: $FSM_ERROR"
        fi
    done
}

run_dfa() {
    fsm_machine_from_string m "$PROTOCOL"
    local number=0 event
    for event in request release grant release jump request; do
        (( ++number ))
        said fsm_machine_fire m "$event" $number; local moved=$REPLY
        fsm_machine_state m;                      local state=$REPLY
        fsm_machine_allowed m;                    _fsm_joined ", " "${REPLY_LIST[@]}"
        printf '    %-8s -> %-5s now %-8s allowed: %s\n' "$event" "$moved" "$state" "$REPLY"
    done
    banner "questions where it stands"
    said fsm_machine_can m grant;          echo "can('grant')   $REPLY"
    said fsm_machine_can m release;        echo "can('release') $REPLY"
    said fsm_machine_in_state m waiting;   echo "in_state('waiting') $REPLY"
    fsm_machine_trace m
    local record where state event target out=()
    for record in "${REPLY_LIST[@]}"; do
        IFS=$FSM_SEP read -r where state event target <<< "$record"
        out+=("$where:$event>$target")
    done
    echo "trace: ${out[*]}"
}

run_nfa() {
    fsm_machine_from_string m '
        A ---( x )---> B ---( y )---> D
        : ---( x )---> C ---( y )---> E
        C ---( z )---> F
    ' dfa=0
    local event
    for event in x z y; do
        fsm_machine_fire m "$event" "t=$event"
        fsm_machine_current m; _fsm_joined ", " "${REPLY_LIST[@]}"
        echo "    after $event: $REPLY"
    done
    banner "'state' asked of a set"
    fsm_machine_reset m; fsm_machine_fire m x
    if fsm_machine_state m; then echo "$REPLY"; else echo "FsmError: $FSM_ERROR"; fi
}

run_forbidden() {
    fsm_machine_from_string m "$PROTOCOL"
    local number=0 event
    for event in request grant fault; do
        (( ++number ))
        said fsm_machine_fire m "$event" $number
        printf '    %-8s -> %s\n' "$event" "$REPLY"
    done
    fsm_machine_state m
    echo "now in $REPLY -- breaches: ${m[breach_n]}"
}

run_model() {
    fsm_machine_from_string m "$PROTOCOL"$'\n    state limbo\n    limbo ---( kick )---> idle\n'
    fsm_machine_check m; echo "check: $REPLY"
    banner "path_to"
    local state
    for state in busy crashed limbo idle; do
        path_text m "$state"
        printf '    %-8s %s\n' "$state" "$REPLY"
    done
    fsm_machine_fire m request
    path_text m busy start=now;                         echo "    busy from now: $REPLY"
    said fsm_machine_state_reachable m idle start=now;  echo "    state_reachable('idle', start='now'): $REPLY"
}

run_report() {
    fsm_machine_from_string m "$PROTOCOL" name=protocol
    local event
    for event in request grant release request grant; do fsm_machine_fire m "$event"; done
    fsm_machine_report m
    echo "report returns $REPLY"
}

run_masks() {
    fsm_machine_from_string m "$PROTOCOL"
    banner "'grant' disallowed in every state, since line 2"
    fsm_machine_disallow m grant "" 2
    fsm_machine_fire m request 3
    fsm_machine_allowed m; _fsm_joined ", " "${REPLY_LIST[@]}"; local allowed=$REPLY
    said fsm_machine_can m grant
    echo "    allowed now: $allowed -- can('grant'): $REPLY"
    fsm_machine_fire m grant 4
    path_text m busy;           echo "    path_to('busy'):               $REPLY"
    path_text m busy masked=0;  echo "    path_to('busy', masked=False): $REPLY"
    fsm_machine_check m;            echo "    check(): $REPLY"
    fsm_machine_check m masked=0;   echo "    check(masked=False): $REPLY"
    banner "allowed again; 'busy' forbidden while standing in it"
    fsm_machine_allow m grant "" 5
    fsm_machine_fire m grant 6
    fsm_machine_forbid m busy 7
    fsm_machine_fire m release 8
    fsm_machine_fire m request 9
    fsm_machine_fire m grant 10
    banner "permitted: 'busy', and the model's own 'crashed'"
    fsm_machine_permit m busy 11
    fsm_machine_permit m crashed 12
    said fsm_machine_fire m fault 13; local moved=$REPLY
    fsm_machine_state m
    echo "    fault -> $moved -- now in $REPLY"
    banner "a phase: 'release' disallowed in 'busy' for a block"
    fsm_machine_reset m
    fsm_machine_fire m request; fsm_machine_fire m grant
    fsm_machine_disallowed m release busy phase \
        fsm_machine_fire m release 20
    fsm_machine_fire m release 21
    fsm_machine_disallow m cancel "" 22
    fsm_machine_report m
    banner "refused: a word the model never names"
    fsm_machine_disallow m jump               || echo "FsmError: $FSM_ERROR"
    fsm_machine_forbid m limbo                || echo "FsmError: $FSM_ERROR"
    fsm_machine_allow m grant nowhere         || echo "FsmError: $FSM_ERROR"
}

declare -A choice_map=(
    [syntax]=run_syntax [refused]=run_refused [dfa]=run_dfa [nfa]=run_nfa
    [forbidden]=run_forbidden [model]=run_model [report]=run_report [masks]=run_masks
)
hwut_runner_new runner "hwut_fsm: a state machine as the test's model of the system" choice_map
hwut_runner_run runner "$@"
