"""rtkernel.py -- the scheduling core of a small RTOS, one tick at a time.

Fixed priorities, preemptive: in every tick the ready job with the highest
EFFECTIVE priority runs. Jobs share one mutex 'M'. With protocol
'inheritance', a job holding M runs at the priority of the highest job
blocked on M (priority inheritance); with protocol 'none' it keeps its own.

A task:  name, prio (higher runs first), first release, period (0: once),
         relative deadline, work -- a list of (kind, ticks) with kind 'c'
         (compute) or 'm' (compute while holding M).
run() returns, per tick, the state of every task:
         '=' running   'm' running inside M   '-' ready, preempted
         'B' blocked on M   '.' nothing to do
and the events: (tick, task, 'release' | 'done' | 'miss').
"""


class Job:
    def __init__(self, task, release):
        self.task, self.release = task, release
        self.work = [list(seg) for seg in task["work"]]
        self.missed = False


def run(task_list, protocol, horizon):
    jobs, owner, timeline, event_list = [], None, [], []
    for t in range(horizon):
        for task in task_list:
            first, period = task["release"], task["period"]
            if t == first or (period and t > first and (t - first) % period == 0):
                jobs.append(Job(task, t))
                event_list.append((t, task["name"], "release"))

        def effective(job):
            prio = job.task["prio"]
            if protocol == "inheritance" and job is owner:
                for other in jobs:
                    if other is not job and other.work and other.work[0][0] == "m":
                        prio = max(prio, other.task["prio"])
            return prio

        state = dict((task["name"], ".") for task in task_list)
        for job in jobs:
            state[job.task["name"]] = "-"
        runner = None
        for job in sorted(jobs, key=effective, reverse=True):
            kind = job.work[0][0]
            if kind == "m" and owner not in (None, job):
                state[job.task["name"]] = "B"
                continue
            runner = job
            break
        if runner:
            kind = runner.work[0][0]
            if kind == "m":
                owner = runner
            state[runner.task["name"]] = "m" if kind == "m" else "="
        for job in jobs:
            if job is not runner and job.work[0][0] == "m" and owner not in (None, job):
                state[job.task["name"]] = "B"
        if runner:
            runner.work[0][1] -= 1
            if runner.work[0][1] == 0:
                runner.work.pop(0)
                if kind == "m":
                    owner = None
            if not runner.work:
                jobs.remove(runner)
                event_list.append((t + 1, runner.task["name"], "done"))
        for job in jobs:
            if not job.missed and t + 1 >= job.release + job.task["deadline"]:
                job.missed = True
                event_list.append((t + 1, job.task["name"], "miss"))
        timeline.append(state)
    return timeline, event_list
