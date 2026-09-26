#! /bin/bash
#
# @hwut {
#     title      = "Every supervisor event reaches the HINTS by name"
#     choices    = ["caps", "multi"]
#     #  THIS TEST STORMS ON PURPOSE (O-21): its 'pids' offender forks
#     #  40 past an INNER cap of 4. The outer supervisor watches the
#     #  same process group, so it says what it costs.
#     caps { child_process_max_n = 128 }
# }
#
# ---------------------------------------------------------------------------
#
# THE OUTER LEVEL: 'hwut.run' over a tree of applications that each
# violate ONE cap, and a reader who looks only at the HINTS block. Every
# violation must be named there -- the cap that was hit, with its numbers
# -- and the phrase "killed by the supervisor" must appear NOWHERE. That
# phrase is the fallback for a containment nobody translated; a test that
# permits it once permits it for every cap.
#
#     caps    one application per cap, each stating a small cap in its
#             header and blowing it: wall-clock, cpu, memory, file size,
#             process count.
#     multi   the same violations under 'interactive = true', where ONE
#             process serves every choice (multi_execute). The choice
#             that blew the cap is named with its cap; the choices that
#             never ran because the process was already gone say THAT,
#             and are not reported as killed.
#
# The wall clock is masked from the DIRECTORIES line ('eq_pattern').
# Numbers in the HINTS ('cap 8 MB, peak 41 MB') are machine-chosen and
# are stripped: the assertion is that a cap is NAMED, not what was seen.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../../.." && pwd)   # above vut/, so 'vut.' imports
RUN="python3 -m vut.services.run"
export PYTHONPATH="$ROOT"

case "$1" in
    --hwut-info)
        echo "Every supervisor event reaches the HINTS by name;"
        echo "CHOICES: caps, multi;"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"

#  --------------------------------------------------------------------------
#  THE OFFENDERS. Each states the cap it will blow, small, in its own
#  header, so the run is quick and the violation is unambiguous. Each
#  has a nominal, so the gate (E-41) lets it run.
#  --------------------------------------------------------------------------
tree() {                # $1: 'plain' or 'multi'
    local mode=$1
    mkdir -p tree/suite/TEST/GOOD
    printf 'hwut {\n}\n' > hwut-root.conf
    printf 'hwut {\n}\n' > tree/suite/TEST/hwut.conf
    case $mode in
        plain) offender_plain ;;
        multi) offender_multi ;;
    esac
}

#  The body of each offence, as a bash fragment. EACH 'exec's: the
#  application ITSELF must be the offender. A cap that kills a child
#  of a bash wrapper leaves bash to print '<hwut-end>' and exit 0, and
#  the truthful report is then "unexpected stderr" -- which is what
#  the first draft of this test got, and rightly.
BLOW_WALL='exec sleep 30'
BLOW_CPU='exec python3 -c "
while True: pass"'
BLOW_MEMORY='exec python3 -c "
x = bytearray(64 * 1024 * 1024); import time; time.sleep(2)"'
#  CPython ignores SIGXFSZ and dies by its own EFBIG exception; 'dd'
#  does not, and dies by the signal -- the death the cap is for.
BLOW_FSIZE='exec dd if=/dev/zero of=big bs=1M count=4 status=none'
BLOW_PIDS='exec python3 -c "
import os, time
for _ in range(40):
    if os.fork() == 0: time.sleep(5); os._exit(0)
time.sleep(5)"'

offender_plain() {
    local d=tree/suite/TEST
    #  name  cap-word=value  body
    offender $d wall   "timeout_sec = 1"           "$BLOW_WALL"
    offender $d cpu    "cpu_sec = 1"               "$BLOW_CPU"
    offender $d memory "memory_mb = 8"             "$BLOW_MEMORY"
    offender $d fsize  "file_size_mb = 1"          "$BLOW_FSIZE"
    offender $d pids   "child_process_max_n = 4"   "$BLOW_PIDS"
}

offender() {            # $1 dir  $2 name  $3 cap statement  $4 body
    local d=$1 name=$2 cap=$3 body=$4
    printf '#!/bin/bash\n# @hwut { title = "%s"  caps { %s } }\n%s\necho "<hwut-end>"\n' \
        "$name" "$cap" "$body" > $d/test-$name.sh
    chmod +x $d/test-$name.sh
    printf '<hwut-end>\n' > $d/GOOD/test-$name.sh.txt
}

offender_multi() {
    local d=tree/suite/TEST
    #  ONE application, interactive: choices served by one process in
    #  SORTED order -- the plan's order, not the header's -- so the
    #  names carry a letter that makes the sort the story. 'a_first'
    #  passes; 'b_blow' exceeds the process cap; 'c_after' and
    #  'd_last' never get served.
    #  A proper interactive citizen: DOWN 'run <choice> <out> <err>',
    #  UP 'done <choice> <status>', 'bye' on 'quit'. The choice's
    #  output goes to the sinks it was told; the wire carries only
    #  the protocol.
    cat > $d/test-multi.sh << 'EOF'
#!/bin/bash
# @hwut { title = "multi"
#         choices = ["a_first", "b_blow", "c_after", "d_last"]
#         interactive = true
#         caps { child_process_max_n = 4  timeout_sec = 20 } }
while read -r verb choice out err; do
    case "$verb" in
        quit) echo "bye"; exit 0 ;;
        run)
            case "$choice" in
                b_blow)
                    #  THE OFFENCE, in the session's own process group:
                    #  a storm past the process cap.
                    python3 -c "
import os, time
for _ in range(40):
    if os.fork() == 0: time.sleep(5); os._exit(0)
time.sleep(5)" > "$out" 2> "$err"
                    printf '<hwut-end>\n' >> "$out" ;;
                *)  printf 'steady %s\n<hwut-end>\n' "$choice" > "$out"; : > "$err" ;;
            esac
            echo "done $choice 0" ;;
    esac
done
EOF
    chmod +x $d/test-multi.sh
    for c in a_first b_blow c_after d_last; do
        printf 'steady %s\n<hwut-end>\n' $c > $d/GOOD/test-multi.sh--$c.txt
    done
}

#  --------------------------------------------------------------------------
#  THE READING: the HINTS block only, numbers stripped, and the verdict.
#  --------------------------------------------------------------------------
hints() {
    #  From the HINTS banner to the closing rule, the framing dropped,
    #  the numbers in parentheses dropped, runs of blanks folded.
    awk '/^HINTS/{on=1; next} on && /^====/{exit} on' run.txt \
        | grep -v '^----' \
        | sed 's/ *([^)]*)//' \
        | sed 's/  */ /g; s/ *$//'
}

verdict() {             # $1 label  $2 count (>0 holds)  $3 message
    local label=$1 count=$2 msg=$3
    if [ "${count:-0}" -gt 0 ] 2>/dev/null; then echo "  OK  : $msg"
    else                                         echo "  FAIL: $msg"; fail=1
    fi
}

case "$1" in

caps)
    tree plain
    $RUN --directory=tree --plain > run.txt 2> err.txt
    echo "STATUS: $?"
    echo "HINTS {"
    hints | sed 's/^/    /'
    echo "}"
    fail=0
    h=$(hints)
    verdict a "$(echo "$h" | grep -c 'test-wall.sh .*over the wall-clock cap')"   \
              "wall-clock: named"
    verdict b "$(echo "$h" | grep -c 'test-cpu.sh .*over the cpu-time cap')"      \
              "cpu-time: named"
    verdict c "$(echo "$h" | grep -c 'test-memory.sh .*over the memory cap')"     \
              "memory: named"
    verdict d "$(echo "$h" | grep -c 'test-fsize.sh .*over the file-size cap')"   \
              "file-size: named"
    verdict e "$(echo "$h" | grep -c 'test-pids.sh .*over the process cap')"      \
              "process count: named"
    verdict f "$([ "$(grep -c 'killed by the supervisor' run.txt)" = 0 ] && echo 1)" \
              "'killed by the supervisor' appears nowhere"
    [ $fail = 0 ] && echo "SUCCESS: every cap is named where it was hit." \
                  || echo "FAILURE: a containment reached the reader untranslated."
    ;;

multi)
    tree multi
    $RUN --directory=tree --plain > run.txt 2> err.txt
    echo "STATUS: $?"
    echo "HINTS {"
    hints | sed 's/^/    /'
    echo "}"
    fail=0
    h=$(hints)
    verdict a "$(grep -c 'a_first .*\[OK\]' run.txt)" \
              "the choice before the offence passed"
    verdict b "$(echo "$h" | grep -c 'b_blow .*over the process cap')" \
              "the offending choice is named with its cap"
    verdict c "$(echo "$h" | grep -c 'c_after .*already died')" \
              "the choice after it says the process had already died"
    verdict d "$([ "$(echo "$h" | grep -c 'c_after .*killed\|d_last .*killed')" = 0 ] && echo 1)" \
              "and is NOT reported as killed"
    verdict e "$([ "$(grep -c 'killed by the supervisor' run.txt)" = 0 ] && echo 1)" \
              "'killed by the supervisor' appears nowhere"
    [ $fail = 0 ] && echo "SUCCESS: one process, one offence, every choice told the truth." \
                  || echo "FAILURE: the multi road lost the story."
    ;;

*)
    echo "unknown choice '$1'"
    exit 1 ;;
esac

echo "<hwut-end>"
