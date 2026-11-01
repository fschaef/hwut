#! /usr/bin/env bash
#
# @hwut {
#     title   = "Demo: what hwut tolerates, and where it is said"
#     choices {
#         plain       { features = ["demo-passes-on-every-run", "exact-comparison"] }
#         tolerance   { features = ["demo-passes-on-every-run", "equivalence-pattern", "numeric-ratio"]
#                       tolerance {
#                           eq_pattern    = ["(hello|bonjour|hallo|buongiorno|hola|ahoj)"]
#                           numeric_ratio = 0.01
#                       } }
#         constraints { features = ["demo-passes-on-every-run", "constraints"]
#                       tolerance {
#                           constraints = ["load >= 0 and load <= 100",
#                                          "even % 2 == 0",
#                                          "twice == 2 * once"]
#                       } }
#         analogies   { features = ["demo-passes-on-every-run", "analogies"] }
#         race        { features = ["demo-passes-on-every-run", "order-free-block"] }
#         pool        { features = ["demo-passes-on-every-run", "potpourri-subset-duplicates"] }
#         progress    { features = ["demo-passes-on-every-run", "visible-nothing"]
#                       tolerance { nothing = ["[.]+"] } }
#         lisp        { features = ["demo-passes-on-every-run", "analogy-markers"]
#                       tolerance { analogy = ["{", "}"] } }
#         clusters    { features = ["demo-passes-on-every-run", "point-cloud-pair-distance"] }
#     }
# }
#
#______________________________________________________________________________
# A TEST APPLICATION OF HWUT, FOR READING -- 'demo.py' of the Python
# demonstration, in bash.
#
#     hwut.run                   runs every choice below, compares with GOOD/
#     hwut.play demo.sh plain    runs one choice and records it in OUT/
#     hwut.accept demo.sh plain  blesses that recording as GOOD; it runs
#                                nothing. Where a GOOD stands, the change
#                                is 'hwut.merge's -- or '--force' (also
#                                '--as-is') replaces it whole.
#     hwut.merge                 shows OUTPUT against GOOD, key by key
#     hwut.config.show demo.sh   prints what hwut READ from the header above
#
# The header above is the whole configuration: a title, and one scope per
# choice. hwut calls 'demo.sh <choice>' (with the 'bash' of hwut-root.conf)
# and compares what it prints on stdout with 'GOOD/demo.sh--<choice>.txt' --
# here a '.link' to the Python demo's GOOD: the same text, byte for byte.
# '<hwut-end>' closes the stream.
#
# Every run is drawn anew (SRANDOM, the kernel's), so the output differs
# from run to run -- and every choice passes anyway. What each choice shows,
# and WHY it passes, is said in 'demo.py' and in '../../python/TEST/README.txt';
# the choices here print the same, drawn the bash way:
#
#     plain        nothing varies; nothing is tolerated
#     tolerance    'eq_pattern', 'numeric_ratio'
#     constraints  '((name: value))' judged by laws
#     analogies    '((handle))' consistent throughout
#     race         '##! potpourri': three workers -- background subshells --
#                  print as they finish
#     pool         '##! potpourri subset duplicates': four workers take
#                  twelve jobs from one queue (a counter under 'flock')
#     progress     'nothing': lines that count as none
#     lisp         'analogy = ["{", "}"]': markers of one's own
#     clusters     '##! point-cloud ... pair dist=Linf' -- the clustering in
#                  awk: bash has no float
#______________________________________________________________________________
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

GREETING_LIST=(hello bonjour hallo buongiorno hola ahoj)

plain() {
    #  RETURN: 0; prints what never varies.
    echo "the first line"
    echo "the second line: 1 2 3"
}

tolerance() {
    #  RETURN: 0; prints a greeting and a value in [19.91, 20.09], both drawn
    #          at random.
    local cents=$(( 1991 + SRANDOM % 19 ))
    echo "greeting: ${GREETING_LIST[SRANDOM % ${#GREETING_LIST[@]}]}, world"
    printf 'value:    %d.%02d\n' $(( cents / 100 )) $(( cents % 100 ))
}

constraints() {
    #  RETURN: 0; prints bindings, each drawn at random, each lawful.
    local tenth=$(( SRANDOM % 1001 )) once=$(( 1 + SRANDOM % 50 ))
    printf 'load  ((load: %d.%d)) %%\n' $(( tenth / 10 )) $(( tenth % 10 ))
    printf 'even  ((even: %i))\n' $(( 2 * (SRANDOM % 501) ))
    printf 'once  ((once: %i))\n' $once
    printf 'twice ((twice: %i))\n' $(( 2 * once ))
}

analogies() {
    #  RETURN: 0; prints two handles, each drawn at random, each used
    #          consistently from opening to closing.
    local first second
    first=$(( 0x1000 + SRANDOM % 0xF000 ))
    while second=$(( 0x1000 + SRANDOM % 0xF000 )); (( second == first )); do :; done
    printf 'open  ((%04x)) input.txt\n'  $first
    printf 'open  ((%04x)) output.txt\n' $second
    printf 'read  ((%04x)) 17 lines\n'   $first
    printf 'write ((%04x)) 17 lines\n'   $second
    printf 'close ((%04x))\n'            $first
    printf 'close ((%04x))\n'            $second
}

race() {
    #  RETURN: 0; three workers print as they finish; the order is the
    #          scheduler's, the facts are not. The program frames the
    #          unordered block itself: '##! potpourri' ... '####'. A worker
    #          is a background subshell; its line is one write -- no lock.
    local pair nap
    echo "start"
    echo "##! potpourri"
    for pair in A:3 B:5 C:2; do
        ( printf -v nap '0.%03d' $(( SRANDOM % 21 )); sleep "$nap"; echo "worker ${pair%:*} done: ${pair#*:} jobs" ) &
    done
    wait
    echo "####"
    echo "all joined"
}

pool() {
    #  RETURN: 0; four workers take twelve jobs from one queue -- a counter
    #          file under 'flock' -- and each reports the job it finished.
    #          Who takes how many is the scheduler's.
    local queue name
    queue=$(mktemp -d)
    echo 12 > "$queue/left"; : > "$queue/done"
    for name in A B C D; do
        (
            local left nap
            while :; do
                {   flock 9
                    read -r left < "$queue/left"
                    (( left > 0 )) && echo $(( left - 1 )) > "$queue/left"
                } 9> "$queue/lock"
                (( left > 0 )) || exit 0
                printf -v nap '0.%04d' $(( SRANDOM % 51 )); sleep "$nap"
                echo "job done by worker $name" >> "$queue/done"
            done
        ) &
    done
    wait
    local -a done_list
    mapfile -t done_list < "$queue/done"
    rm -rf "$queue"
    echo "twelve jobs, four workers:"
    echo "##! potpourri subset duplicates"
    printf '%s\n' "${done_list[@]}"
    echo "####"
    echo "jobs done: ${#done_list[@]}"
}

progress() {
    #  RETURN: 0; a download that prints dots while it waits; how many is
    #          the network's.
    local i dots
    echo "connecting to mirror"
    for (( i = SRANDOM % 4; i > 0; --i )); do
        printf -v dots '%*s' $(( 1 + SRANDOM % 8 )) ""
        echo "${dots// /.}"
    done
    echo "connected"
    echo "received 1024 bytes"
}

lisp() {
    #  RETURN: 0; a Lisp session at its prompt: two objects, each printed
    #          with its address '{...}', drawn anew per run, and each used
    #          again.
    local table thread
    table=$(( 0x1000000000 + SRANDOM ))
    while thread=$(( 0x1000000000 + SRANDOM )); (( thread == table )); do :; done
    echo '* (defvar *cache* (make-hash-table))'
    printf '#<HASH-TABLE :TEST EQL :COUNT 0 {%X}>\n' $table
    echo '* (defvar *worker* (make-thread (lambda () (loop (sleep 1))) :name "worker"))'
    printf '#<THREAD "worker" RUNNING {%X}>\n' $thread
    echo '* (let ((key (list 1 2))) (setf (gethash key *cache*) *worker*))'
    printf '#<THREAD "worker" RUNNING {%X}>\n' $thread
    echo '* *cache*'
    printf '#<HASH-TABLE :TEST EQL :COUNT 1 {%X}>\n' $table
}

clusters() {
    #  RETURN: 0; clusters 90 noisy points around three centres and prints
    #          the centroids in the order the run found them. The numbers
    #          are awk's: bash has no float.
    echo "centroids (x y), in the order found:"
    echo "##! point-cloud limit=0.3 pair dist=Linf"
    awk -v seed=$SRANDOM '
        function gauss(mu, sigma) {
            return mu + sigma * sqrt(-2 * log(1 - rand())) * cos(6.283185307179586 * rand())
        }
        function d2(i, k) { return (px[i] - cx[k]) ^ 2 + (py[i] - cy[k]) ^ 2 }
        BEGIN {
            srand(seed)
            split("1 5 9", centre_x, " "); split("1 4 1", centre_y, " ")
            n = 0
            for (c = 1; c <= 3; ++c)
                for (j = 0; j < 30; ++j) { px[n] = gauss(centre_x[c], 0.3); py[n] = gauss(centre_y[c], 0.3); ++n }
            # The start: one point at random, then twice the point farthest
            # from every start chosen so far -- one start per cluster.
            s = int(rand() * n); cx[0] = px[s]; cy[0] = py[s]; k_n = 1
            while (k_n < 3) {
                best = -1
                for (i = 0; i < n; ++i) {
                    near = -1
                    for (k = 0; k < k_n; ++k) if (near < 0 || d2(i, k) < near) near = d2(i, k)
                    if (near > best) { best = near; b = i }
                }
                cx[k_n] = px[b]; cy[k_n] = py[b]; ++k_n
            }
            for (round = 0; round < 10; ++round) {
                for (k = 0; k < 3; ++k) { sx[k] = 0; sy[k] = 0; m[k] = 0 }
                for (i = 0; i < n; ++i) {
                    nearest = 0
                    for (k = 1; k < 3; ++k) if (d2(i, k) < d2(i, nearest)) nearest = k
                    sx[nearest] += px[i]; sy[nearest] += py[i]; ++m[nearest]
                }
                for (k = 0; k < 3; ++k) { cx[k] = sx[k] / m[k]; cy[k] = sy[k] / m[k] }
            }
            for (k = 0; k < 3; ++k) printf "    %5.2f %5.2f\n", cx[k], cy[k]
        }'
    echo "####"
}

declare -A CHOICE_MAP=([plain]=plain [tolerance]=tolerance [constraints]=constraints
                       [analogies]=analogies [race]=race [pool]=pool [progress]=progress
                       [lisp]=lisp [clusters]=clusters)
CHOICE_ORDER="plain, tolerance, constraints, analogies, race, pool, progress, lisp, clusters"

choice=${1-}
if [[ -z $choice || -z ${CHOICE_MAP[$choice]+x} ]]; then
    echo "choices: $CHOICE_ORDER"
    exit 1
fi
"${CHOICE_MAP[$choice]}"
echo "<hwut-end>"
