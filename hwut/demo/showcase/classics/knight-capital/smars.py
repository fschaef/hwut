"""
______________________________________________________________________________
smars.py -- a router as Knight Capital's SMARS routed parent orders on
1 August 2012: one parent order is cut into child orders sent to market.

    route(release, flag_word, parent_shares, step_max)

Two releases of the router stood that morning:

    'rlp-2012'  the new code for the Retail Liquidity Program. Bit 0x01 of
                the flag word asks for RLP routing: child orders until the
                parent's shares are filled -- the filled shares counted.
    'old-2003'  the old code. Bit 0x01 still meant 'Power Peg', a test
                function unused since 2003. Its stop -- the count of shares
                already filled -- had been moved elsewhere in 2005, so
                Power Peg sends child orders and never stops on its own.

A child order is CHILD_SHARES shares and fills at once. 'step_max' stands
in for the time it took a person to stop the router: no route sends more
child orders than that.

A third word: 'rlp-2012-new-flag' asks for RLP by a fresh bit, 0x02. To
the old code 0x02 means nothing, and it routes the order plainly, with the
filled shares counted.
______________________________________________________________________________
"""
CHILD_SHARES = 100

FLAG_RLP_REUSED = 0x01         # the bit that once meant Power Peg
FLAG_RLP_NEW    = 0x02         # a bit no release had used


def route(release, flag_word, parent_shares, step_max):
    """
    RETURN: int, the shares the router sent to market in child orders for
            one parent order of 'parent_shares', within 'step_max' child
            orders.
    """
    sent = 0
    for _ in range(step_max):
        if release == "old-2003" and flag_word & FLAG_RLP_REUSED:
            sent += CHILD_SHARES                # Power Peg: no stop
            continue
        if sent >= parent_shares:               # RLP, or a plain order:
            break                               # the fills are counted
        sent += min(CHILD_SHARES, parent_shares - sent)
    return sent
