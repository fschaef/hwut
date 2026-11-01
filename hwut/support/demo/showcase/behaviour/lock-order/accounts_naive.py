"""accounts_naive.py -- BROKEN FIXTURE: a 'small cleanup' of accounts.py that
takes the locks in the order the transfer names the accounts: source first,
then destination. Every test of single transfers passes; three threads
moving money around a ring can deadlock -- the backoff turns the deadlock
into a stall, and the stall into nothing anybody sees.
"""
from accounts import Bank as _Bank


class Bank(_Bank):
    def lock_order(self, src, dst):
        return [src, dst]                       # <-- the cleanup
