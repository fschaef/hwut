#! /usr/bin/env python3
# @hwut {
#     title    = "Spotify (2013): a user name's canonical form that changed when taken again"
#     choices {
#         nodeprep-2013 { features = ["names-tabled", "one-account-two-keys", "not-idempotent-named"]
#                         tolerance { constraints = ["nonidempotent > 0", "shared > 0"] } }
#         nfkc-casefold { features = ["names-tabled", "one-account-two-keys", "idempotent"]
#                         tolerance { constraints = ["nonidempotent == 0", "shared == 0"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  the canonical form of user names -- once, and taken again -- and
         which distinct registered names end up under one account key
HISTORY  In June 2013 Spotify described on its engineering blog how user
names had been canonicalised so that look-alike spellings meet at one
account: a library function was applied to the name, and the result was
the key. For some Unicode characters the function was not idempotent:
'ᴮᴵᴳᴮᴵᴿᴰ' (modifier letters) gave 'BIGBIRD', and 'BIGBIRD' given again
gave 'bigbird'. A name canonicalised once at sign-up and once more later
-- in a password reset -- could thus reach another user's account.

REQUIREMENT  canonical(canonical(x)) == canonical(x) for every name, and
             two names registered as different accounts never meet under
             one key later.

THE UNIT  '../canonical.py': 'nodeprep-2013' folds the case, then applies
NFKC (which can bring in upper-case letters after the folding);
'nfkc-casefold' applies NFKC, folds, and applies NFKC again.

WHAT THE TEST PRINTS
  1. THE NAMES: per name its canonical form once and twice, '!!' where the
     two differ. The names are a space of spellings: plain, fullwidth,
     modifier letters, ligatures, sharp s, a titlecase digraph, a dotted
     capital I.
  2. ONE ACCOUNT, TWO NAMES: pairs of names registered as two accounts
     (their keys differ once) whose keys are equal when taken twice.
  3. The bindings '((nonidempotent: N))' and '((shared: N))'.

CHOICES
    nodeprep-2013  the modifier-letter spellings move on the second pass;
                   they meet the plain accounts.
    nfkc-casefold  every key is a fixed point; no two accounts meet.

HOW TO READ THE GOOD  Exact; the file is UTF-8. A '!!' row is a name whose
key is not stable. Laws: '> 0' for 2013 -- the violation report --,
'== 0' for the fix.
______________________________________________________________________________
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from canonical import canonical                     # noqa: E402

CHOICE_LIST = ["nodeprep-2013", "nfkc-casefold"]
NAME_LIST = ["bigbird", "BigBird", "ＢｉｇＢｉｒｄ", "ᴮᴵᴳᴮᴵᴿᴰ",
             "admin", "ᴬᴰᴹᴵᴺ", "ﬁona", "fiona", "Straße", "strasse",
             "ǅemal", "džemal", "İlknur"]


def run(variant):
    """RETURN: None. Prints the table, the shared accounts and the
    bindings for 'variant'."""
    sys.stdout.reconfigure(encoding="utf-8")
    once_db  = {name: canonical(name, variant) for name in NAME_LIST}
    twice_db = {name: canonical(once_db[name], variant) for name in NAME_LIST}
    print("canonical.py variant '%s'   %d names" % (variant, len(NAME_LIST)))
    print()
    print("1. THE NAMES: name -> key once -> key twice")
    print("##! verbatim")
    for name in NAME_LIST:
        mark = "   !!" if once_db[name] != twice_db[name] else ""
        print("   %-14s %-14s %s%s" % (name, once_db[name], twice_db[name], mark))
    print("####")
    shared = []
    for i, a in enumerate(NAME_LIST):
        for b in NAME_LIST[i + 1:]:
            if once_db[a] != once_db[b] and twice_db[a] == twice_db[b]:
                shared.append((a, b))
    print()
    print("2. ONE ACCOUNT, TWO NAMES (different keys once, one key twice)")
    print("##! verbatim")
    for a, b in shared:
        print("   %s  and  %s   -> %s" % (a, b, twice_db[a]))
    if not shared:
        print("   none")
    print("####")
    nonidempotent = sum(once_db[n] != twice_db[n] for n in NAME_LIST)
    print()
    print("keys that change when taken again ((nonidempotent: %d))   law == 0   %s"
          % (nonidempotent, "kept" if nonidempotent == 0 else "BROKEN"))
    print("pairs of accounts that meet       ((shared: %d))   law == 0   %s"
          % (len(shared), "kept" if not shared else "BROKEN"))


choice = sys.argv[1] if len(sys.argv) > 1 else ""
if choice not in CHOICE_LIST:
    print("choices: %s" % ", ".join(CHOICE_LIST))
    sys.exit(1)
run(choice)
print("<hwut-end>")
