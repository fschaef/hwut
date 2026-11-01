"""account.py -- the withdrawal of a cash-machine back end, cut into its
atomic steps. A withdrawal is a generator: every 'next()' performs ONE
step on the shared account and yields the step's name. Between two steps
another withdrawal may run -- that is all a thread switch can do.

    withdraw_unlocked   check-then-act: read, check, write -- the code as it
                        was written first
    withdraw_locked     the same steps inside the account's lock; a step
                        that finds the lock taken yields 'wait' and stays
                        where it is
"""


class Account:
    def __init__(self, balance):
        self.balance   = balance
        self.lock_by   = None          # name of the holder, or None
        self.dispensed = []            # (who, amount) -- the cash that left


def withdraw_unlocked(account, who, amount):
    yield "begin"
    seen = account.balance;                       yield "read %d" % seen
    ok = seen >= amount;                          yield "check %s" % ("ok" if ok else "NO")
    if ok:
        account.balance = seen - amount
        account.dispensed.append((who, amount));  yield "write %d" % account.balance
    else:                                         yield "refuse"
    yield "end"


def withdraw_locked(account, who, amount):
    while account.lock_by is not None:            yield "wait"
    account.lock_by = who;                        yield "lock"
    seen = account.balance;                       yield "read %d" % seen
    ok = seen >= amount;                          yield "check %s" % ("ok" if ok else "NO")
    if ok:
        account.balance = seen - amount
        account.dispensed.append((who, amount));  yield "write %d" % account.balance
    else:                                         yield "refuse"
    account.lock_by = None;                       yield "unlock"
