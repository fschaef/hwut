#! /usr/bin/env python3
# @hwut {
#     title    = "The DAO (2016): ether paid out before the balance was zeroed -- and the payee called again"
#     choices {
#         june-2016      { features = ["call-stack-drawn", "ledger-drawn", "reentrancy-drains"]
#                          tolerance { constraints = ["drained > 0", "unpaid > 0"] } }
#         checks-effects { features = ["call-stack-drawn", "ledger-drawn", "effects-first"]
#                          tolerance { constraints = ["drained == 0", "unpaid == 0"] } }
#         mutex          { features = ["call-stack-drawn", "ledger-drawn", "reentry-refused"]
#                          tolerance { constraints = ["drained == 0", "unpaid == 0"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  the calls a contract makes while four members take their ether
         out, drawn as a call stack, and the ledger afterwards
HISTORY  On 17 June 2016 an attacker moved about 3.6 million ether out of
The DAO, a fund run by a contract on Ethereum. Its 'splitDAO' function
paid a member's ether out BEFORE it set the member's balance to zero.
Paying ether to a contract runs that contract's code; the attacker's code
called 'splitDAO' again from inside the payment, found the balance not
yet zeroed, and was paid again -- and again. The Ethereum community undid
the theft by a hard fork in July 2016. The pattern is called REENTRANCY;
the rule against it, checks-effects-interactions: change the state first,
call out last.

REQUIREMENT  No member is ever paid more than it put in, and every member
             can take its ether out -- whatever a member's own code does
             while it is being paid.

THE UNIT  '../dao.py', the contract in three variants: as in June 2016
(pay, then zero the balance), checks-effects (zero, then pay), mutex (pay,
then zero, but refuse a withdraw while one is running). alice, bob and
carol put in 100, 50 and 70 ether; mallory puts in 20 and withdraws first.
Her 'receive' calls 'withdraw' again, up to 20 times, before it returns.
Then alice, bob and carol withdraw.

WHAT THE TEST PRINTS
  1. THE CALL STACK, one line per step, indented by its depth: a
     withdraw, what it is owed, what it pays and to whom.
  2. THE LEDGER: per member what it put in, what it received, what it is
     still owed; and what the contract holds.
  3. The bindings: '((drained: N))', ether paid to members beyond what
     they put in; '((unpaid: N))', ether members put in and could not
     take out.

CHOICES
    june-2016       mallory is paid 12 times; nothing is left for the rest.
    checks-effects  her second call finds a zero balance; everyone is paid.
    mutex           her second call is refused; everyone is paid.

HOW TO READ THE GOOD  All exact. In the stack, each deeper line is a call
made from inside the payment above it; under June 2016 they stack until
the contract is empty. Laws: 'drained > 0' for June 2016 -- the violation
report --, and 'unpaid > 0'; 'drained == 0' and 'unpaid == 0' for the
two fixes.
______________________________________________________________________________
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from dao import Contract, Member, Attacker            # noqa: E402

CHOICE_LIST = ["june-2016", "checks-effects", "mutex"]
DEPOSIT_DB  = {"alice": 100, "bob": 50, "carol": 70, "mallory": 20}


def run(variant):
    """RETURN: None. Plays the withdrawals under 'variant' and prints the
    call stack, the ledger and the bindings."""
    line_list = []
    contract  = Contract(variant, lambda depth, text:
                         line_list.append("  " * (depth - 1) + text))
    member_db = {name: Attacker(name, 20) if name == "mallory" else Member(name)
                 for name in DEPOSIT_DB}
    for name in ("alice", "bob", "carol", "mallory"):
        contract.deposit(member_db[name], DEPOSIT_DB[name])
    for name in ("mallory", "alice", "bob", "carol"):
        contract.withdraw(name)

    print("dao.py variant '%s'   deposits: %s   held %d"
          % (variant, ", ".join("%s %d" % pair for pair in DEPOSIT_DB.items()),
             sum(DEPOSIT_DB.values())))
    print()
    print("1. THE CALL STACK (deeper = called from inside the payment above)")
    print("##! verbatim")
    for line in line_list:
        print("   " + line)
    print("####")
    print()
    print("2. THE LEDGER (ether)")
    print("##! verbatim")
    print("   member     put in   received   still owed")
    for name, deposit in DEPOSIT_DB.items():
        print("   %-9s %7d %10d %12d" % (name, deposit, member_db[name].received,
                                        contract.balance.get(name, 0)))
    print("   contract holds %d" % contract.held)
    print("####")
    drained = sum(max(0, member_db[n].received - d) for n, d in DEPOSIT_DB.items())
    unpaid  = sum(max(0, d - member_db[n].received) for n, d in DEPOSIT_DB.items())
    print()
    print("paid beyond what was put in ((drained: %d))   law == 0   %s"
          % (drained, "kept" if drained == 0 else "BROKEN"))
    print("put in and not paid out     ((unpaid: %d))   law == 0   %s"
          % (unpaid, "kept" if unpaid == 0 else "BROKEN"))


choice = sys.argv[1] if len(sys.argv) > 1 else ""
if choice not in CHOICE_LIST:
    print("choices: %s" % ", ".join(CHOICE_LIST))
    sys.exit(1)
run(choice)
print("<hwut-end>")
