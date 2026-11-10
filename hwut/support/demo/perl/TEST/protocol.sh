#! /bin/bash
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title   = "Demo: an order law, stated as modes (a pype)"
#     features = ["demo-perl", "demo-perl+cover-order-law-by-pype", "demo-perl+cover-pype-owns-terminal-token"]
#     choices { clean  { }
#               broken { features = ["demo-perl+cover-law-breach-verdict"] }
#               slow   { features = ["demo-perl+cover-pype-tick", "demo-perl+cover-pype-time-guard"] } }
# }
#
# Five clients talk to a service at once. The order of the lines is the
# scheduler's. 'protocol.pype' holds the LAW -- every request answered,
# once, before shutdown; nothing before its request; nothing after
# shutdown -- and prints one verdict per exchange, sorted. The producer
# reports as it happens and prints no '<hwut-end>': the pype's '<eof>'
# does (pype manual 1b).
#
# 'broken' feeds the same pype a stream that breaks the law on purpose --
# answered twice, never answered, an answer without its request, a request
# after shutdown. The pype names each breach and says 'law: BROKEN'; that
# report is the GOOD.
#
# 'slow' answers request 2 only after 3 s. The pype is fed LIVE, so its
# clock is the service's: 'tick:' wakes it while no line arrives, and a
# wait guard marks a request open for over 1 s as late. (A pype named in
# a header reads the output after the run, all at once -- time is no
# input there.)
HERE=$(cd "$(dirname "$0")" && pwd)
#  THE PYPE IS THE FACE ON PATH in an installed hwut, and a copy written
#  by 'hwut.support perl' stands anywhere; in the clone, the module below.
if command -v hwut.pype > /dev/null 2>&1; then
    pype() { hwut.pype "$@"; }
else
    ROOT=$(cd "$HERE/../../../../.." && pwd)
    export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
    pype() { python3 -m hwut.services.pype "$@"; }
fi

producer() {
    #  FIVE CLIENTS, FIVE PROCESSES: each line is one write, so lines never
    #  tear; the order between them is the scheduler's.
    perl - <<'PL'
use strict; use warnings; use Time::HiRes qw(sleep);
sub say { syswrite(STDOUT, "$_[0]\n") }
my @pid;
for my $n (1 .. 5) {
    my $pid = fork // die "fork: $!\n";
    if ($pid == 0) {
        srand($$ ^ int(Time::HiRes::time() * 1e6));
        sleep rand 0.02;  say("request $n");
        sleep rand 0.02;  say("response $n");
        exit 0;
    }
    push @pid, $pid;
}
waitpid($_, 0) for @pid;
say("shutdown");
PL
}

breaking() {
    printf '%s\n' "request 1" "response 1" "response 1" "request 2" \
                   "response 3" "shutdown" "request 4"
}

slow() {
    echo "request 1"; echo "response 1"
    echo "request 2"; echo "request 3"; echo "response 3"
    sleep 3
    echo "response 2"; echo "shutdown"
}

case "$1" in
    clean)  producer | pype "$HERE/protocol.pype" ;;
    broken) breaking | pype "$HERE/protocol.pype" ;;
    slow)   slow     | pype "$HERE/protocol.pype" ;;
    *)      echo "choices: clean, broken, slow"; exit 1 ;;
esac
