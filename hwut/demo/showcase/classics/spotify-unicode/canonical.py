"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________
canonical.py -- the canonical form of a user name: the key under which an
account is found, so that 'BigBird' and 'bigbird' are one account.

    canonical(name, variant)
        'nodeprep-2013'  casefold, then NFKC -- the order that is wrong:
                         NFKC can turn a character into an UPPER-case one
                         ('ᴮ' MODIFIER LETTER CAPITAL B -> 'B') after the
                         folding is done
        'nfkc-casefold'  NFKC, casefold, NFKC -- folded after the last
                         character that normalisation can bring in
______________________________________________________________________________
"""
import unicodedata


def canonical(name, variant):
    """
    RETURN: str, the canonical form of 'name' under 'variant'.
    """
    if variant == "nodeprep-2013":
        return unicodedata.normalize("NFKC", name.casefold())
    return unicodedata.normalize("NFKC",
                                 unicodedata.normalize("NFKC", name).casefold())
