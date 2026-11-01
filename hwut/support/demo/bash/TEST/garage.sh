#! /usr/bin/env bash
#
# @hwut {
#     title    = "Demo: a garage's space counter -- a space, a stream and races, generated"
#     interactive = true
#     choices {
#         space       { features = ["space-from-hocon", "space-iterator", "hwut-runner"]
#                       tolerance { constraints = ["mismatches == 0"] } }
#         random      { features = ["deterministic-stream", "hwut-runner"]
#                       tolerance { constraints = ["mismatches == 0"] } }
#         race-naive  { features = ["deterministic-timeline", "space-iterator", "hwut-runner"]
#                       tolerance { constraints = ["overbooked > 0"] } }
#         race-atomic { features = ["deterministic-timeline", "space-iterator", "hwut-runner"]
#                       tolerance { constraints = ["overbooked == 0"] } }
#     }
# }
#
#______________________________________________________________________________
# SUBJECT  the counter of free spaces at a garage's gates: which cars it
#          admits, which it refuses, and how many stand inside.
# REQUIREMENT  The garage admits a car only while a space is free, lets a car
#              out only while one stands inside, and never holds more cars
#              than it has spaces -- also when two gates admit at once.
#
# 'garage.py' of the Python demonstration, in bash, with the bash port of
# hwut's helpers for writing tests (support/test_writing/bash):
#
# space        'garage-space.hocon' read by 'hwut_hocon.sh'; every
#              combination walked by 'space_iterator.sh': 3 x 5 x 4 = 60
#              cases, each a cell of a matrix, checked against the model.
# random       'dr_stream_new s 4711': 1000 cars arriving and leaving at a
#              garage of 5. The stream is Python's, seed for seed: the GOOD
#              is the Python demo's.
# race-naive   two gates, one free space, on timelines drawn as strings
#              ('deterministic_timeline.sh'); all six interleavings of two
#              two-step gates in four ticks. Where both check before either
#              admits, both admit: 'overbooked > 0' -- the GOOD is the
#              accepted violation report.
# race-atomic  the same six, checking and admitting in ONE step.
#              'overbooked == 0'.
#
# THE FRONT END is 'hwut_runner.sh': the choice map below is the whole
# command line, '--hwut-info' included; 'interactive = true' starts the
# application once and asks for the choices one after another.
#______________________________________________________________________________
source "$(dirname "${BASH_SOURCE[0]}")/support.sh"
source hwut_runner.sh
source space_iterator.sh
source hwut_hocon.sh
source deterministic_random.sh
source deterministic_timeline.sh

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

# _____________________________________________________________________________
# the unit under test: a counter of the spaces a garage has -- a global
# associative array, 'capacity' and 'occupied'
#
garage_new() {
    #  RETURN: 0, the global associative array '$1' is an empty garage of
    #             '$2' spaces.
    declare -gA "$1"
    local -n _garage=$1
    _garage=([capacity]=$2 [occupied]=0)
}

garage_free() {
    #  RETURN: 0, REPLY = the number of spaces free now -- negative where the
    #             garage '$1' is overbooked.
    local -n _garage=$1
    REPLY=$(( _garage[capacity] - _garage[occupied] ))
}

garage_arrive() {
    #  RETURN: 0, a car was admitted to garage '$1', if a space was free;
    #          1, else (the car is refused).
    local -n _garage=$1
    (( _garage[capacity] - _garage[occupied] > 0 )) || return 1
    (( ++_garage[occupied] ))
    return 0
}

garage_leave() {
    #  RETURN: 0, a car drove out of garage '$1', if one stood inside;
    #          1, else.
    local -n _garage=$1
    (( _garage[occupied] > 0 )) || return 1
    (( --_garage[occupied] ))
    return 0
}

list_text() {
    #  RETURN: 0, REPLY = the values '$@' as Python prints a list of ints:
    #             '[1, 2, 3]'.
    local IFS=,
    REPLY="[$*]"
    REPLY=${REPLY//,/, }
}

# _____________________________________________________________________________
# space -- the tested space from HOCON, walked by space_iterator
#
read_space() {
    #  RETURN: 0; the dimensions of the space in file '$1', in the order
    #          written: their names in the array 'dimension_name', the values
    #          of the k-th in the array 'dimension_k'. Every fault the HOCON
    #          reader found is printed with '!!' first.
    local text i entry item k=0
    text=$(< "$1")
    hocon_source_lines space_src "$text"
    hocon_parse space_doc space_src "$(basename "$1")"
    for (( i = 0; i < ${#space_doc_fault_message[@]}; ++i )); do
        hocon_fault_text space_doc "$i"; echo "!! $REPLY"
    done
    hocon_get space_doc "${space_doc[root]}" space
    dimension_name=()
    for entry in ${space_doc_children[REPLY]}; do
        dimension_name+=("${space_doc_key[entry]}")
        declare -ga "dimension_$k"
        local -n _dimension=dimension_$k
        _dimension=()
        for item in ${space_doc_children[entry]}; do _dimension+=("${space_doc_value[item]}"); done
        (( ++k ))
    done
}

space() {
    #  RETURN: 0; prints every case of the space as a matrix cell.
    read_space "$HERE/garage-space.hocon"
    local header="" k mismatch_n=0 case_n=0
    for (( k = 0; k < ${#dimension_name[@]}; ++k )); do
        local -n _dimension=dimension_$k
        list_text "${_dimension[@]}"
        header+="${header:+  x  }${dimension_name[k]} $REPLY"
    done
    echo "space: $header"
    echo "cell: cars inside / cars refused at the gate ('!!' differs from the model)"
    local -A row_map=()
    local capacity arriving leaving refused admitted i mark cell
    space_iterator_new cases dimension_0 dimension_1 dimension_2
    while space_iterator_next cases; do
        capacity=${REPLY_LIST[0]} arriving=${REPLY_LIST[1]} leaving=${REPLY_LIST[2]}
        garage_new unit "$capacity"
        refused=0
        for (( i = 0; i < arriving; ++i )); do garage_arrive unit || (( ++refused )); done
        for (( i = 0; i < leaving; ++i )); do garage_leave unit; done
        admitted=$(( arriving < capacity ? arriving : capacity ))
        if (( unit[occupied] == admitted - (leaving < admitted ? leaving : admitted)
              && refused == arriving - admitted )); then mark="  "
        else                                             mark="!!"; (( ++mismatch_n ))
        fi
        printf -v cell '%-9s' "${unit[occupied]}/$refused$mark"
        row_map[$capacity,$arriving]+="${row_map[$capacity,$arriving]:+  }$cell"
        (( ++case_n ))
    done
    local line
    for capacity in "${dimension_0[@]}"; do
        line=""
        for leaving in "${dimension_2[@]}"; do printf -v cell 'leave %-3d' "$leaving"; line+="${line:+  }$cell"; done
        line="capacity $capacity   $line"
        echo "${line%"${line##*[! ]}"}"
        for arriving in "${dimension_1[@]}"; do
            line="  arrive $arriving   ${row_map[$capacity,$arriving]}"
            echo "${line%"${line##*[! ]}"}"
        done
    done
    echo "cases $case_n, differing from the model ((mismatches: $mismatch_n))"
}

# _____________________________________________________________________________
# random -- a deterministic stream of arrivals and departures
#
random_stream() {
    #  RETURN: 0; prints the summary of 1000 drawn cars, model-checked.
    dr_stream_new stream 4711
    garage_new unit 5
    local model=0 i n mismatch_n=0 strip="" bar
    local arrive_n=0 refused_n=0 leave_n=0 empty_n=0
    local -a histogram=(0 0 0 0 0 0)
    for (( i = 0; i < 1000; ++i )); do
        if dr_stream_coin stream 0.55; then
            (( ++arrive_n ))
            garage_arrive unit || (( ++refused_n ))
            model=$(( model + 1 < 5 ? model + 1 : 5 ))
            strip+="+"
        else
            (( ++leave_n ))
            garage_leave unit || (( ++empty_n ))
            model=$(( model - 1 > 0 ? model - 1 : 0 ))
            strip+="-"
        fi
        (( unit[occupied] != model && ++mismatch_n ))
        (( ++histogram[unit[occupied]] ))
    done
    echo "seed 4711, garage of 5, 1000 cars drawn: '+' arrives, '-' leaves"
    echo "first 60: ${strip:0:60}"
    echo "arrivals $arrive_n, refused $refused_n; departures $leave_n, from an empty garage $empty_n"
    echo "cars inside after each event:"
    for (( n = 0; n < 6; ++n )); do
        printf -v bar '%*s' $(( histogram[n] / 10 )) ""
        printf '    %d  %4d  %s\n' "$n" "${histogram[n]}" "${bar// /#}"
    done
    echo "steps differing from the model ((mismatches: $mismatch_n))"
}

# _____________________________________________________________________________
# race -- two gates on drawn timelines
#
Gate_fire() {
    #  RETURN: 0; the gate '$1' performed its next step at tick '$2': its
    #          first checks (and, atomic, admits), its second admits (or
    #          opens).
    local -n _gate=$1
    local -n _gate_log=${_gate[log]}
    local name=${_gate[name]} garage=${_gate[garage]}
    if (( _gate[step] == 0 && _gate[atomic] )); then
        if garage_arrive "$garage"; then _gate[saw_free]=1; _gate_log+=("$name checks+admits")
        else                             _gate[saw_free]=0; _gate_log+=("$name refuses")
        fi
    elif (( _gate[step] == 0 )); then
        garage_free "$garage"
        _gate[saw_free]=$(( REPLY > 0 ))
        _gate_log+=("$name sees $REPLY free")
    elif (( _gate[atomic] )); then
        if (( _gate[saw_free] )); then _gate_log+=("$name opens"); else _gate_log+=("$name stays shut"); fi
    elif (( _gate[saw_free] )); then
        local -n _gate_garage=$garage
        (( ++_gate_garage[occupied] ))                          # the naive admit
        _gate_log+=("$name admits")
    else
        _gate_log+=("$name refuses")
    fi
    (( ++_gate[step] ))
}

interleavings() {
    #  RETURN: 0; the array 'interleaving_a' and 'interleaving_b' hold every
    #          pair of timelines in four ticks in which each of two gates
    #          fires twice, never at the same tick: gate A's and gate B's.
    local tick=(0 1 2 3) a1 a2 b1 b2 t line_a line_b
    interleaving_a=() interleaving_b=()
    space_iterator_new ticks tick tick tick tick
    while space_iterator_next ticks; do
        a1=${REPLY_LIST[0]} a2=${REPLY_LIST[1]} b1=${REPLY_LIST[2]} b2=${REPLY_LIST[3]}
        (( a1 < a2 && b1 < b2 && a1 != b1 && a1 != b2 && a2 != b1 && a2 != b2 )) || continue
        line_a="" line_b=""
        for t in 0 1 2 3; do
            (( t == a1 || t == a2 )) && line_a+=1 || line_a+=" "
            (( t == b1 || t == b2 )) && line_b+=1 || line_b+=" "
        done
        interleaving_a+=("$line_a") interleaving_b+=("$line_b")
    done
}

race() {
    #  RETURN: 0; plays every interleaving of two gates at one space; '$1'
    #          is 1 where a gate checks and admits in one step.
    echo "one free space, two gates, one car at each; timelines: a digit fires"
    echo "    gate A  gate B  what happens                                    inside"
    interleavings
    local i overbooked_n=0 mark line events
    for (( i = 0; i < ${#interleaving_a[@]}; ++i )); do
        garage_new lot 1
        race_log=()
        dt_trigger_new gate_a Gate "${interleaving_a[i]}" A
        dt_trigger_new gate_b Gate "${interleaving_b[i]}" B
        gate_a+=([garage]=lot [atomic]=$1 [log]=race_log [step]=0 [saw_free]=0)
        gate_b+=([garage]=lot [atomic]=$1 [log]=race_log [step]=0 [saw_free]=0)
        dt_dispatcher_new gates gate_a gate_b
        dt_dispatcher_run gates
        mark="  "
        (( lot[occupied] > lot[capacity] )) && { mark="!!"; (( ++overbooked_n )); }
        printf -v events '%s, ' "${race_log[@]}"
        printf -v line '    "%s"  "%s"  %-46s  %d %s' "${interleaving_a[i]}" "${interleaving_b[i]}" \
                       "${events%, }" "${lot[occupied]}" "$mark"
        echo "${line%"${line##*[! ]}"}"
    done
    echo "interleavings overbooking the garage ((overbooked: $overbooked_n)) of ${#interleaving_a[@]}"
}

race_naive()  {
    #  RETURN: 0; the gates check, then admit, in two steps.
    race 0
}

race_atomic() {
    #  RETURN: 0; the gates check and admit in one step.
    race 1
}

declare -A choice_map=([space]=space [random]=random_stream
                       [race-naive]=race_naive [race-atomic]=race_atomic)
hwut_runner_new runner "Demo: a garage's space counter -- a space, a stream and races, generated;" choice_map
hwut_runner_run runner "$@"
