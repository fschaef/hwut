# logsum.awk -- summary of a service log, for the on-call engineer.
#
#     awk -f logsum.awk service.log
#
# Line format:  <ISO-8601 UTC time> <host> <process>[<pid>]: <message>
# Prints: the window, the lines that could not be read, requests and errors
# per host with the 95th percentile latency, requests per minute, restarts,
# and an alert for every process restarted more than LIMIT times within
# WINDOW seconds.
BEGIN { LIMIT = 3; WINDOW = 300 }

function days(y, m, d) {                         # days since 1970-01-01
    if (m <= 2) { y--; m += 12 }
    return 365 * y + int(y / 4) - int(y / 100) + int(y / 400) + int((153 * (m - 3) + 2) / 5) + d - 719469
}
function seconds(ts) {
    return days(substr(ts, 1, 4) + 0, substr(ts, 6, 2) + 0, substr(ts, 9, 2) + 0) * 86400 \
         + substr(ts, 12, 2) * 3600 + substr(ts, 15, 2) * 60 + substr(ts, 18, 6)
}
function p95(host,    n, i, j, v, a) {
    n = lat_n[host]
    for (i = 1; i <= n; i++) a[i] = lat[host, i]
    for (i = 2; i <= n; i++) {                    # insertion sort
        v = a[i]
        for (j = i - 1; j >= 1 && a[j] > v; j--) a[j + 1] = a[j]
        a[j + 1] = v
    }
    return a[int(0.95 * n + 0.999999)]
}

$1 !~ /^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9:.]+Z$/ || $3 !~ /^[a-z]+\[[0-9]+\]:$/ {
    bad[++bad_n] = NR
    next
}
{
    t = seconds($1)
    if (!seen++) { first = $1; t0 = t }
    last = $1
    host = $2
    split($3, part, /[\[\]]/); proc = part[1]; pid = part[2]
    minute = int((t - t0) / 60)
    if ($4 == "GET") {
        req[host]++; per_min[minute]++
        lat[host, ++lat_n[host]] = $7 + 0
    } else if ($4 == "ERROR") {
        req[host]++; err[host]++; per_min[minute]++
    } else if ($4 == "exited") {
        exit_pid[host, proc] = pid; exit_code[host, proc] = $5
        k = ++restart_n[host, proc]; restart_t[host, proc, k] = t
        restart_line[++restart_total] = sprintf("%s %s[%s] %s at +%ds", host, proc, pid, $5, t - t0)
    } else if ($4 == "started" && (host, proc) in exit_pid) {
        restart_line[restart_total] = restart_line[restart_total] sprintf(", restarted as %s[%s]", proc, pid)
        delete exit_pid[host, proc]
    }
}
END {
    printf "window     %s .. %s  (%d s)\n", first, last, seconds(last) - t0
    printf "lines      %d read, %d unreadable", NR, bad_n
    for (i = 1; i <= bad_n; i++) printf "%s%d", (i == 1 ? " (line " : ", "), bad[i]
    print (bad_n ? ")" : "")
    print "per host   host requests errors p95_ms"
    for (host in req) printf "           %s %d %d %d\n", host, req[host], err[host] + 0, p95(host)
    print "per minute"
    for (m = 0; m in per_min; m++) {
        bar = sprintf("%*s", int(per_min[m] / 8), ""); gsub(/ /, "=", bar)
        printf "  +%d min %4d %s\n", m, per_min[m], bar
    }
    print "restarts"
    for (i = 1; i <= restart_total; i++) print "  " restart_line[i]
    if (!restart_total) print "  none"
    print "alerts"
    for (key in restart_n) {
        split(key, kp, SUBSEP)
        for (i = 1; i + LIMIT <= restart_n[key]; i++)
            if (restart_t[key, i + LIMIT] - restart_t[key, i] <= WINDOW) {
                printf "  CRASH LOOP %s %s: %d restarts, more than %d within %d s\n", kp[1], kp[2], restart_n[key], LIMIT, WINDOW
                alert_n++
                break
            }
    }
    if (!alert_n) print "  none"
}
