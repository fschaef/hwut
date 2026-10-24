"""account.py -- the account aggregate: decides commands from its events.

State is never stored, only derived: replaying the events gives the status
(none, active, frozen, closed) and the balance. A command is checked against
that state and, if allowed, becomes one event appended at the version it was
decided on. On a version conflict the command is decided again on the
fresh state.

    open | deposit n | withdraw n | freeze | unfreeze | close
"""
from eventstore import Conflict


def fold(event_list):
    status, balance = "none", 0
    for e in event_list:
        kind = e["type"]
        if kind == "opened":      status = "active"
        elif kind == "deposited": balance += e["amount"]
        elif kind == "withdrawn": balance -= e["amount"]
        elif kind == "frozen":    status = "frozen"
        elif kind == "unfrozen":  status = "active"
        elif kind == "closed":    status = "closed"
    return status, balance


def decide(status, balance, command, amount):
    """RETURN: the event, or raise ValueError(reason)."""
    if command == "open":
        if status != "none": raise ValueError("already open")
        return {"type": "opened"}
    if status == "none":   raise ValueError("not open")
    if status == "closed": raise ValueError("closed")
    if command == "deposit":
        return {"type": "deposited", "amount": amount}
    if command == "withdraw":
        if status == "frozen": raise ValueError("frozen")
        if amount > balance:   raise ValueError("insufficient funds")
        return {"type": "withdrawn", "amount": amount}
    if command == "freeze":   return {"type": "frozen"}
    if command == "unfreeze": return {"type": "unfrozen"}
    if command == "close":
        if balance != 0: raise ValueError("balance not zero")
        return {"type": "closed"}
    raise ValueError("unknown command")


def handle(store, stream, command, amount=0, between=None):
    """RETURN: 'accepted' or 'refused (<reason>)'. 'between' runs after the
    state was loaded and before the append -- where a concurrent writer
    would strike."""
    while True:
        event_list = store.load(stream)
        try:
            event = decide(*fold(event_list), command=command, amount=amount)
        except ValueError as reason:
            return "refused (%s)" % reason
        if between:
            between(); between = None
        try:
            store.append(stream, len(event_list), event)
            return "accepted"
        except Conflict:
            continue
