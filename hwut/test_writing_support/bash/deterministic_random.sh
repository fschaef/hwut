# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# PURPOSE: A RANDOM STREAM THAT IS THE SAME EVERYWHERE -- the port of
#          'python/deterministic_random.py': Park-Miller MINSTD,
#          'state = 48271 * state mod (2^31 - 1)'. Bash's arithmetic is 64
#          bit: the product fits, the stream is Python's, seed for seed.
#
#     dr_stream_new s 66             # global associative array 's'
#     dr_stream_next_int s 0 9       # REPLY=7
#     dr_stream_select s pool        # REPLY=an element of the array 'pool'
#     dr_marker_new m
#     dr_stream_select_unchosen s pool m
#
# A FLOAT is carried as its text, as Python's 'repr' writes it: 'next_float'
# and 'gauss' compute in awk (POSIX; the platform's libm, as Python's).
# 'coin' compares 'next_float' with the probability without one: exactly,
# as rationals, where the probability is a decimal of at most nine places
# -- and through awk else.
#
# A SELECTION MARKER remembers candidates by VALUE: a bash array holds
# strings, not objects with an identity (Python's 'id'). Two equal strings
# are one candidate -- as in the Perl port.
#______________________________________________________________________________
[[ -n ${_HWUT_DETERMINISTIC_RANDOM_SH:-} ]] && return 0
_HWUT_DETERMINISTIC_RANDOM_SH=1
source "${BASH_SOURCE[0]%/*}/hwut_pytext.sh"

dr_marker_new() {
    #  RETURN: 0, the global associative array named '$1' is a
    #             SelectionMarker with an empty chosen-set.
    declare -gA "$1"
    local -n _drm_self=$1
    _drm_self=()
}

dr_marker_reset() {
    #  RETURN: 0, the marker '$1' forgot every chosen candidate; the next
    #             cycle restarts.
    local -n _drm_self=$1
    _drm_self=()
}

dr_stream_new() {
    #  RETURN: 0, the global associative array named '$1' is a
    #             DeterministicStream seeded with '$2' (default 0x42).
    declare -gA "$1"
    local -n _drs_self=$1
    _drs_self=([state]=$(( ${2:-0x42} & 0x7FFFFFFF )))
}

dr_stream_next_int() {
    #  RETURN: 0, REPLY = a random integer in ['$2', '$3']; the stream '$1'
    #             advanced by one step.
    local -n _drs_self=$1
    local state=$(( (48271 * _drs_self[state]) % 2147483647 ))
    _drs_self[state]=$state
    if (( $2 == $3 )); then REPLY=$2
    else                    REPLY=$(( $2 + state % ($3 - $2 + 1) ))
    fi
}

dr_stream_next_float() {
    #  RETURN: 0, REPLY = a random float in [0.0, 1.0), as Python's 'repr'
    #             writes it: 'next_int(0, 1000000) / 1000001.0'.
    dr_stream_next_int "$1" 0 1000000
    REPLY=$(awk "$PYTEXT_AWK"' BEGIN { print float_repr('"$REPLY"' / 1000001.0) }')
}

dr_stream_coin() {
    #  RETURN: 0, with the probability '$2' (a decimal text); 1, else.
    #
    #  THE FLOOR (TW-1): 'next_float' takes 1000001 values, so the
    #  probability is resolved in steps of 1/1000001.
    local p=$2 n whole fraction
    dr_stream_next_int "$1" 0 1000000
    n=$REPLY
    if [[ $p =~ ^([0-9]*)\.?([0-9]{0,9})$ && -n $p && $p != . ]]; then
        #  n / 1000001 < whole.fraction  <=>  n * 10^k < whole.fraction * 10^k * 1000001
        whole=${BASH_REMATCH[1]:-0} fraction=${BASH_REMATCH[2]}
        local scale=$(( 10 ** ${#fraction} ))
        (( n * scale < (10#$whole * scale + 10#${fraction:-0}) * 1000001 ))
        return
    fi
    [[ $(awk 'BEGIN { print ('"$n"' / 1000001.0 < ('"$p"') + 0) }') == 1 ]]
}

dr_stream_select() {
    #  RETURN: 0, REPLY = a uniformly random element of the array named
    #             '$2'. Stateless: the same stream state and the same
    #             candidates always yield the same element.
    local -n _drs_pool=$2
    dr_stream_next_int "$1" 0 $(( ${#_drs_pool[@]} - 1 ))
    REPLY=${_drs_pool[REPLY]}
}

dr_stream_choice() {
    #  RETURN: 0, REPLY = a random element of the array named '$2'.
    dr_stream_select "$@"
}

dr_stream_select_unchosen() {
    #  RETURN: 0, REPLY = a random element of the array named '$2' that the
    #             marker '$3' has not seen; the choice is recorded. Where
    #             every candidate was seen, the marker is reset and the full
    #             pool drawn from.
    local -n _drs_pool=$2 _drs_marker=$3
    local unchosen=() candidate
    for candidate in "${_drs_pool[@]}"; do
        [[ -z ${_drs_marker[$candidate]+x} ]] && unchosen+=("$candidate")
    done
    if (( ${#unchosen[@]} == 0 )); then
        _drs_marker=()
        unchosen=("${_drs_pool[@]}")
    fi
    dr_stream_next_int "$1" 0 $(( ${#unchosen[@]} - 1 ))
    REPLY=${unchosen[REPLY]}
    _drs_marker[$REPLY]=1
}

dr_stream_gauss() {
    #  RETURN: 0, REPLY = a draw of the normal distribution ('$2' mu, '$3'
    #             sigma), clipped to ['$4', '$5'] where given, by the
    #             Box-Muller transform -- as Python's 'repr' writes it.
    #
    #  NOT BIT-PORTABLE (S3): the uniform draws are, 'log', 'cos' and 'sqrt'
    #  are the platform's libm. A GOOD that prints a draw rounds it.
    local u1 u2
    dr_stream_next_int "$1" 0 1000000; u1=$REPLY
    dr_stream_next_int "$1" 0 1000000; u2=$REPLY
    REPLY=$(_dr_gauss_awk "$u1" "$u2" "$2" "$3" "${4-}" "${5-}" float_repr)
}

dr_stream_gauss_int() {
    #  RETURN: 0, REPLY = 'gauss' rounded to the nearest integer, a half to
    #             the even one (Python's 'round').
    local u1 u2
    dr_stream_next_int "$1" 0 1000000; u1=$REPLY
    dr_stream_next_int "$1" 0 1000000; u2=$REPLY
    REPLY=$(_dr_gauss_awk "$u1" "$u2" "$2" "$3" "${4-}" "${5-}" py_round)
}

_dr_gauss_awk() {
    #  RETURN: 0; written on stdout: the Box-Muller draw of the integers '$1'
    #          and '$2' (next_int's), mu '$3', sigma '$4', clipped to '$5'
    #          and '$6' where not empty, passed through the awk function '$7'.
    awk -v n1="$1" -v n2="$2" -v mu="$3" -v sigma="$4" -v lower="$5" -v upper="$6" \
        "$PYTEXT_AWK"'
        BEGIN {
            u1 = n1 / 1000001.0 + 1e-9
            u2 = n2 / 1000001.0
            z0 = sqrt(-2.0 * log(u1)) * cos(2.0 * 3.141592653589793 * u2)
            r  = z0 * (sigma + 0) + (mu + 0)
            if      (lower != "" && r < lower + 0) r = lower + 0
            else if (upper != "" && r > upper + 0) r = upper + 0
            printf "%s\n", '"$7"'(r)
        }'
}

dr_stream_sample_indices() {
    #  RETURN: 0, REPLY_LIST = '$3' unique indices from 0 .. '$2'-1, by
    #             Fisher-Yates.
    local n=$2 k=$3 i idx t
    local -a indices=()
    for (( i = 0; i < n; ++i )); do indices[i]=$i; done
    REPLY_LIST=()
    for (( i = 0; i < k; ++i )); do
        dr_stream_next_int "$1" "$i" $(( n - 1 )); idx=$REPLY
        t=${indices[i]}; indices[i]=${indices[idx]}; indices[idx]=$t
        REPLY_LIST+=("${indices[i]}")
    done
}

dr_stream_sample() {
    #  RETURN: 0, REPLY_LIST = '$3' unique elements of the array named '$2',
    #             in the order drawn.
    local -n _drs_pool=$2
    dr_stream_sample_indices "$1" "${#_drs_pool[@]}" "$3"
    local i result=()
    for i in "${REPLY_LIST[@]}"; do result+=("${_drs_pool[i]}"); done
    REPLY_LIST=("${result[@]}")
}
