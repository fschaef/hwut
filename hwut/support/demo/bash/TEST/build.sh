#! /usr/bin/env bash
#
# @hwut {
#     title   = "Demo: a recursive build, serial and parallel -- one summary, by a pype system"
#     pype    = "build.pypes"
#     same    = true
#     choices = ["serial", "parallel"]
#     features = ["pype-in-header", "pype-system", "same-nominal", "choices-as-list",
#                 "pype-push-pop", "pype-entry-exit", "pype-import", "pype-repeat-group",
#                 "pype-quantity", "pype-anchors-globs-flush"]
#     tolerance { constraints = ["compile < 5 s", "breaches == 0"] }
# }
#
#______________________________________________________________________________
# SUBJECT  the log of a recursive build -- configure, then the directories
#          'lib', 'app' and, inside 'app', 'app/plugins' -- and the summary
#          a pype system makes of it.
# REQUIREMENT  A parallel build builds what the serial build builds: the same
#              sources, the same warnings, the same archives and the same
#              program, linked from the same parts.
#
# 'build.py' of the Python demonstration, in bash. The application only
# REPORTS the build as it happens, as 'make -w' would; the header's 'pype =
# "build.pypes"' puts a system of two pype scripts between it and the
# comparison ('normalise.pype' drops a parallel job's tag, 'build.pype'
# makes the summary -- see their comments). 'same = true': both choices
# share ONE GOOD, 'GOOD/build.sh.txt'. The laws: the compile times sum to
# under 5 s, and nothing broke the build's grammar.
#
# 'parallel' runs each job in a background subshell; a job writes its block
# into a file of this process's own ('mktemp'), and the block is printed
# whole when the job is done ('make -O') -- the job that finishes first,
# first ('wait -n').
#______________________________________________________________________________

#  What each directory does: its sources, warnings and products.
declare -A SOURCE_MAP=([lib]="lib/str.c lib/num.c lib/map.c"
                       [app/plugins]="app/plugins/png.c app/plugins/svg.c"
                       [app]="app/main.c app/cli.c")
declare -A WARNING_MAP=([lib/num.c]="lib/num.c:14:9: warning: unused variable 'n'"
                        [app/plugins/svg.c]="app/plugins/svg.c:3:1: warning: implicit declaration of 'xml_open'")
declare -A PRODUCT_MAP=([lib]="ar rcs lib/libcore.a lib/str.o lib/num.o lib/map.o"
                        [app/plugins]="ar rcs app/plugins/libplug.a app/plugins/png.o app/plugins/svg.o"
                        [app]="ld -o app/demo app/main.o app/cli.o lib/libcore.a app/plugins/libplug.a")

compile_lines() {
    #  RETURN: 0; written on stdout: what building directory '$1' prints,
    #          its sources compiled in the time each takes (40 .. 120 ms).
    local source us spent nap
    for source in ${SOURCE_MAP[$1]}; do
        us=$(( 40000 + SRANDOM % 80001 ))
        printf -v nap '0.%06d' "$us"; sleep "$nap"
        if (( us < 100000 )); then spent="$(( us / 1000 )) ms"
        else printf -v spent '0.%02d s' $(( (us + 5000) / 10000 ))
        fi
        echo "cc -c $source -o ${source%.c}.o (took $spent)"
        [[ -n ${WARNING_MAP[$source]+x} ]] && echo "${WARNING_MAP[$source]}"
    done
    return 0
}

directory_block() {
    #  RETURN: 0; written on stdout: the block 'make -w' prints for '$1' at
    #          level '$2', the block of '$3' (where given) nested before the
    #          product.
    echo "make[$2]: Entering directory '$1'"
    compile_lines "$1"
    [[ -n ${3-} ]] && directory_block "$3" $(( $2 + 1 ))
    echo "${PRODUCT_MAP[$1]}"
    echo "make[$2]: Leaving directory '$1'"
}

configure() {
    #  RETURN: 0; prints what 'configure' prints, and that make enters the
    #          top directory.
    echo "configure: checking for cc... cc"
    echo "configure: checking for ar... ar"
    echo "make: Entering directory 'demo'"
}

serial() {
    #  RETURN: 0; builds one directory after the other.
    configure
    directory_block lib 1
    directory_block app 1 app/plugins
    echo "make: Leaving directory 'demo'"
}

parallel() {
    #  RETURN: 0; builds 'lib' and 'app' at once; each job's block printed
    #          whole when it is done, every line tagged with the job.
    local scratch pid
    local -A slot_of=()
    configure
    scratch=$(mktemp -d)
    directory_block lib 1 | sed 's/^/job1: /' > "$scratch/1" &
    slot_of[$!]=1
    directory_block app 1 app/plugins | sed 's/^/job2: /' > "$scratch/2" &
    slot_of[$!]=2
    for _ in 1 2; do
        wait -n -p pid
        cat "$scratch/${slot_of[$pid]}"
    done
    rm -rf "$scratch"
    echo "make: Leaving directory 'demo'"
}

case ${1-} in
    serial)   serial ;;
    parallel) parallel ;;
    *)        echo "choices: serial, parallel"; exit 1 ;;
esac
