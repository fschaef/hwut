"""numfmt.py -- number formatting for invoices, configured per locale.

BUG (as found): the separators are configured ONCE per process -- the
first locale wins, later calls of configure() are ignored. In a program
that serves one locale per process nobody notices.
"""
_separators = None


def configure(locale):
    global _separators
    if _separators is None:
        _separators = {"de": (".", ","), "en": (",", "."), "ch": ("'", ".")}[locale]


def fmt(x):
    group, point = _separators
    whole, frac = ("%.2f" % x).split(".")
    digits = ""
    for i, d in enumerate(reversed(whole)):
        if i and i % 3 == 0:
            digits = group + digits
        digits = d + digits
    return digits + point + frac
