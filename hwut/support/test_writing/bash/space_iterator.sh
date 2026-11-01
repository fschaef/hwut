# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# PURPOSE: EVERY COMBINATION OF A PARAMETER BASIS -- the port of
#          'python/space_iterator.py': the cartesian product, the RIGHTMOST
#          dimension changing fastest. A dimension is an array, named:
#
#     x=(0 2 4); name=(otto heinz); number=(1 2 3)
#     space_iterator_new it x name number
#     while space_iterator_next it; do
#         run_test "${REPLY_LIST[@]}"          # 0 otto 1, 0 otto 2, ...
#     done
#
# An empty basis yields exactly one point, the empty one; a basis with an
# empty dimension yields nothing -- as 'itertools.product'.
#______________________________________________________________________________
[[ -n ${_HWUT_SPACE_ITERATOR_SH:-} ]] && return 0
_HWUT_SPACE_ITERATOR_SH=1

space_iterator_new() {
    #  RETURN: 0, the global associative array named '$1' is an iterator
    #             over the product of the arrays named '$2...', standing
    #             before its first point.
    declare -gA "$1"
    local -n _si_self=$1
    local name; shift
    _si_self=([basis]="$*" [at]="" [started_f]=0 [done_f]=0)
    for name; do
        local -n _si_dimension=$name
        (( ${#_si_dimension[@]} == 0 )) && _si_self[done_f]=1
    done
}

space_iterator_next() {
    #  RETURN: 0, REPLY_LIST = the next point, one value per dimension, in
    #             the basis's order;
    #          1, every point was yielded.
    local -n _si_self=$1
    local -a basis at
    read -ra basis <<< "${_si_self[basis]}"
    read -ra at    <<< "${_si_self[at]}"
    (( _si_self[done_f] )) && return 1
    if (( ! _si_self[started_f] )); then
        _si_self[started_f]=1
        local k
        for (( k = 0; k < ${#basis[@]}; ++k )); do at[k]=0; done
    else
        #  THE RIGHTMOST DIMENSION FIRST; a carry moves to its left.
        local k=$(( ${#basis[@]} - 1 ))
        while (( k >= 0 )); do
            local -n _si_dimension=${basis[k]}
            (( ++at[k] < ${#_si_dimension[@]} )) && break
            at[k]=0
            (( --k ))
        done
        if (( k < 0 )); then _si_self[done_f]=1; return 1; fi
    fi
    _si_self[at]="${at[*]}"
    REPLY_LIST=()
    local k
    for (( k = 0; k < ${#basis[@]}; ++k )); do
        local -n _si_dimension=${basis[k]}
        REPLY_LIST+=("${_si_dimension[at[k]]}")
    done
    return 0
}
