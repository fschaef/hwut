#! /usr/bin/env python3
"""invoice.py -- the invoice tool: one line per item, VAT per line.

    python3 invoice.py < invoice.csv

Amounts are decimal; every amount is rounded to the cent half-up
('kaufmaennisch'): net = qty x price, VAT = net x rate, gross = net + VAT,
each rounded once, the totals being sums of the rounded amounts."""
import sys
from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")


def cents(value):
    """RETURN: 'value' rounded half-up to the cent."""
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


total_net = total_vat = Decimal(0)
for line in sys.stdin:
    if line.startswith("#") or line.count(";") < 3:
        continue
    item, qty, price, rate = line.rstrip("\n").split(";")
    net = cents(Decimal(qty) * Decimal(price))
    vat = cents(net * Decimal(rate) / 100)
    print("%s;%s;%s;%s" % (item, net, vat, net + vat))
    total_net += net
    total_vat += vat
print("TOTAL;%s;%s;%s" % (total_net, total_vat, total_net + total_vat))
