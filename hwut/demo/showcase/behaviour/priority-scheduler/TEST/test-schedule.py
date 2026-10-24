#! /usr/bin/env python3
# @hwut {
#     title    = "Fixed-priority scheduling on one CPU: Gantt charts, deadlines, priority inversion"
#     choices {
#         rate-monotonic { features = ["deadlines-met", "preemption"]
#                          tolerance { constraints = ["misses == 0"] } }
#         overload       { features = ["miss-shown"]
#                          tolerance { constraints = ["misses > 0"] } }
#         inversion      { features = ["inversion-shown"]
#                          tolerance { constraints = ["misses > 0"] } }
#         inheritance    { features = ["inheritance-bounds"]
#                          tolerance { constraints = ["misses == 0"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  the schedule the RTOS core produces for one task set on one CPU
         (Gantt chart) and every job's response against its deadline
REQUIREMENT  On one CPU, the highest-priority ready job always runs; a job
             blocked on the mutex waits at most for the critical section of
             the job holding it (priority inheritance), so the high-priority
             'bus' task of the Pathfinder set meets its 8-tick deadline; and
             a task set within the CPU's capacity misses no deadline.

The unit is '../rtkernel.py', the scheduling core of a small RTOS, stepped
one tick at a time over a task set from '../tasksets/' (name, priority,
release, period, deadline, work -- 'c' compute, 'm' inside mutex M).

The GANTT chart, one column per tick, one row per task, highest priority
on top:
    =  running        m  running while holding the mutex M
    -  ready, but a higher-priority job runs     B  blocked on the mutex
    .  nothing to do  and under each row:  ^ release   ! deadline missed
The GOOD repeats this legend under the chart. Then every job's release,
completion, response and deadline, and the number of missed deadlines,
bound as '((misses: N))'.

rate-monotonic  three periodic tasks, utilisation 0.75: preemption visible
                as '-', no '!' anywhere -- ((misses: 0)).
overload        'slow' grown to 9 ticks, utilisation 1.06: the chart shows
                where the CPU runs out; the misses are listed with '!!'.
inversion       Pathfinder, 1997, protocol 'none': 'bus' blocks on M held
                by 'meteo', and 'comms' -- unrelated to M -- preempts
                'meteo' for 8 ticks. 'bus' misses its deadline: the GOOD file
                is the accepted picture of the bug that reset the lander.
inheritance     the same set with priority inheritance (the fix uploaded to
                Mars): 'meteo' runs at 'bus' priority inside M, 'comms'
                waits; 'bus' answers in 7 ticks, within its 8.

HWUT CONCEPTS  The chart stands in '##! verbatim': it pins every tick, so
ANY change of the schedule turns the run red -- also a lawful one, such as
'bus' answering in 5. The constraint binding '((misses: N))' carries the
law into hwut's own judgment: 'misses == 0' for the choices that must keep
it, 'misses > 0' for overload and inversion, whose GOODs are the accepted
reports. At run time the chart fails first; the law guards the
RE-RECORDING -- 'hwut.accept' refuses a new chart with a missed deadline on
a lawful choice (inheritance broken: 'bus' late), and an inversion chart
that no longer shows the miss.
______________________________________________________________________________
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import rtkernel                                                   # noqa: E402

CHOICE_DB = {   # task set, mutex protocol, ticks to show
    "rate-monotonic": ("rate-monotonic.txt", "none", 32),
    "overload":       ("overload.txt", "none", 32),
    "inversion":      ("pathfinder.txt", "none", 24),
    "inheritance":    ("pathfinder.txt", "inheritance", 24),
}


def read_taskset(path):
    task_list = []
    with open(path) as fh:
        for line in fh:
            if line.startswith("#") or not line.strip():
                continue
            word = line.split()
            task_list.append({"name": word[0], "prio": int(word[1]), "release": int(word[2]),
                              "period": int(word[3]), "deadline": int(word[4]),
                              "work": [(w[0], int(w[1:])) for w in word[5:]]})
    return sorted(task_list, key=lambda task: -task["prio"])


def main(choice):
    taskset, protocol, horizon = CHOICE_DB[choice]
    task_list = read_taskset(os.path.join(HERE, "..", "tasksets", taskset))
    timeline, event_list = rtkernel.run(task_list, protocol, horizon)

    print("task set: tasksets/%s, mutex protocol: %s" % (taskset, protocol))
    for task in task_list:
        print("    %-6s prio %d  release %2d  period %2s  deadline %2d  work %s"
              % (task["name"], task["prio"], task["release"], task["period"] or "-",
                 task["deadline"], " ".join("%s%d" % seg for seg in task["work"])))
    periodic = [t for t in task_list if t["period"]]
    if periodic:
        u = sum(sum(n for _, n in t["work"]) / t["period"] for t in periodic)
        print("    utilisation U = %s = %.2f  %s" % (" + ".join("%d/%d" % (sum(n for _, n in t["work"]), t["period"])
                                                           for t in periodic), u,
                                               "(<= 1: within the CPU)" if u <= 1 else "(> 1: more than the CPU has)"))
    else:
        print("    one-shot jobs (no period); mutex M shared by %s"
              % " and ".join(t["name"] for t in task_list if any(k == "m" for k, _ in t["work"])))
    print()
    print("##! verbatim")
    print("tick    " + "".join(str(t).ljust(5) if t % 5 == 0 else "" for t in range(horizon)).rstrip())
    for task in task_list:
        name = task["name"]
        print("%-7s %s" % (name, "".join(state[name] for state in timeline)))
        marks = [" "] * horizon
        for t, who, what in event_list:
            if who == name and t < horizon and what in ("release", "miss"):
                marks[t] = "^" if what == "release" and marks[t] == " " else "!"
        print("        %s" % "".join(marks).rstrip())
    print("####")
    print("(= running   m running, holding mutex M   - ready, a higher one runs")
    print(" B blocked on M   . nothing to do;   under a row: ^ release  ! missed)")
    print()

    open_db, miss_n = {}, 0
    print("jobs:")
    for t, who, what in sorted(event_list, key=lambda e: (e[1] != "bus", e[1], e[0])):
        if what == "release":
            open_db.setdefault(who, []).append(t)
        elif what == "done":
            release = open_db[who].pop(0)
            deadline = next(task["deadline"] for task in task_list if task["name"] == who)
            late = t - release > deadline
            miss_n += late
            print("    %-6s released %2d  done %2d  response %2d  deadline %2d  %s"
                  % (who, release, t, t - release, deadline, "!! MISSED" if late else "met"))
    for who in sorted(open_db):
        for release in open_db[who]:
            deadline = next(task["deadline"] for task in task_list if task["name"] == who)
            if release + deadline <= horizon:
                miss_n += 1
                print("    %-6s released %2d  not done by tick %d  deadline %2d  !! MISSED"
                      % (who, release, horizon, deadline))
    blocked = [k for k, state in enumerate(timeline) if any(state[t["name"]] == "B" for t in task_list)]
    for task in task_list:
        mine = [k for k in blocked if timeline[k][task["name"]] == "B"]
        if mine:
            lower = [k for k in mine if any(timeline[k][o["name"]] in "=" and o["prio"] < task["prio"]
                                            and not any(w == "m" for w, _ in o["work"]) for o in task_list)]
            print("%s blocked on M for %d ticks, %d of them while a lower-priority task outside M ran"
                  % (task["name"], len(mine), len(lower)))
    print("deadline misses: ((misses: %d))   law == 0   %s" % (miss_n, "kept" if not miss_n else "BROKEN"))


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in CHOICE_DB:
        print("choices: %s" % ", ".join(CHOICE_DB))
        sys.exit(1)
    main(choice)
    print("<hwut-end>")
