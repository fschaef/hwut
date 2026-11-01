#! /usr/bin/env bash
#
# @hwut {
#     title      = "space_iterator: every combination of a parameter basis"
#     choices {
#         product { features = ["bash-space"] }
#         edges   { features = ["bash-space"] }
#     }
#     interactive = true
# }
#
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# PURPOSE: The bash port of 'python/TEST/test-space-iterator.py', choice for
#          choice, held against its GOOD files by '.link'.
#______________________________________________________________________________
source "$(dirname "$0")/../hwut_runner.sh"
source "$(dirname "$0")/../space_iterator.sh"

banner() { echo; echo "--- $1 ---"; }

points() {
    #  RETURN: 0; every point of the basis '$@' (array names) printed, one
    #          per line, then the count.
    local n=0 text
    space_iterator_new it "$@"
    while space_iterator_next it; do
        printf -v text '%s, ' "${REPLY_LIST[@]}"
        (( ${#REPLY_LIST[@]} )) || text=""
        echo "  (${text%, })"
        (( ++n ))
    done
    echo "  $n point(s)"
}

run_product() {
    banner "[0, 2, 4] x [otto, heinz] x [1, 2] -- 3 * 2 * 2 points"
    local x=(0 2 4) name=(otto heinz) number=(1 2)
    points x name number
}

run_edges() {
    banner "an EMPTY basis -- one point, the empty one"
    points
    banner "a basis with an EMPTY dimension -- nothing"
    local one=(1 2) none=() three=(3)
    points one none three
    banner "ONE dimension -- its values one by one"
    local letters=(a b c)
    points letters
}

declare -A choice_map=([product]=run_product [edges]=run_edges)
hwut_runner_new runner "space_iterator: every combination of a parameter basis" choice_map
hwut_runner_run runner "$@"
