#! /usr/bin/env python3
# @hwut {
#     title    = "Knight Capital (2012): one of eight servers kept the old code, and a reused flag meant Power Peg"
#     choices {
#         deployed-2012 { features = ["release-table", "shares-per-server", "overfill-named"]
#                         tolerance { constraints = ["overfill > 0"] } }
#         all-updated   { features = ["release-table", "shares-per-server", "no-overfill"]
#                         tolerance { constraints = ["overfill == 0", "releases == 1"] } }
#         flag-retired  { features = ["release-table", "shares-per-server", "no-overfill"]
#                         tolerance { constraints = ["overfill == 0"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  the shares eight routing servers send to market for the same
         parent orders, per server, beside the release each one runs
HISTORY  On 1 August 2012 Knight Capital began routing orders for the NYSE
Retail Liquidity Program. The new code had been deployed to seven of the
eight servers of its router SMARS; on the eighth the old code still stood.
The new code reused a flag that in the old code had activated 'Power Peg',
a function unused for years, whose check of the shares already filled had
been moved away. On the eighth server every RLP parent order started Power
Peg, which sent child orders without end. In about 45 minutes Knight
accumulated unwanted positions and lost about 440 million US dollars (the
SEC's order of October 2013 tells the story).

REQUIREMENT  Every server of a deployment runs the same release, and a
             parent order of N shares yields at most N shares of child
             orders.

THE UNIT  '../smars.py': route(release, flag_word, parent_shares, step_max)
-- 'rlp-2012' and 'old-2003', the flag bit 0x01 reused, or a fresh bit
0x02. A child order is 100 shares and fills at once; 'step_max' = 40 stands
in for the minutes until a person stopped the router.

THE ORDERS  Every server routes the same three RLP parent orders, of 300,
1000 and 2500 shares.

WHAT THE TEST PRINTS
  1. THE DEPLOYMENT: per server its release.
  2. PER SERVER the shares ordered and sent, the overfill, and a bar of
     the shares sent ('#' = 500 shares).

CHOICES
    deployed-2012  server 8 runs 'old-2003', the flag is 0x01: Power Peg
                   sends 40 child orders for each parent order.
    all-updated    all eight run 'rlp-2012': one release, no overfill.
    flag-retired   server 8 still runs 'old-2003', but RLP asks by the
                   fresh bit 0x02, which the old code does not know: it
                   routes plainly, no overfill -- two releases still stand.

HOW TO READ THE GOOD  The table stands in '##! verbatim', every number
exact. Bindings: '((overfill: N))' shares sent beyond the shares ordered,
all servers together -- law '> 0' for deployed-2012, '== 0' else;
'((releases: N))' the releases deployed, law '== 1' where all is updated.
______________________________________________________________________________
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from smars import route, FLAG_RLP_REUSED, FLAG_RLP_NEW                # noqa: E402

PARENT_LIST = [300, 1000, 2500]
STEP_MAX    = 40
CHOICE_DB   = {"deployed-2012": (["rlp-2012"] * 7 + ["old-2003"], FLAG_RLP_REUSED),
               "all-updated":   (["rlp-2012"] * 8,                FLAG_RLP_REUSED),
               "flag-retired":  (["rlp-2012"] * 7 + ["old-2003"], FLAG_RLP_NEW)}


def main(choice):
    """RETURN: int, 0 once the deployment and the shares are printed."""
    release_list, flag_word = CHOICE_DB[choice]
    ordered = sum(PARENT_LIST)
    print("choice %s: RLP orders carry flag word 0x%02x" % (choice, flag_word))
    print()
    print("1. THE DEPLOYMENT")
    print("##! verbatim")
    for k, release in enumerate(release_list):
        print("   server %d  %s" % (k + 1, release))
    print("####")
    releases = len(set(release_list))
    print("   releases deployed ((releases: %d))" % releases)
    print()
    print("2. SHARES PER SERVER, three parent orders of %s shares" % ", ".join(map(str, PARENT_LIST)))
    print("##! verbatim")
    print("   server  release    ordered     sent   overfill")
    overfill = 0
    for k, release in enumerate(release_list):
        sent = sum(route(release, flag_word, shares, STEP_MAX) for shares in PARENT_LIST)
        over = max(0, sent - ordered)
        overfill += over
        print(("   %6d  %-9s  %7d  %7d  %9d  %s"
               % (k + 1, release, ordered, sent, over, "#" * (sent // 500))).rstrip())
    print("####")
    print("   ('#' = 500 shares sent)")
    if choice == "deployed-2012":
        print("   shares beyond the orders ((overfill: %d))   law > 0   the failure, reproduced" % overfill)
    else:
        print("   shares beyond the orders ((overfill: %d))   law == 0   %s"
              % (overfill, "kept" if overfill == 0 else "BROKEN"))
    return 0


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in CHOICE_DB:
        print("choices: %s" % ", ".join(CHOICE_DB))
        sys.exit(1)
    status = main(choice)
    print("<hwut-end>")
    sys.exit(status)
