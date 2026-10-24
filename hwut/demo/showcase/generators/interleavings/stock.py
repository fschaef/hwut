"""stock.py -- reserving the last item of a web shop's stock, cut into
atomic steps. A reservation is a generator: every 'next()' performs ONE
step and yields its name; another reservation may run between two steps.

    reserve_check_then_act   page: show n; then SELECT n, check n >= 1; then
                             UPDATE n = <n read> - 1 -- the check and the
                             write are two statements
    reserve_conditional      UPDATE n = n - 1 WHERE n >= 1 -- the check and
                             the write are ONE statement; the read before
                             it only fills the order page
"""


class Stock:
    def __init__(self, n):
        self.n = n
        self.confirmed = []


def reserve_check_then_act(stock, who):
    yield "p%d" % stock.n
    seen = stock.n
    ok = seen >= 1;               yield "c%d" % seen
    if ok:
        stock.n = seen - 1
        stock.confirmed.append(who)
    yield "w%d" % stock.n if ok else "x"


def reserve_conditional(stock, who):
    yield "p%d" % stock.n
    ok = stock.n >= 1
    if ok:
        stock.n -= 1
        stock.confirmed.append(who)
    yield "u" + ("+" if ok else "-")
    yield "ok" if ok else "x"
