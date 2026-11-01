#! /usr/bin/env bash
#
# @hwut {
#     title      = "DeterministicStream RNG and SelectionMarker spread"
#     choices {
#         gauss      { features = ["bash-random"] }
#         primitives { features = ["bash-random"] }
#         ranges     { features = ["bash-random"] }
#         sample     { features = ["bash-random"] }
#         seed_sweep { features = ["bash-random"] }
#         select     { features = ["bash-random"] }
#         unchosen   { features = ["bash-random"] }
#     }
#     interactive = true
# }
#
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# PURPOSE: The bash port of 'python/TEST/test-deterministic-random.py', choice
#          for choice. Its GOOD files are the Python test's, by '.link': the
#          two modules owe the same stream, byte for byte.
#______________________________________________________________________________
source "$(dirname "$0")/../hwut_runner.sh"
source "$(dirname "$0")/../deterministic_random.sh"

SEED=0x42
TOLERANCE_REGION_BEGIN="##! table numeric={1:1e-12}"
REGION_END="####"

banner() { echo; echo "--- $1 ---"; }

draws() {
    #  RETURN: 0, REPLY = the REPLY of '$1' calls of '$3...', joined by
    #             the text '$2'.
    local n=$1 separator=$2 i out=""; shift 2
    for (( i = 0; i < n; ++i )); do
        "$@"
        out+="${out:+$separator}$REPLY"
    done
    REPLY=$out
}

run_primitives() {
    local i
    banner "next_int(0, 1000000) -- first 20"
    dr_stream_new s $SEED
    for (( i = 0; i < 20; ++i )); do dr_stream_next_int s 0 1000000; printf '[%02d] %d\n' $i "$REPLY"; done

    banner "next_float -- first 10 (full precision)"
    dr_stream_new s $SEED
    for (( i = 0; i < 10; ++i )); do dr_stream_next_float s; printf '[%02d] %s\n' $i "$REPLY"; done

    banner "coin(0.5) -- 40 draws"
    dr_stream_new s $SEED
    local out=()
    for (( i = 0; i < 40; ++i )); do if dr_stream_coin s 0.5; then out+=(T); else out+=(F); fi; done
    echo "${out[*]}"
}

run_ranges() {
    banner "next_int(0, 9) -- 30 draws"
    dr_stream_new s $SEED
    draws 30 " " dr_stream_next_int s 0 9; echo "$REPLY"

    banner "next_int(5, 5) -- degenerate range returns the bound"
    dr_stream_new s $SEED
    draws 5 " " dr_stream_next_int s 5 5; echo "$REPLY"

    banner "next_int(-3, 3) -- spanning zero"
    dr_stream_new s $SEED
    local i out=()
    for (( i = 0; i < 20; ++i )); do dr_stream_next_int s -3 3; printf -v REPLY '%+d' "$REPLY"; out+=("$REPLY"); done
    echo "${out[*]}"
}

run_gauss() {
    local i
    banner "gauss(0, 1) -- 10 draws (full precision)"
    dr_stream_new s $SEED
    echo "$TOLERANCE_REGION_BEGIN"
    for (( i = 0; i < 10; ++i )); do dr_stream_gauss s 0.0 1.0; printf '[%02d] %s\n' $i "$REPLY"; done
    echo "$REGION_END"

    banner "gauss(0, 1) clamped to [-1, 1]"
    dr_stream_new s $SEED
    echo "$TOLERANCE_REGION_BEGIN"
    for (( i = 0; i < 10; ++i )); do dr_stream_gauss s 0.0 1.0 -1.0 1.0; printf '[%02d] %s\n' $i "$REPLY"; done
    echo "$REGION_END"

    banner "gauss_int(100, 15) -- 20 draws"
    dr_stream_new s $SEED
    draws 20 " " dr_stream_gauss_int s 100.0 15.0; echo "$REPLY"
}

run_sample() {
    banner "sample_indices(10, 10) -- full permutation"
    dr_stream_new s $SEED
    dr_stream_sample_indices s 10 10; pytext_list_repr int "${REPLY_LIST[@]}"; echo "$REPLY"

    banner "sample_indices(20, 5) -- partial draw"
    dr_stream_new s $SEED
    dr_stream_sample_indices s 20 5; pytext_list_repr int "${REPLY_LIST[@]}"; echo "$REPLY"

    banner "choice from a list -- 20 draws"
    dr_stream_new s $SEED
    local pool=(alpha beta gamma delta epsilon)
    draws 20 " " dr_stream_choice s pool; echo "$REPLY"

    banner "sample(list, 4) -- unique elements"
    dr_stream_new s $SEED
    local letters=(A B C D E F G H)
    dr_stream_sample s letters 4; pytext_list_repr str "${REPLY_LIST[@]}"; echo "$REPLY"
}

run_select() {
    banner "select over a list -- 20 draws"
    dr_stream_new s $SEED
    local pool=(a b c d)
    draws 20 " " dr_stream_select s pool; echo "$REPLY"

    banner "select over a tuple -- 12 draws"
    dr_stream_new s $SEED
    local branches=(p q r)
    draws 12 " " dr_stream_select s branches; echo "$REPLY"
}

run_unchosen() {
    local i out first
    banner "stable pool -- three full cycles of 4 elements"
    dr_stream_new s $SEED
    local pool=(a b c d)
    dr_marker_new m
    draws 12 " " dr_stream_select_unchosen s pool m; echo "$REPLY"

    banner "FRESH container each call -- identical to the stable pool above"
    dr_stream_new s $SEED
    dr_marker_new m
    out=()
    for (( i = 0; i < 12; ++i )); do
        local fresh=(a b c d)                  # a new array every call
        dr_stream_select_unchosen s fresh m; out+=("$REPLY")
    done
    echo "${out[*]}"

    banner "sub-pool coherence -- draw from [a,b] then the full [a,b,c,d]"
    dr_stream_new s $SEED
    dr_marker_new m
    local full=(a b c d) sub=(a b)
    dr_stream_select_unchosen s sub m; first=$REPLY
    draws 3 " " dr_stream_select_unchosen s full m
    echo "first(from sub): $first  then(from full): $REPLY"

    banner "reset() restarts the cycle"
    dr_stream_new s $SEED
    dr_marker_new m
    draws 4 " " dr_stream_select_unchosen s pool m; local before=$REPLY
    dr_marker_reset m
    draws 4 " " dr_stream_select_unchosen s pool m; local after=$REPLY
    echo "before reset: $before"
    echo "after  reset: $after"
}

run_seed_sweep() {
    local seed
    banner "first next_int(0, 1000000) per seed 0..15"
    for (( seed = 0; seed < 16; ++seed )); do
        dr_stream_new s $seed
        dr_stream_next_int s 0 1000000
        printf 'seed=%2d -> %d\n' $seed "$REPLY"
    done
}

declare -A choice_map=(
    [primitives]=run_primitives
    [ranges]=run_ranges
    [gauss]=run_gauss
    [sample]=run_sample
    [select]=run_select
    [unchosen]=run_unchosen
    [seed_sweep]=run_seed_sweep
)
hwut_runner_new runner "DeterministicStream RNG and SelectionMarker spread" choice_map
hwut_runner_run runner "$@"
