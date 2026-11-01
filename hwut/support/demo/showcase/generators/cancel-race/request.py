"""request.py -- an outstanding RPC request of a client library. The reply
may complete it while the caller cancels it (time-out, user abort). Both
paths are generators of atomic steps; another may run between two steps.

    *_check_then_set   look at the state in one step, set it and notify
                       in the next -- as first written
    *_atomic           compare-and-set of the state in ONE step; the
                       notification follows in the next
Notification = the user's callback AND the release of the connection
slot back to the pool.
"""


class Request:
    def __init__(self):
        self.state    = "pending"
        self.callback = []           # what the user was told, in order
        self.released = 0            # connection slots handed back


def complete_check_then_set(r, value):
    pending = r.state == "pending";          yield "look " + r.state
    if pending:
        r.state = "done"
        r.callback.append("done(%s)" % value); r.released += 1;  yield "notify done"
    else:                                     yield "drop reply"


def cancel_check_then_set(r):
    pending = r.state == "pending";          yield "look " + r.state
    if pending:
        r.state = "cancelled"
        r.callback.append("cancelled");       r.released += 1;  yield "notify cancel"
    else:                                     yield "too late"


def complete_atomic(r, value):
    won = r.state == "pending"
    if won: r.state = "done"
    yield "cas " + ("won" if won else "lost")
    if won:
        r.callback.append("done(%s)" % value); r.released += 1;  yield "notify done"
    else:                                     yield "drop reply"


def cancel_atomic(r):
    won = r.state == "pending"
    if won: r.state = "cancelled"
    yield "cas " + ("won" if won else "lost")
    if won:
        r.callback.append("cancelled");       r.released += 1;  yield "notify cancel"
    else:                                     yield "too late"
