#! /bin/bash
#
# @hwut {
#     title    = "Log summary: an awk report over a live-looking service log"
#     tolerance { eq_pattern  = ["[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}[.][0-9]{3}Z"]
#                 constraints = ["alert_misses == 0"] }
#     choices {
#         normal    { features = ["counts", "restarts", "no-false-alarm"] }
#         crashloop { features = ["crash-loop-alert"] }
#         boundary  { features = ["crash-loop-alert", "no-false-alarm"] }
#         garbled   { features = ["unreadable-lines"] }
#     }
# }
#
# ______________________________________________________________________________
# SUBJECT  the report ../logsum.awk writes over one five-minute log of three
#          web hosts: counts, latency, restarts, alerts
# REQUIREMENT. For a five-minute log of three web hosts, ../logsum.awk
#     R1  counts requests and errors per host and per minute, with the
#         95th percentile latency per host;
#     R2  lists every restart, old process and new one;
#     R3  alerts a CRASH LOOP when a process restarts more than 3 times
#         within 300 s, and only then;
#     R4  names the lines it cannot read instead of miscounting them.
#
# CHOICES -- ../genlog.py writes the log; the traffic is fixed, but the
# timestamps end now, the pids are new and same-millisecond lines come in
# any order, as in a real log:
#     normal     one OOM restart on web-2: listed, no alert (R1, R2, R3).
#     crashloop  web-3's worker killed five times in two minutes: the
#                system breaks the rule, the report's alert says so.
#     boundary   the edge of R3: web-1's worker restarts exactly 3 times
#                within 300 s (no alert), web-2's exactly 4 times (alert).
#     garbled    three mangled lines: named by number, the counts stay right.
#
# HWUT CONCEPTS -- one for each kind of volatility:
#     eq_pattern   the timestamps (any ISO-8601 UTC millisecond time equals
#                  any other); the header states it for every choice.
#     analogies    the pids, printed as '((pid))': free, but consistent --
#                  the pid a restart line says it started must be the pid
#                  the next line says exited.
#     table key=0  awk's 'for (host in ...)' has no defined order; the rows
#                  are matched by host name, every column exact.
#     constraint   R3 stated as a law: the test re-derives from the printed
#                  restart list which processes restarted more than 3 times
#                  within 300 s and counts every process where that and the
#                  report's alerts disagree: '((alert_misses: 0))'. An alert
#                  raised at 3 restarts breaks the law, not just the picture.
#
# The test reshapes the tool's text with a second awk: it frames the per-host
# table for 'table key=0', wraps pids into analogies and appends the R3 line.
# The numbers and alert lines are the tool's own, unchanged.
#
# READING THE GOOD. Per host: requests, errors, p95 in ms. Per minute: a bar
# of '=' per 8 requests. Restarts read as a chain old -> new. 'alerts' is
# 'none' or the CRASH LOOP line; 'near misses' names a process with exactly
# 3 restarts within 300 s -- the edge of R3, no alert; 'R3' counts the
# processes where the alerts disagree with the restart list, with the law
# and verdict.
# ______________________________________________________________________________
HERE=$(cd "$(dirname "$0")" && pwd)

case "$1" in
    normal|crashloop|boundary|garbled) ;;
    *) echo "choices: normal, crashloop, boundary, garbled"; exit 1 ;;
esac

python3 "$HERE/../genlog.py" "$1" | awk -f "$HERE/../logsum.awk" | awk '
    /^per host/   { print "per host"; print "##! table key=0"; in_table = 1
                    printf "  %-8s %8s %7s %7s\n", "host", "requests", "errors", "p95_ms"; next }
    /^per minute/ { if (in_table) print "####"; in_table = 0
                    print "per minute   (requests; bar: 8 requests per =)"; next }
    in_table      { $0 = sprintf("  %-8s %8s %7s %7s", $1, $2, $3, $4) }
    /^restarts/   { section = "restarts" }
    /^alerts/     { section = "alerts" }
    section == "restarts" && /code=/ {      # "  web-2 worker[pid] code=137 at +20s, ..."
        key = $1 " " substr($2, 1, index($2, "[") - 1)
        at = $5; gsub(/[+s,]/, "", at); n = ++restart_n[key]; restart_at[key, n] = at + 0 }
    section == "alerts" && /CRASH LOOP/ { alerted[$3 " " substr($4, 1, length($4) - 1)] = 1 }
    section == "restarts" { $0 = gensub_pid($0) }
    { print }
    END {
        near = ""                      # at most one near miss per fixture: order is moot
        for (key in restart_n) {
            loop = 0; most = 0
            for (i = 1; i <= restart_n[key]; i++) {
                n = 0
                for (j = i; j <= restart_n[key]; j++) if (restart_at[key, j] - restart_at[key, i] <= 300) n++
                if (n > most) most = n
            }
            loop = most > 3
            if (most == 3) near = near sprintf("  %s: 3 restarts within 300 s -- no alert (needs more than 3)\n", key)
            if (loop != (key in alerted)) misses++
            delete alerted[key]
        }
        for (key in alerted) misses++         # an alert for a process that never restarted
        printf "near misses\n%s", (near == "" ? "  none\n" : near)
        printf "R3 alert iff more than 3 restarts within 300 s: misses ((alert_misses: %d))   law == 0   %s\n", \
               misses, (misses == 0 ? "kept" : "BROKEN")
    }
    function gensub_pid(s,    out) {
        out = ""
        while (match(s, /\[[0-9]+\]/)) {
            out = out substr(s, 1, RSTART) "((" substr(s, RSTART + 1, RLENGTH - 2) "))]"
            s = substr(s, RSTART + RLENGTH)
        }
        return out s
    }'
echo "<hwut-end>"
