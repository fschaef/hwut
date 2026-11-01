#! /usr/bin/env python3
"""genlog.py -- a five-minute service log, as three web hosts write it.

    genlog.py <scenario>          scenario: normal, crashloop, boundary, garbled

The traffic is the same in every run (fixed seed): requests, latencies,
errors. What a real log never repeats is real here too: the timestamps
end NOW, the process ids are drawn anew, and lines of one millisecond
come in any order.

    normal     one worker restart on web-2 (an OOM kill), nothing else
    crashloop  web-3's worker is OOM-killed five times in two minutes
    boundary   web-1's worker killed 3 times, web-2's 4 times, each within
               300 s: exactly at and just past the alert limit
    garbled    'normal', plus three lines a broken shipper mangled"""
import random
import sys
import time
from datetime import datetime, timezone

scenario = sys.argv[1]
traffic  = random.Random(7)                     # the same traffic every run
volatile = random.Random(time.time_ns())        # what differs every run
now_ms   = int(time.time() * 1000)
start_ms = now_ms - 300_000
pid = lambda: volatile.randint(1000, 65000)
event_list = []                                 # (ms, tie, text)


def stamp(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + "%03dZ" % (ms % 1000)


def emit(ms, text):
    event_list.append((ms, volatile.random(), "%s %s" % (stamp(ms), text)))


for host in ("web-1", "web-2", "web-3"):
    api, worker = pid(), pid()
    emit(start_ms, "%s worker[%d]: started" % (host, worker))
    t = start_ms + traffic.randint(0, 500)
    while t < now_ms - 1000:
        path = traffic.choice(("/orders", "/orders", "/cart", "/login", "/search"))
        if traffic.random() < 0.02:
            emit(t, "%s api[%d]: ERROR %s db timeout after 5000ms" % (host, api, path))
        else:
            ms = int(traffic.lognormvariate(3.5, 0.6)) + (400 if path == "/search" else 0)
            emit(t, "%s api[%d]: GET %s 200 %dms" % (host, api, path, ms))
        t += traffic.randint(200, 800)
    kills = {"normal": {"web-2": [200]}, "garbled": {"web-2": [200]},
             "crashloop": {"web-3": [60, 90, 120, 150, 180]},
             "boundary": {"web-1": [40, 140, 240], "web-2": [20, 90, 160, 230]}}[scenario].get(host, [])
    for second in kills:
        ms = start_ms + second * 1000
        emit(ms, "%s worker[%d]: exited code=137" % (host, worker))
        worker = pid()
        emit(ms + 250, "%s worker[%d]: started" % (host, worker))

event_list.sort()
lines = [text for _, _, text in event_list]
if scenario == "garbled":
    lines[17]  = lines[17][:31]                        # cut short
    lines.insert(230, "\x00\x00\x00\x00 web-1 api")    # a block of zeros
    lines.insert(400, lines[400].replace(" ", "", 3))  # blanks lost
print("\n".join(lines))
