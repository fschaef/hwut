#! /usr/bin/env bash
#
# @hwut {
#     title      = "TriggerDispatcher: schedule, priority, and the end of time"
#     choices {
#         abstract    { features = ["bash-timeline"] }
#         cancel      { features = ["bash-timeline"] }
#         edges       { features = ["bash-timeline"] }
#         priority    { features = ["bash-timeline"] }
#         schedule    { features = ["bash-timeline"] }
#         stable      { features = ["bash-timeline"] }
#         stop        { features = ["bash-timeline"] }
#         termination { features = ["bash-timeline"] }
#         yielding    { features = ["bash-timeline"] }
#     }
#     interactive = true
# }
#
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# PURPOSE: The bash port of 'python/TEST/test-deterministic-timeline.py',
#          choice for choice, held against its GOOD files by '.link'. A
#          trigger class is a function prefix; a coroutine is a step function.
#______________________________________________________________________________
source "$(dirname "$0")/../hwut_runner.sh"
source "$(dirname "$0")/../deterministic_timeline.sh"

banner() { echo; echo "--- $1 ---"; }

# ------------------------------------------------------------ the triggers
SpeakingTrigger_new() {
    #  RETURN: 0; the trigger '$1' named '$2' with timeline '$3' says what
    #          it is asked to do -- silent at the end where '$4' is 1.
    dt_trigger_new "$1" "${5:-SpeakingTrigger}" "$3" "$2"
    local -n self=$1
    self[silent_termination_f]=${4:-0}
    printf 'SETUP: %-7s |%s|\n' "$2" "$3"
}
SpeakingTrigger_fire() {
    local -n self=$1
    echo "  [t:$2] ${self[name]} fires"
}
SpeakingTrigger_on_termination() {
    local -n self=$1
    (( self[silent_termination_f] )) && return
    echo "  [end:$2] ${self[name]} notified"
}

#  MUTE: fires, and does NOT override 'on_termination'.
MuteTrigger_new() {
    dt_trigger_new "$1" MuteTrigger "$3" "$2"
    printf 'SETUP: %-7s |%s|  (no on_termination override)\n' "$2" "$3"
}
MuteTrigger_fire() { SpeakingTrigger_fire "$@"; }

dispatch() {
    #  RETURN: the run's end: a dispatcher over the triggers '$@', run to
    #          completion.
    dt_dispatcher_new d "$@"
    dt_dispatcher_run d
}

run_schedule() {
    banner "staggered: A at 0, B at 2, C at 4"
    SpeakingTrigger_new a A "1    "; SpeakingTrigger_new b B "  1  "; SpeakingTrigger_new c C "    1"
    dispatch a b c

    banner "a SHORT timeline stops contributing; the long one goes on"
    SpeakingTrigger_new s SHORT "11"; SpeakingTrigger_new l LONG "111111"
    dispatch s l

    banner "the SCHEDULE as built -- '[tick] (priority)name'"
    SpeakingTrigger_new a A "12"; SpeakingTrigger_new b B "21"
    dt_dispatcher_new d a b
    dt_dispatcher_print d
}

run_priority() {
    banner "digits swap between ticks: B leads at 0, A leads at 1"
    SpeakingTrigger_new a A "21"; SpeakingTrigger_new b B "12"
    dispatch a b

    banner "0 is the strongest digit, 9 the weakest"
    SpeakingTrigger_new w WEAK "9"; SpeakingTrigger_new s STRONG "0"
    dispatch w s
}

run_stable() {
    banner "three triggers, all digit 1 at tick 0"
    SpeakingTrigger_new a first "1"; SpeakingTrigger_new b second "1"; SpeakingTrigger_new c third "1"
    dispatch a b c

    banner "registered BACKWARDS -- the order follows registration, not the name"
    SpeakingTrigger_new a third "1"; SpeakingTrigger_new b second "1"; SpeakingTrigger_new c first "1"
    dispatch a b c
}

run_termination() {
    banner "end_tick is the LENGTH -- 5 characters, last firing at tick 0"
    SpeakingTrigger_new e EARLY "1    "
    dispatch e

    banner "a trigger that NEVER fires is notified all the same"
    SpeakingTrigger_new f FIRES "1  "; SpeakingTrigger_new s SILENT "   "
    dispatch f s

    banner "the LONGEST timeline sets end_tick for everybody"
    SpeakingTrigger_new s SHORT "1"; SpeakingTrigger_new g LONG "1      "
    dispatch s g

    banner "a trigger that does not override is simply silent at the end"
    SpeakingTrigger_new s SPEAKS "1 "; MuteTrigger_new m MUTE "1 "
    dispatch s m
}

# --------------------------------------------------------------- yielding
ProducingTrigger_fire() {
    local -n self=$1
    self[item]="item@$2"
    echo "  [t:$2] ${self[name]} prepared ${self[item]}"
}
ProducingTrigger_on_termination() {
    local -n self=$1
    self[finished]=1
    echo "  [end:$2] ${self[name]} announced end-of-stream"
}

consume_step() {
    #  RETURN: 0 to wait (the yield); 1 once the end-of-stream was seen.
    local -n task=$1
    local -n the_producer=${task[context]}
    while true; do
        if [[ -z ${the_producer[item]} ]]; then
            if (( the_producer[finished] )); then
                echo "  consumer saw end-of-stream after ${task[taken]:-0} item(s)"
                return 1
            fi
            return 0
        fi
        task[taken]=$(( ${task[taken]:-0} + 1 ))
        echo "        consumer took ${the_producer[item]}"
        the_producer[item]=""
    done
}

run_yielding() {
    banner "producer fires at every tick; consumer waits between them"
    dt_trigger_new producer ProducingTrigger "111" PROD
    producer[item]=""; producer[finished]=0
    printf 'SETUP: %-7s |%s|\n' PROD 111
    dt_dispatcher_new d producer
    dt_dispatcher_task d run
    dt_task_new take consume_step producer
    dt_task_gather run take
    echo
    echo "Each item was taken BEFORE the next tick prepared one: the run yields."
}

# ------------------------------------------------------------ stop, cancel
StoppingTrigger_fire() {
    local -n self=$1
    SpeakingTrigger_fire "$@"
    echo "  ... asks the dispatcher to stop"
    dt_dispatcher_stop "${self[dispatcher]}"
}
StoppingTrigger_on_termination() { SpeakingTrigger_on_termination "$@"; }

run_stop() {
    banner "stop() after the first tick -- ticks 1.. are not walked, the announcement still comes"
    SpeakingTrigger_new stopper STOPPER "1111" 0 StoppingTrigger
    SpeakingTrigger_new bystander OTHER "1111"
    dt_dispatcher_new d stopper bystander
    stopper[dispatcher]=d
    dt_dispatcher_run d
    echo
    echo "end_tick is still the timeline's length, not the tick the run stopped at."
}

run_cancel() {
    banner "cancel() the task carrying run() -- no announcement follows"
    SpeakingTrigger_new a A "1111111111"
    dt_dispatcher_new d a
    dt_dispatcher_task d task
    dt_task_step task                                  # one tick passes
    dt_task_cancel task
    dt_task_await task
    (( $? == DT_CANCELLED )) && echo "  run() was cancelled"
    echo
    echo "No '[end:..]' line above: the triggers were abandoned, not ended."
}

run_edges() {
    banner "an EMPTY timeline -- end_tick 0"
    SpeakingTrigger_new e EMPTY ""
    dispatch e

    banner "a timeline of BLANKS -- no digit, so nothing fires"
    SpeakingTrigger_new b BLANK "    "
    dispatch b

    banner "NO TRIGGERS at all -- nothing to announce, and no failure"
    dispatch
    echo "  (dispatcher ran; nothing was scheduled)"

    banner "a timeline of blanks beside one that fires"
    SpeakingTrigger_new b BLANK "   "; SpeakingTrigger_new f FIRES " 1 "
    dispatch b f
}

run_abstract() {
    banner "the BASE 'fire' is abstract -- it refuses"
    dt_trigger_new bare BareTrigger "1" BARE
    dispatch bare
    (( $? == DT_NOT_IMPLEMENTED )) && echo "  NotImplementedError -- as owed: a trigger must say what it does"

    banner "the BASE 'on_termination' is optional -- it is silent"
    dt_trigger_new bare BareTrigger "" BARE
    dt_trigger_on_termination bare 0
    echo "  returned quietly; nothing raised, nothing printed"

    banner "a NAME given is the name kept"
    dt_trigger_new given "" "1" GIVEN
    echo "  name: ${given[name]}"
}

declare -A choice_map=(
    [schedule]=run_schedule [priority]=run_priority [stable]=run_stable
    [termination]=run_termination [yielding]=run_yielding [stop]=run_stop
    [cancel]=run_cancel [edges]=run_edges [abstract]=run_abstract
)
hwut_runner_new runner "TriggerDispatcher: schedule, priority, and the end of time" choice_map
hwut_runner_run runner "$@"
