# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# PURPOSE: A DETERMINISTIC EVENT DISPATCHER -- the port of
#          'python/deterministic_timeline.py'. Triggers fire at the ticks
#          their timeline strings mark with a digit; within one tick the
#          LOWER digit fires first, equal digits in registration order:
#
#              Trigger A: "1  12 1"
#              Trigger B: " 1  1 2"
#
#          When the last tick has passed, every trigger is told
#          'on_termination(end_tick)', 'end_tick' being the LONGEST
#          timeline's length. 'stop' leaves early and still announces; a
#          CANCELLED task announces nothing.
#
# A TRIGGER OF ONE'S OWN is a CLASS: a name whose functions are its methods.
#
#     MyTrigger_fire()           { echo "[$2] ${T[name]} fired"; }   # $1: self
#     MyTrigger_on_termination() { ...; }                            # optional
#     dt_trigger_new a MyTrigger "1 1 3" SUB
#     dt_dispatcher_new d a b c
#     dt_dispatcher_run d
#
# 'self' is the trigger's associative array, by name ('local -n self=$1');
# a class adds its own fields to it. A class without '_fire' is ABSTRACT:
# the run ends there with DT_NOT_IMPLEMENTED -- Python's
# NotImplementedError. Without '_on_termination' the end says nothing.
#
# THE YIELD WITHOUT COROUTINES: a TASK is a step function, one 'dt_task_step'
# runs up to the next yield. 'dt_task_gather' steps tasks in turn, in the
# order given -- the order 'asyncio.gather' gives them -- until each is done.
#______________________________________________________________________________
[[ -n ${_HWUT_DETERMINISTIC_TIMELINE_SH:-} ]] && return 0
_HWUT_DETERMINISTIC_TIMELINE_SH=1

DT_OK=0
DT_NOT_IMPLEMENTED=1
DT_CANCELLED=2

dt_trigger_new() {
    #  RETURN: 0, the global associative array named '$1' is a trigger of
    #             the class '$2' ('' for the base), with timeline '$3' and
    #             name '$4' -- where none is given, 'trigger-<$1>'.
    declare -gA "$1"
    local -n _dt_self=$1
    _dt_self=([class]=$2 [timeline]=$3 [name]=${4:-trigger-$1})
}

dt_trigger_fire() {
    #  RETURN: DT_OK, the trigger '$1' did what it does at tick '$2';
    #          DT_NOT_IMPLEMENTED, its class says nothing it does (abstract).
    local -n _dt_self=$1
    local method=${_dt_self[class]}_fire
    declare -F "$method" >/dev/null || return $DT_NOT_IMPLEMENTED
    "$method" "$1" "$2"
    return $DT_OK
}

dt_trigger_on_termination() {
    #  RETURN: 0; the trigger '$1' was told the timeline passed at tick '$2'
    #          -- silently where its class does not override.
    local -n _dt_self=$1
    local method=${_dt_self[class]}_on_termination
    declare -F "$method" >/dev/null && "$method" "$1" "$2"
    return 0
}

# ------------------------------------------------------------------ the task
dt_task_new() {
    #  RETURN: 0, the global associative array named '$1' is a task: the
    #             step function '$2' (called with the task's name; status 0:
    #             it yielded, more to come; 1: done) over the context '$3'.
    declare -gA "$1"
    local -n _dt_task=$1
    _dt_task=([step]=$2 [context]=$3 [done_f]=0 [cancelled_f]=0 [error]=$DT_OK)
}

dt_task_step() {
    #  RETURN: 0, the task '$1' yielded and goes on; 1, it is done or
    #             cancelled.
    local -n _dt_task=$1
    (( _dt_task[done_f] )) && return 1
    "${_dt_task[step]}" "$1" || _dt_task[done_f]=1
    (( ! _dt_task[done_f] ))
}

dt_task_cancel() {
    #  RETURN: 0; the task '$1' is abandoned: never stepped again, and what
    #          it would have done at its end is not done.
    local -n _dt_task=$1
    _dt_task[done_f]=1
    _dt_task[cancelled_f]=1
}

dt_task_await() {
    #  RETURN: the task '$1's end, once done: DT_OK, DT_CANCELLED where it
    #          was cancelled (Python's CancelledError), or its own error.
    while dt_task_step "$1"; do :; done
    local -n _dt_task=$1
    (( _dt_task[cancelled_f] )) && return $DT_CANCELLED
    return "${_dt_task[error]}"
}

dt_task_gather() {
    #  RETURN: 0, once every task '$@' is done -- stepped in turn, in the
    #             order given, each up to its next yield.
    local live_f=1 task
    while (( live_f )); do
        live_f=0
        for task; do
            local -n _dt_task=$task
            (( _dt_task[done_f] )) && continue
            dt_task_step "$task"
            live_f=1
        done
    done
}

# ------------------------------------------------------------ the dispatcher
dt_dispatcher_new() {
    #  RETURN: 0, the global associative array named '$1' is a dispatcher
    #             over the triggers '$2...', its schedule built: per tick the
    #             triggers due there, the lower digit first, registration
    #             order between equal digits (an insertion sort, stable).
    declare -gA "$1"
    local -n _dt_self=$1
    local self=$1; shift
    local end_tick=0 trigger t j priority line
    for trigger; do
        local -n _dt_trigger=$trigger
        (( ${#_dt_trigger[timeline]} > end_tick )) && end_tick=${#_dt_trigger[timeline]}
    done
    _dt_self=([triggers]="$*" [end_tick]=$end_tick [running_f]=1 [tick]=0 [i]=0)
    for (( t = 0; t < end_tick; ++t )); do
        local -a due=() due_priority=()
        for trigger; do
            local -n _dt_trigger=$trigger
            line=${_dt_trigger[timeline]}
            [[ ${line:t:1} == [0-9] ]] || continue
            priority=${line:t:1}
            j=${#due[@]}
            while (( j > 0 && due_priority[j-1] > priority )); do
                due[j]=${due[j-1]}; due_priority[j]=${due_priority[j-1]}; (( --j ))
            done
            due[j]=$trigger; due_priority[j]=$priority
        done
        _dt_self[due_$t]="${due[*]}"
        _dt_self[priority_$t]="${due_priority[*]}"
    done
}

dt_dispatcher_stop() {
    #  RETURN: 0; the run of dispatcher '$1' leaves at the next firing and
    #          still announces.
    local -n _dt_self=$1
    _dt_self[running_f]=0
}

_dt_dispatcher_step() {
    #  RETURN: 0 after one firing (the yield); 1 once the timeline passed and
    #          every trigger was told -- or a trigger had nothing to do
    #          (the task's 'error' then DT_NOT_IMPLEMENTED).
    local -n _dt_task=$1
    local -n _dt_self=${_dt_task[context]}
    local -a due
    local trigger
    while (( _dt_self[running_f] && _dt_self[tick] < _dt_self[end_tick] )); do
        read -ra due <<< "${_dt_self[due_${_dt_self[tick]}]}"
        if (( _dt_self[i] < ${#due[@]} )); then
            trigger=${due[_dt_self[i]]}
            (( ++_dt_self[i] ))
            if ! dt_trigger_fire "$trigger" "${_dt_self[tick]}"; then
                _dt_task[error]=$DT_NOT_IMPLEMENTED
                return 1
            fi
            return 0
        fi
        (( ++_dt_self[tick] ))
        _dt_self[i]=0
    done
    for trigger in ${_dt_self[triggers]}; do
        dt_trigger_on_termination "$trigger" "${_dt_self[end_tick]}"
    done
    return 1
}

dt_dispatcher_task() {
    #  RETURN: 0; the task named '$2' is the run of dispatcher '$1', ready
    #          to be stepped or gathered.
    local -n _dt_self=$1
    _dt_self[tick]=0
    _dt_self[i]=0
    dt_task_new "$2" _dt_dispatcher_step "$1"
}

dt_dispatcher_run() {
    #  RETURN: DT_OK once the timeline passed and the triggers were told;
    #          DT_NOT_IMPLEMENTED where a trigger said nothing it does.
    dt_dispatcher_task "$1" "_dt_run_of_$1"
    dt_task_await "_dt_run_of_$1"
}

dt_dispatcher_print() {
    #  RETURN: 0; written on stdout: 'TriggerDispatcher', then one line per
    #          firing, '[tick] (priority)name', in the order of the run --
    #          Python's 'repr'.
    local -n _dt_self=$1
    local t k
    local -a due priority
    echo "TriggerDispatcher"
    for (( t = 0; t < _dt_self[end_tick]; ++t )); do
        read -ra due      <<< "${_dt_self[due_$t]}"
        read -ra priority <<< "${_dt_self[priority_$t]}"
        for (( k = 0; k < ${#due[@]}; ++k )); do
            local -n _dt_trigger=${due[k]}
            echo "[$t] (${priority[k]})${_dt_trigger[name]}"
        done
    done
}
