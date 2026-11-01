"""accounts.py -- money transfers between accounts, one lock per account.

THE RULE of this code base: a thread that needs several account locks takes
them in the order of the account names. A lock that is not free within
50 ms makes the transfer let go of everything it holds and try again (a
'try-lock with backoff'), so a lock-order mistake does not hang the
process -- it only costs latency, and nobody notices it. That is why the
order is checked by a test.
"""
import random
import time


class LockTimeout(Exception):
    pass


class Bank:
    def __init__(self, balance_db, make_lock):
        self.balance_db = dict(balance_db)
        self.lock_db = dict((name, make_lock(name)) for name in balance_db)

    def lock_order(self, src, dst):
        """RETURN: the order in which the two locks are taken."""
        return sorted([src, dst])

    def transfer(self, src, dst, amount):
        held = self._take(self.lock_order(src, dst))
        try:
            self.balance_db[src] -= amount
            self.balance_db[dst] += amount
        finally:
            for name in reversed(held):
                self.lock_db[name].release()

    def _take(self, name_list):
        while True:
            held = []
            try:
                for name in name_list:
                    if not self.lock_db[name].acquire(timeout=0.05):
                        raise LockTimeout(name)
                    held.append(name)
                return held
            except LockTimeout:
                for name in reversed(held):
                    self.lock_db[name].release()
                time.sleep(random.uniform(0.0, 0.01))
