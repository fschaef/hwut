# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# PURPOSE: A STATE MACHINE AS A TEST'S MODEL OF THE SYSTEM UNDER TEST -- the
#          port of 'python/hwut_fsm.py' (its README: '../python/README-
#          hwut_fsm.txt'). A test FIRES the events it observes; every event
#          the model does not allow, and every forbidden state entered, is
#          PRINTED as a line -- so it lands in the GOOD file.
#
#     fsm_machine_from_string m '
#         initial: idle
#         forbidden: crashed
#         idle    ---( request )---> waiting ---( grant )---> busy
#         busy    ---( release )---> idle
#         :       ---( fault )--->   crashed
#     ' || echo "FsmError: $FSM_ERROR"
#     fsm_machine_fire m request 1     # status 0
#     fsm_machine_fire m release 2     # BREACH line 2: 'release' in 'waiting' -- allowed: grant
#     fsm_machine_report m             # what was visited, what never was
#
# THE OBJECT is the global associative array named by the caller ('m'),
# with arrays of its own named '<m>_...'. Options follow the positional
# arguments as 'key=value': 'dfa=0' (Python's DFA=False), 'name=protocol',
# 'write=<function>' (takes one line; default: print it), 'masked=0',
# 'start=now'.
#
# WHERE PYTHON RAISES FsmError, a function returns 1 and the message stands
# in FSM_ERROR. A RESULT stands in REPLY (a text, a count) or REPLY_LIST (a
# tuple); a bool is the status. 'path_to' returns 1 for Python's None.
# A 'where' is a text: digits name a line ('line 3'), any other text stands
# as written, '' (or none given) names no place -- Python's None.
#
# A trace record and an edge key join their fields by FSM_SEP ($'\x1f').
#______________________________________________________________________________
[[ -n ${_HWUT_FSM_SH:-} ]] && return 0
_HWUT_FSM_SH=1
source "${BASH_SOURCE[0]%/*}/hwut_pytext.sh"

FSM_SEP=$'\x1f'
FSM_ERROR=""

_FSM_ARROW_RE='-+[[:space:]]*\(([^()]*)\)[[:space:]]*-*>'
_FSM_NAME_RE='^(state[[:space:]]+)?([A-Za-z_][A-Za-z0-9_.-]*)$'
_FSM_KEY_RE='^(initial|forbidden|final)[[:space:]]*:[[:space:]]*(.*)$'

fsm_print_line() {
    #  RETURN: 0; '$1' was printed, with a newline -- the default 'write'.
    printf '%s\n' "$1"
}

_fsm_strip() {
    #  RETURN: 0, REPLY = '$1' without the blanks around it.
    REPLY=${1#"${1%%[![:space:]]*}"}
    REPLY=${REPLY%"${REPLY##*[![:space:]]}"}
}

_fsm_where_text() {
    #  RETURN: 0, REPLY = ' line 3' for '3', ' <text>' for a text, '' for
    #             none -- the place a breach line names.
    if   [[ -z $1 ]];            then REPLY=""
    elif [[ $1 =~ ^[0-9]+$ ]];   then REPLY=" line $1"
    else                              REPLY=" $1"
    fi
}

_fsm_since_text() {
    #  RETURN: 0, REPLY = ' since line 9' for '9', ' since <text>' for a
    #             text, '' for none -- when a mask or a forbidden state began.
    _fsm_where_text "$1"
    [[ -n $REPLY ]] && REPLY=" since$REPLY"
}

_fsm_name_of() {
    #  RETURN: 0, REPLY = the state named by '$1' -- 'A' or 'state A';
    #          1, else -- FSM_ERROR names line '$2'.
    _fsm_strip "$1"
    if [[ $REPLY =~ $_FSM_NAME_RE ]]; then REPLY=${BASH_REMATCH[2]}; return 0; fi
    FSM_ERROR="line $2: '$REPLY' names no state -- a state is a word ('A', 'state A')"
    return 1
}

_fsm_options() {
    #  RETURN: 0; the 'key=value' words '$@' stand in the associative array
    #          '_fsm_option' (declared by the caller).
    local word
    for word; do _fsm_option[${word%%=*}]=${word#*=}; done
}

_fsm_joined() {
    #  RETURN: 0, REPLY = the words '$2...' joined by the text '$1'.
    local separator=$1 out="" word; shift
    for word; do out+="${out:+$separator}$word"; done
    REPLY=$out
}

_fsm_quoted_joined() {
    #  RETURN: 0, REPLY = the words '$@' each in single quotes, joined by
    #             ', ' -- "'a', 'b'".
    local out="" word
    for word; do out+="${out:+, }'$word'"; done
    REPLY=$out
}

# ---------------------------------------------------------------- reading
fsm_machine_new() {
    #  RETURN: 0, the machine '$1' stands in its initial state;
    #          1, else -- FSM_ERROR: a DFA with two transitions for one
    #             (state, event); a forbidden or final state no transition
    #             names.
    #
    #  Options: 'initial=<state>' (required), 'transitions=<array name>'
    #  (elements 'source${FSM_SEP}event${FSM_SEP}target'), 'states=<state
    #  ...>' named by no transition (yet), 'forbidden=<state ...>',
    #  'final=<state ...>', 'dfa=0', 'name=<text>', 'write=<function>'.
    local self=$1; shift
    local -A _fsm_option=([dfa]=1 [name]=fsm [write]=fsm_print_line [transitions]="" \
                          [states]="" [forbidden]="" [final]="")
    _fsm_options "$@"
    declare -gA "$self" "${self}_edge" "${self}_eventset"
    declare -ga "${self}_states" "${self}_events"
    local -n _fsm_self=$self _fsm_edge=${self}_edge _fsm_eventset=${self}_eventset
    local -n _fsm_states=${self}_states _fsm_events=${self}_events
    _fsm_self=([name]=${_fsm_option[name]} [dfa_f]=${_fsm_option[dfa]} [write]=${_fsm_option[write]}
               [initial]=${_fsm_option[initial]} [model_forbidden]="" [final]="")
    _fsm_edge=(); _fsm_eventset=()
    local -A state_set=([${_fsm_option[initial]}]=1)
    local state source event target triple
    for state in ${_fsm_option[states]}; do state_set[$state]=1; done
    if [[ -n ${_fsm_option[transitions]} ]]; then
        local -n _fsm_triples=${_fsm_option[transitions]}
        for triple in "${_fsm_triples[@]}"; do
            IFS=$FSM_SEP read -r source event target <<< "$triple"
            local key=$source$FSM_SEP$event
            local targets=${_fsm_edge[$key]-}
            if (( _fsm_self[dfa_f] )) && [[ -n $targets && " $targets " != *" $target "* ]]; then
                pytext_sorted_words $targets
                FSM_ERROR="'$source' --($event)--> '${REPLY_LIST[0]}' and '$target': a DFA moves one way per event -- or 'DFA=False'"
                return 1
            fi
            [[ " $targets " == *" $target "* ]] || targets+="${targets:+ }$target"
            pytext_sorted_words $targets
            _fsm_edge[$key]="${REPLY_LIST[*]}"
            _fsm_eventset[$event]=1
            state_set[$source]=1; state_set[$target]=1
        done
    fi
    local label chosen unknown
    for label in forbidden final; do
        unknown=()
        for state in ${_fsm_option[$label]}; do [[ -z ${state_set[$state]+x} ]] && unknown+=("$state"); done
        if (( ${#unknown[@]} )); then
            pytext_sorted unknown
            _fsm_quoted_joined "${REPLY_LIST[@]}"
            FSM_ERROR="$label state(s) $REPLY: named nowhere else in the model"
            return 1
        fi
    done
    pytext_sorted_words ${_fsm_option[forbidden]}; _fsm_self[model_forbidden]="${REPLY_LIST[*]}"
    pytext_sorted_words ${_fsm_option[final]};     _fsm_self[final]="${REPLY_LIST[*]}"
    for state in ${_fsm_self[model_forbidden]}; do state_set[$state]=1; done
    pytext_sorted_words "${!state_set[@]}";  _fsm_states=("${REPLY_LIST[@]}")
    local events=("${!_fsm_eventset[@]}")
    pytext_sorted events;                    _fsm_events=("${REPLY_LIST[@]}")
    fsm_machine_reset "$self"
}

fsm_machine_from_string() {
    #  RETURN: 0, the machine '$1' is the model the text '$2' states;
    #          1, else -- FSM_ERROR names the line.
    #
    #  One statement per line; '#' starts a comment:
    #      initial: A              where the machine starts; default: the
    #                              first state the text names
    #      forbidden: X, Y         states the system must never enter
    #      final: A, B             states it may end in
    #      state A                 a state, transitions or not
    #      A ---( ev )---> B ---( ev2 )---> C
    #                              transitions, chained
    #      :  ---( ev )---> D      ':' is the state that began the line above
    #  Options as for 'fsm_machine_new': 'dfa=0', 'name=', 'write='.
    local self=$1 text=$2; shift 2
    local -A _fsm_option=([dfa]=1)
    _fsm_options "$@"
    local -a triple_list=() state_list=() raw_list
    local -A line_of=() declared_n=()
    local -a declared_initial=() declared_forbidden=() declared_final=()
    local first="" previous_head="" number=0 raw line word rest part head source target event
    mapfile -t raw_list <<< "$text"
    for raw in "${raw_list[@]}"; do
        (( ++number ))
        _fsm_strip "${raw%%#*}"; line=$REPLY
        [[ -z $line ]] && continue
        if [[ $line =~ $_FSM_KEY_RE ]]; then
            word=${BASH_REMATCH[1]} rest=${BASH_REMATCH[2]}
            local -a name_list=() part_list
            IFS=, read -ra part_list <<< "$rest,"
            for part in "${part_list[@]}"; do
                _fsm_strip "$part"; [[ -z $REPLY ]] && continue
                _fsm_name_of "$part" $number || return 1
                name_list+=("$REPLY")
            done
            if [[ $word == initial ]] && (( ${#name_list[@]} != 1 )); then
                FSM_ERROR="line $number: 'initial:' names one state"
                return 1
            fi
            local -n _fsm_declared=declared_$word
            _fsm_declared+=("${name_list[@]}")
            declared_n[$word]=1
            continue
        fi
        #  THE ARROWS: [state, event, state, event, state ...].
        local -a piece_list=()
        rest=$line
        while [[ $rest =~ $_FSM_ARROW_RE ]]; do
            piece_list+=("${rest%%"${BASH_REMATCH[0]}"*}" "${BASH_REMATCH[1]}")
            rest=${rest#*"${BASH_REMATCH[0]}"}
        done
        piece_list+=("$rest")
        if (( ${#piece_list[@]} == 1 )); then
            _fsm_name_of "$line" $number || return 1
            head=$REPLY
            first=${first:-$head}
            state_list+=("$head")
            previous_head=$head
            continue
        fi
        local i
        for (( i = 1; i < ${#piece_list[@]}; i += 2 )); do
            _fsm_strip "${piece_list[i]}"
            if [[ -z $REPLY ]]; then
                FSM_ERROR="line $number: an arrow names no event -- '---( event )--->'"
                return 1
            fi
        done
        _fsm_strip "${piece_list[0]}"
        if [[ $REPLY == : ]]; then
            if [[ -z $previous_head ]]; then
                FSM_ERROR="line $number: ':' stands for the state of the line above, and none stands there"
                return 1
            fi
            head=$previous_head
        else
            _fsm_name_of "${piece_list[0]}" $number || return 1
            head=$REPLY
        fi
        first=${first:-$head}; previous_head=$head
        source=$head
        for (( i = 1; i < ${#piece_list[@]}; i += 2 )); do
            _fsm_name_of "${piece_list[i+1]}" $number || return 1
            target=$REPLY
            _fsm_strip "${piece_list[i]}"; event=$REPLY
            local key=$source$FSM_SEP$event
            #  THE DFA'S CONFLICT NAMED WHERE IT STANDS: both lines.
            if (( _fsm_option[dfa] )) && [[ -n ${line_of[$key]+x} && ${line_of[$key]%% *} != "$target" ]]; then
                FSM_ERROR="line $number: '$source' --($event)--> '$target', and line ${line_of[$key]#* }: --> '${line_of[$key]%% *}' -- a DFA moves one way per event, or 'DFA=False'"
                return 1
            fi
            [[ -n ${line_of[$key]+x} ]] || line_of[$key]="$target $number"
            triple_list+=("$source$FSM_SEP$event$FSM_SEP$target")
            source=$target
        done
    done
    if [[ -z $first && -z ${declared_n[initial]+x} ]]; then
        FSM_ERROR="the model names no state"
        return 1
    fi
    local initial=${declared_initial[0]:-$first}
    fsm_machine_new "$self" "$@" initial="$initial" transitions=triple_list \
                    states="${state_list[*]}" forbidden="${declared_forbidden[*]}" \
                    final="${declared_final[*]}"
}

fsm_machine_to_string() {
    #  RETURN: 0, REPLY = the model in the text 'from_string' reads, one
    #             transition per line, sorted.
    local -n _fsm_self=$1 _fsm_edge=$1_edge _fsm_states=$1_states
    local lines=("initial: ${_fsm_self[initial]}") key source event target state
    local -A named=([${_fsm_self[initial]}]=1)
    [[ -n ${_fsm_self[model_forbidden]} ]] && { _fsm_joined ", " ${_fsm_self[model_forbidden]}; lines+=("forbidden: $REPLY"); }
    [[ -n ${_fsm_self[final]} ]]           && { _fsm_joined ", " ${_fsm_self[final]};           lines+=("final: $REPLY"); }
    local keys=("${!_fsm_edge[@]}")
    pytext_sorted keys
    for key in "${REPLY_LIST[@]}"; do
        source=${key%%"$FSM_SEP"*} event=${key#*"$FSM_SEP"}
        for target in ${_fsm_edge[$key]}; do
            lines+=("$source ---( $event )---> $target")
            named[$source]=1; named[$target]=1
        done
    done
    for state in "${_fsm_states[@]}"; do
        [[ -n ${named[$state]+x} || " ${_fsm_self[model_forbidden]} " == *" $state "* ]] && continue
        lines+=("state $state")
    done
    printf -v REPLY '%s\n' "${lines[@]}"
    REPLY=${REPLY%$'\n'}
}

# ---------------------------------------------------------------- running
fsm_machine_reset() {
    #  RETURN: 0; the machine '$1' stands in its initial state again, under
    #          the model as written: what was seen is forgotten, and so is
    #          every mask and every state forbidden or permitted since.
    local self=$1
    declare -gA "${self}_mask" "${self}_forbid" "${self}_permit" "${self}_visit" "${self}_taken"
    declare -ga "${self}_trace"
    local -n _fsm_self=$self _fsm_forbid=${self}_forbid _fsm_visit=${self}_visit
    local -n _fsm_mask=${self}_mask _fsm_permit=${self}_permit _fsm_taken=${self}_taken _fsm_trace=${self}_trace
    _fsm_mask=(); _fsm_forbid=(); _fsm_permit=(); _fsm_taken=(); _fsm_trace=()
    local state
    for state in ${_fsm_self[model_forbidden]}; do _fsm_forbid[$state]=""; done
    _fsm_self[current]=${_fsm_self[initial]}
    _fsm_visit=([${_fsm_self[initial]}]=1)
    _fsm_self[breach_n]=0
}

_fsm_masked_f() {
    #  RETURN: 0, the event '$3' is disallowed in state '$2' of machine '$1'
    #             now -- in every state, or in that one; 1, else.
    local -n _fsm_mask=$1_mask
    [[ -n ${_fsm_mask[$FSM_SEP$3]+x} || -n ${_fsm_mask[$2$FSM_SEP$3]+x} ]]
}

_fsm_write() {
    #  RETURN: 0; the line '$2' went through machine '$1's 'write'.
    local -n _fsm_self=$1
    "${_fsm_self[write]}" "$2"
}

_fsm_here() {
    #  RETURN: 0, REPLY = where machine '$1' stands: "'idle'", or
    #             "{'a', 'b'}" for a set.
    local -n _fsm_self=$1
    local current=(${_fsm_self[current]})
    _fsm_quoted_joined "${current[@]}"
    (( ${#current[@]} == 1 )) || REPLY="{$REPLY}"
}

fsm_machine_fire() {
    #  RETURN: 0, the event '$2' moved machine '$1' (and entered no
    #             forbidden state);
    #          1, it was not allowed where the machine stands -- a BREACH
    #             line is written and the machine stays -- or it entered a
    #             forbidden state, which is written too.
    #  '$3' is the place the breach line names.
    local self=$1 event=$2 where=${3-} state target hint
    local -n _fsm_self=$1 _fsm_edge=$1_edge _fsm_taken=$1_taken _fsm_trace=$1_trace
    local -n _fsm_visit=$1_visit _fsm_forbid=$1_forbid _fsm_mask=$1_mask _fsm_eventset=$1_eventset
    local -A moved=()
    local masked=()
    for state in ${_fsm_self[current]}; do
        local key=$state$FSM_SEP$event
        if _fsm_masked_f "$self" "$state" "$event"; then
            [[ -n ${_fsm_edge[$key]+x} ]] && masked+=("$state")
            continue
        fi
        for target in ${_fsm_edge[$key]-}; do
            moved[$target]=1
            local edge=$key$FSM_SEP$target
            _fsm_taken[$edge]=$(( ${_fsm_taken[$edge]:-0} + 1 ))
            _fsm_trace+=("$where$FSM_SEP$state$FSM_SEP$event$FSM_SEP$target")
        done
    done
    if (( ${#moved[@]} == 0 )); then
        (( ++_fsm_self[breach_n] ))
        fsm_machine_allowed "$self"
        if (( ${#REPLY_LIST[@]} )); then _fsm_joined ", " "${REPLY_LIST[@]}"; hint="allowed: $REPLY"
        else                              hint="no event leaves it"
        fi
        if [[ -z ${_fsm_eventset[$event]+x} ]]; then
            hint="an event the model never names"
        elif (( ${#masked[@]} )); then
            local since=${_fsm_mask[${masked[0]}$FSM_SEP$event]-${_fsm_mask[$FSM_SEP$event]-}}
            _fsm_since_text "$since"; hint="disallowed$REPLY"
        fi
        _fsm_where_text "$where"; local where_text=$REPLY
        _fsm_here "$self"
        _fsm_write "$self" "BREACH$where_text: '$event' in $REPLY -- $hint"
        return 1
    fi
    pytext_sorted_words "${!moved[@]}"
    _fsm_self[current]="${REPLY_LIST[*]}"
    local entered=()
    for state in "${REPLY_LIST[@]}"; do
        _fsm_visit[$state]=$(( ${_fsm_visit[$state]:-0} + 1 ))
        [[ -n ${_fsm_forbid[$state]+x} ]] && entered+=("$state")
    done
    _fsm_where_text "$where"; local where_text=$REPLY
    for state in "${entered[@]}"; do
        (( ++_fsm_self[breach_n] ))
        if [[ " ${_fsm_self[model_forbidden]} " == *" $state "* && -z ${_fsm_forbid[$state]} ]]; then
            hint="a forbidden state"
        else
            _fsm_since_text "${_fsm_forbid[$state]}"; hint="forbidden$REPLY"
        fi
        _fsm_write "$self" "BREACH$where_text: '$state' entered by '$event' -- $hint"
    done
    (( ${#entered[@]} == 0 ))
}

# ------------------------------------------------------ the law, changing
fsm_machine_forbidden() {
    #  RETURN: 0, REPLY_LIST = the states forbidden NOW, sorted -- the
    #             model's, less those permitted, with those forbidden since.
    local -n _fsm_forbid=$1_forbid
    pytext_sorted_words "${!_fsm_forbid[@]}"
}

_fsm_known() {
    #  RETURN: 0, the event '$2' and the state '$3' (each where not empty)
    #             are named by machine '$1's model;
    #          1, else -- FSM_ERROR names what is not.
    local -n _fsm_eventset=$1_eventset _fsm_events=$1_events _fsm_states=$1_states
    if [[ -n $2 && -z ${_fsm_eventset[$2]+x} ]]; then
        _fsm_joined ", " "${_fsm_events[@]}"
        FSM_ERROR="'$2': an event the model never names -- events: $REPLY"
        return 1
    fi
    if [[ -n $3 && " ${_fsm_states[*]} " != *" $3 "* ]]; then
        _fsm_joined ", " "${_fsm_states[@]}"
        FSM_ERROR="'$3': a state the model never names -- states: $REPLY"
        return 1
    fi
}

fsm_machine_disallow() {
    #  RETURN: 0; from now on the event '$2' is a breach -- in state '$3'
    #             alone, or in every state where '$3' is empty -- until
    #             'allow' lifts it; the breach line says 'disallowed since
    #             <'$4'>';
    #          1, the model names no such event or state (FSM_ERROR).
    _fsm_known "$1" "$2" "${3-}" || return 1
    local -n _fsm_mask=$1_mask
    local key=${3-}$FSM_SEP$2
    [[ -n ${_fsm_mask[$key]+x} ]] || _fsm_mask[$key]=${4-}
}

fsm_machine_allow() {
    #  RETURN: 0; the mask 'disallow' set for event '$2' in state '$3' (''
    #             for every state) is lifted; a mask of another scope stays;
    #          1, the model names no such event or state (FSM_ERROR).
    _fsm_known "$1" "$2" "${3-}" || return 1
    local -n _fsm_mask=$1_mask
    unset "_fsm_mask[${3-}$FSM_SEP$2]"
}

fsm_machine_forbid() {
    #  RETURN: 0; from now on entering state '$2' is a breach, until
    #             'permit'. Where the machine STANDS in it, one BREACH line
    #             is written at once, naming '$3';
    #          1, the model names no such state (FSM_ERROR).
    _fsm_known "$1" "" "$2" || return 1
    local -n _fsm_self=$1 _fsm_forbid=$1_forbid _fsm_permit=$1_permit
    [[ -n ${_fsm_forbid[$2]+x} ]] && return 0
    _fsm_forbid[$2]=${3-}
    unset "_fsm_permit[$2]"
    if [[ " ${_fsm_self[current]} " == *" $2 "* ]]; then
        (( ++_fsm_self[breach_n] ))
        _fsm_where_text "${3-}"; local where_text=$REPLY
        _fsm_since_text "${3-}"
        _fsm_write "$1" "BREACH$where_text: stands in '$2' -- forbidden$REPLY"
    fi
}

fsm_machine_permit() {
    #  RETURN: 0; state '$2' is no longer forbidden -- a state of the
    #             model's own 'forbidden:' too, until 'forbid' again;
    #          1, the model names no such state (FSM_ERROR).
    _fsm_known "$1" "" "$2" || return 1
    local -n _fsm_self=$1 _fsm_forbid=$1_forbid _fsm_permit=$1_permit
    [[ -n ${_fsm_forbid[$2]+x} ]] || return 0
    unset "_fsm_forbid[$2]"
    [[ " ${_fsm_self[model_forbidden]} " == *" $2 "* ]] && _fsm_permit[$2]=${3-}
    return 0
}

fsm_machine_disallowed() {
    #  RETURN: the status of the command '$5...', run with the event '$2'
    #          disallowed in state '$3' since '$4' (see 'disallow'), allowed
    #          again after it -- Python's 'with m.disallowed(...)'.
    local self=$1 event=$2 state=$3 where=$4 status; shift 4
    fsm_machine_disallow "$self" "$event" "$state" "$where" || return 1
    "$@"; status=$?
    fsm_machine_allow "$self" "$event" "$state"
    return $status
}

fsm_machine_forbidding() {
    #  RETURN: the status of the command '$4...', run with state '$2'
    #          forbidden since '$3' (see 'forbid'), permitted again after it.
    local self=$1 state=$2 where=$3 status; shift 3
    fsm_machine_forbid "$self" "$state" "$where" || return 1
    "$@"; status=$?
    fsm_machine_permit "$self" "$state"
    return $status
}

# --------------------------------------------------------------- questions
fsm_machine_state() {
    #  RETURN: 0, REPLY = the one state machine '$1' stands in;
    #          1, a set of states stands (dfa=0): ask 'current' (FSM_ERROR).
    local -n _fsm_self=$1
    local current=(${_fsm_self[current]})
    if (( ${#current[@]} != 1 )); then
        _fsm_here "$1"
        FSM_ERROR="the machine stands in $REPLY: ask 'current()'"
        return 1
    fi
    REPLY=${current[0]}
}

fsm_machine_current() {
    #  RETURN: 0, REPLY_LIST = every state machine '$1' stands in, sorted.
    local -n _fsm_self=$1
    REPLY_LIST=(${_fsm_self[current]})
}

fsm_machine_in_state() {
    #  RETURN: 0, machine '$1' stands in state '$2'; 1, else.
    local -n _fsm_self=$1
    [[ " ${_fsm_self[current]} " == *" $2 "* ]]
}

fsm_machine_can() {
    #  RETURN: 0, the event '$2' would move machine '$1' now; 1, else.
    local -n _fsm_self=$1 _fsm_edge=$1_edge
    local state
    for state in ${_fsm_self[current]}; do
        [[ -n ${_fsm_edge[$state$FSM_SEP$2]+x} ]] && ! _fsm_masked_f "$1" "$state" "$2" && return 0
    done
    return 1
}

fsm_machine_allowed() {
    #  RETURN: 0, REPLY_LIST = the events that would move machine '$1' now,
    #             sorted.
    local -n _fsm_self=$1 _fsm_edge=$1_edge
    local -A found=()
    local key state event
    for key in "${!_fsm_edge[@]}"; do
        state=${key%%"$FSM_SEP"*} event=${key#*"$FSM_SEP"}
        [[ " ${_fsm_self[current]} " == *" $state "* ]] || continue
        _fsm_masked_f "$1" "$state" "$event" && continue
        found[$event]=1
    done
    local events=("${!found[@]}")
    pytext_sorted events
}

fsm_machine_trace() {
    #  RETURN: 0, REPLY_LIST = every transition fired, in order, each
    #             'where${FSM_SEP}state${FSM_SEP}event${FSM_SEP}state'.
    local -n _fsm_trace=$1_trace
    REPLY_LIST=("${_fsm_trace[@]}")
}

# -------------------------------------------------------- the model alone
_fsm_successors() {
    #  RETURN: 0; the associative array '_fsm_successor' (declared by the
    #          caller) maps each state of machine '$1' to the sorted
    #          'event${FSM_SEP}target' pairs leaving it -- under the masks
    #          where '$2' is 1, as written else.
    local -n _fsm_edge=$1_edge
    local key source event target
    local -A pairs=()
    for key in "${!_fsm_edge[@]}"; do
        source=${key%%"$FSM_SEP"*} event=${key#*"$FSM_SEP"}
        (( $2 )) && _fsm_masked_f "$1" "$source" "$event" && continue
        for target in ${_fsm_edge[$key]}; do
            pairs[$source]+="$event$FSM_SEP$target"$'\n'
        done
    done
    for source in "${!pairs[@]}"; do
        local list
        mapfile -t list <<< "${pairs[$source]%$'\n'}"
        pytext_sorted list
        printf -v _fsm_successor[$source] '%s\n' "${REPLY_LIST[@]}"
    done
}

fsm_machine_path_to() {
    #  RETURN: 0, REPLY_LIST = the shortest sequence of events from the start
    #             -- the initial state, 'start=now' for where the machine
    #             stands, 'start=<state>' -- into state '$2' (empty where
    #             the start is that state); among equally short paths, the
    #             one first in event order;
    #          1, '$2' cannot be reached from there (Python's None).
    #  Under the masks standing now; 'masked=0' asks the model as written.
    local self=$1 goal=$2; shift 2
    local -n _fsm_self=$self
    local -A _fsm_option=([start]="" [masked]=1)
    _fsm_options "$@"
    local -a start_list
    case ${_fsm_option[start]} in
        now) start_list=(${_fsm_self[current]}) ;;
        "")  start_list=("${_fsm_self[initial]}") ;;
        *)   start_list=("${_fsm_option[start]}") ;;
    esac
    REPLY_LIST=()
    [[ " ${start_list[*]} " == *" $goal "* ]] && return 0
    local -A _fsm_successor=() seen=()
    _fsm_successors "$self" "${_fsm_option[masked]}"
    pytext_sorted start_list
    local -a queue_state=() queue_path=()
    local state pair event target here path head=0
    for state in "${REPLY_LIST[@]}"; do queue_state+=("$state"); queue_path+=(""); seen[$state]=1; done
    while (( head < ${#queue_state[@]} )); do
        here=${queue_state[head]} path=${queue_path[head]}
        (( ++head ))
        local pairs
        mapfile -t pairs <<< "${_fsm_successor[$here]-}"
        for pair in "${pairs[@]}"; do
            [[ -z $pair ]] && continue
            event=${pair%%"$FSM_SEP"*} target=${pair#*"$FSM_SEP"}
            [[ -n ${seen[$target]+x} ]] && continue
            if [[ $target == "$goal" ]]; then
                path+="$event$FSM_SEP"
                IFS=$FSM_SEP read -ra REPLY_LIST <<< "${path%"$FSM_SEP"}"
                return 0
            fi
            seen[$target]=1
            queue_state+=("$target"); queue_path+=("$path$event$FSM_SEP")
        done
    done
    REPLY_LIST=()
    return 1
}

fsm_machine_state_reachable() {
    #  RETURN: 0, state '$2' can be reached (see 'path_to'; options
    #             'start=', 'masked='); 1, else.
    fsm_machine_path_to "$@"
}

_fsm_forbidden_of() {
    #  RETURN: 0, REPLY = the states forbidden now where '$2' is 1, the
    #             model's own else -- blank-separated.
    local -n _fsm_self=$1
    if (( $2 )); then fsm_machine_forbidden "$1"; REPLY="${REPLY_LIST[*]}"
    else              REPLY=${_fsm_self[model_forbidden]}
    fi
}

fsm_machine_unreachable() {
    #  RETURN: 0, REPLY_LIST = the states no path from the initial state
    #             reaches, forbidden ones left out -- sorted; under the masks
    #             unless 'masked=0'.
    local self=$1; shift
    local -A _fsm_option=([masked]=1)
    _fsm_options "$@"
    local -n _fsm_states=${self}_states
    _fsm_forbidden_of "$self" "${_fsm_option[masked]}"
    local forbidden=" $REPLY " state result=()
    for state in "${_fsm_states[@]}"; do
        [[ $forbidden == *" $state "* ]] && continue
        fsm_machine_path_to "$self" "$state" masked="${_fsm_option[masked]}" || result+=("$state")
    done
    REPLY_LIST=("${result[@]}")
}

fsm_machine_dead_ends() {
    #  RETURN: 0, REPLY_LIST = the states no event leaves that are neither
    #             final nor forbidden -- sorted; under the masks unless
    #             'masked=0' (a mask can make one).
    local self=$1; shift
    local -A _fsm_option=([masked]=1) _fsm_successor=()
    _fsm_options "$@"
    local -n _fsm_self=$self _fsm_states=${self}_states
    _fsm_successors "$self" "${_fsm_option[masked]}"
    _fsm_forbidden_of "$self" "${_fsm_option[masked]}"
    local forbidden=" $REPLY " state result=()
    for state in "${_fsm_states[@]}"; do
        [[ -n ${_fsm_successor[$state]+x} || " ${_fsm_self[final]} " == *" $state "* || $forbidden == *" $state "* ]] && continue
        result+=("$state")
    done
    REPLY_LIST=("${result[@]}")
}

fsm_machine_forbidden_reachable() {
    #  RETURN: 0, REPLY_LIST = the forbidden states the model lets the
    #             system reach from the initial state -- sorted; under the
    #             masks and the states forbidden now unless 'masked=0'.
    local self=$1; shift
    local -A _fsm_option=([masked]=1)
    _fsm_options "$@"
    _fsm_forbidden_of "$self" "${_fsm_option[masked]}"
    local state result=()
    for state in $REPLY; do
        fsm_machine_path_to "$self" "$state" masked="${_fsm_option[masked]}" && result+=("$state")
    done
    REPLY_LIST=("${result[@]}")
}

fsm_machine_check() {
    #  RETURN: 0, REPLY = how many findings the MODEL of machine '$1' has,
    #             each written as one line 'MODEL: ...' -- states no path
    #             reaches, dead ends, forbidden states the model allows to
    #             be reached (with the shortest way there); under the masks
    #             unless 'masked=0'.
    local self=$1; shift
    local -A _fsm_option=([masked]=1)
    _fsm_options "$@"
    local masked=${_fsm_option[masked]} state lines=()
    fsm_machine_unreachable "$self" masked=$masked
    for state in "${REPLY_LIST[@]}"; do lines+=("MODEL: '$state' cannot be reached"); done
    fsm_machine_dead_ends "$self" masked=$masked
    for state in "${REPLY_LIST[@]}"; do lines+=("MODEL: '$state' is a dead end -- no event leaves it"); done
    fsm_machine_forbidden_reachable "$self" masked=$masked
    local reachable=("${REPLY_LIST[@]}")
    for state in "${reachable[@]}"; do
        fsm_machine_path_to "$self" "$state" masked=$masked
        lines+=("MODEL: forbidden '$state' is reachable: ${REPLY_LIST[*]}")
    done
    local line
    for line in "${lines[@]}"; do _fsm_write "$self" "$line"; done
    REPLY=${#lines[@]}
}

# ----------------------------------------------------------------- the end
fsm_machine_report() {
    #  RETURN: 0, REPLY = the breaches seen, counting a non-final end;
    #             written before it, sorted, what the events covered of the
    #             model -- states counted without the forbidden ones:
    #                 fsm: 3 of 3 states visited, 3 of 4 transitions taken, 1 breach
    #                   taken      idle ---( request )---> waiting   x2
    #                   not taken  busy ---( fault )---> crashed
    #                   never in   ...
    #                   ended in   'idle'
    #             A machine with final states that ends elsewhere adds a
    #             BREACH line.
    local self=$1
    local -n _fsm_self=$1 _fsm_edge=$1_edge _fsm_taken=$1_taken _fsm_visit=$1_visit
    local -n _fsm_states=$1_states _fsm_mask=$1_mask _fsm_forbid=$1_forbid _fsm_permit=$1_permit
    local key target edges=() state
    for key in "${!_fsm_edge[@]}"; do
        for target in ${_fsm_edge[$key]}; do edges+=("$key$FSM_SEP$target"); done
    done
    pytext_sorted edges; edges=("${REPLY_LIST[@]}")
    local breach_n=${_fsm_self[breach_n]} end_f=1
    if [[ -n ${_fsm_self[final]} ]]; then
        end_f=0
        for state in ${_fsm_self[current]}; do
            [[ " ${_fsm_self[final]} " == *" $state "* ]] && end_f=1
        done
    fi
    (( end_f )) || (( ++breach_n ))
    #  A FORBIDDEN STATE IS NO GOAL OF COVERAGE: counted out.
    local goal_n=0 visited_n=0 forbidden=" ${_fsm_self[model_forbidden]} "
    for state in "${_fsm_states[@]}"; do
        [[ $forbidden == *" $state "* ]] && continue
        (( ++goal_n ))
        [[ -n ${_fsm_visit[$state]+x} ]] && (( ++visited_n ))
    done
    local plural=es; (( breach_n == 1 )) && plural=""
    _fsm_write "$self" "${_fsm_self[name]}: $visited_n of $goal_n states visited, ${#_fsm_taken[@]} of ${#edges[@]} transitions taken, $breach_n breach$plural"
    local edge source event n label times
    for edge in "${edges[@]}"; do
        IFS=$FSM_SEP read -r source event target <<< "$edge"
        n=${_fsm_taken[$edge]:-0}
        if (( n )); then label="taken    "; else label="not taken"; fi
        times=""; (( n > 1 )) && times="   x$n"
        _fsm_write "$self" "  $label  $source ---( $event )---> $target$times"
    done
    for state in "${_fsm_states[@]}"; do
        [[ -n ${_fsm_visit[$state]+x} || $forbidden == *" $state "* ]] && continue
        _fsm_write "$self" "  never in   '$state'"
    done
    _fsm_here "$self"
    local here=$REPLY
    _fsm_write "$self" "  ended in   $here"
    #  A PHASE NEVER LIFTED IS SAID: what still stands at the end.
    local masks=()
    for key in "${!_fsm_mask[@]}"; do masks+=("${key#*"$FSM_SEP"}$FSM_SEP${key%%"$FSM_SEP"*}"); done
    pytext_sorted masks
    for key in "${REPLY_LIST[@]}"; do
        event=${key%%"$FSM_SEP"*} state=${key#*"$FSM_SEP"}
        _fsm_since_text "${_fsm_mask[$state$FSM_SEP$event]}"
        if [[ -z $state ]]; then _fsm_write "$self" "  disallowed '$event' in every state$REPLY"
        else                     _fsm_write "$self" "  disallowed '$event' in '$state'$REPLY"
        fi
    done
    fsm_machine_forbidden "$self"
    for state in "${REPLY_LIST[@]}"; do
        [[ $forbidden == *" $state "* ]] && continue
        _fsm_since_text "${_fsm_forbid[$state]}"
        _fsm_write "$self" "  forbidden  '$state'$REPLY"
    done
    pytext_sorted_words "${!_fsm_permit[@]}"
    for state in "${REPLY_LIST[@]}"; do
        _fsm_since_text "${_fsm_permit[$state]}"
        _fsm_write "$self" "  permitted  '$state'$REPLY"
    done
    if (( ! end_f )); then
        _fsm_joined ", " ${_fsm_self[final]}
        _fsm_write "$self" "BREACH: ended in $here -- final: $REPLY"
    fi
    REPLY=$breach_n
}
