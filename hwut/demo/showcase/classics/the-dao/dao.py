"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________
dao.py -- a contract that holds ether for its members and pays a member's
balance out on request, modelled on The DAO's 'splitDAO' (June 2016).

    Contract(variant)      'june-2016'      pays, THEN zeroes the balance
                           'checks-effects' zeroes the balance, then pays
                           'mutex'          pays, then zeroes -- but refuses
                                            a call while one is running
    .deposit(member, ether)
    .withdraw(member)      pays the member's whole balance by calling the
                           member's 'receive' -- code of the member's own,
                           which may call 'withdraw' again before it returns

Every step is reported to 'log(depth, text)', so a test can draw the call
stack as it happened.
______________________________________________________________________________
"""


class Contract:
    """The ether a contract holds, and what it owes each member."""

    def __init__(self, variant, log):
        """RETURN: None. An empty contract of 'variant'."""
        self.variant  = variant
        self.log      = log
        self.held     = 0              # ether the contract holds
        self.balance  = {}             # member -> ether owed
        self.member   = {}             # name -> member object
        self.busy     = False          # the mutex variant's lock
        self.depth    = 0

    def deposit(self, member, ether):
        """RETURN: None. 'member' pays 'ether' in."""
        self.member[member.name] = member
        self.balance[member.name] = self.balance.get(member.name, 0) + ether
        self.held += ether

    def withdraw(self, name):
        """
        RETURN: int, the ether paid by this call itself (not counting the
                calls it led to); 0 where nothing was owed, the contract
                could not pay, or a reentrant call was refused.
        """
        self.depth += 1
        try:
            amount = self.balance.get(name, 0)
            self.log(self.depth, "withdraw(%s)   owed %d" % (name, amount))
            if self.variant == "mutex" and self.busy:
                self.log(self.depth, "  refused: a withdraw is still running")
                return 0
            if amount == 0 or amount > self.held:
                self.log(self.depth, "  nothing paid" if amount == 0 else
                         "  cannot pay: the contract holds %d" % self.held)
                return 0
            if self.variant == "checks-effects":
                self.balance[name] = 0                 # effect first ...
            self.busy = True
            try:
                self.held -= amount
                self.log(self.depth, "  pay %d -> %s.receive()" % (amount, name))
                self.member[name].receive(self, amount)  # ... interaction last
            finally:
                self.busy = False
            if self.variant != "checks-effects":
                self.balance[name] = 0                 # june-2016: too late
            return amount
        finally:
            self.depth -= 1


class Member:
    """A member that takes the ether and returns."""

    def __init__(self, name):
        """RETURN: None."""
        self.name, self.received = name, 0

    def receive(self, contract, amount):
        """RETURN: None. Takes 'amount'."""
        self.received += amount


class Attacker(Member):
    """A member whose 'receive' calls 'withdraw' again -- up to 'reenter_n'
    times -- before it returns."""

    def __init__(self, name, reenter_n):
        """RETURN: None."""
        Member.__init__(self, name)
        self.reenter_n = reenter_n

    def receive(self, contract, amount):
        """RETURN: None. Takes 'amount', and asks again while it may."""
        self.received += amount
        if self.reenter_n > 0:
            self.reenter_n -= 1
            contract.withdraw(self.name)
