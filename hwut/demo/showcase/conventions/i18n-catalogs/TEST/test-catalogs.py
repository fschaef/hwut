#! /usr/bin/env python3
#
# @hwut {
#     title    = "i18n: every message key in every language, with the same placeholders"
#     features = ["complete", "placeholders", "no-stale"]
#     choices {
#         good   { tolerance { constraints = ["gaps == 0"] } }
#         broken { tolerance { constraints = ["gaps > 0"] } }
#     }
# }
#
"""
______________________________________________________________________________
SUBJECT  the key x language matrix of one set of message catalogues
         (good/broken)
REQUIREMENT: English (en.json) is the source catalogue. For every other
language catalogue in locales/:

    I1  every key of en.json is there                      (else MISSING)
    I2  its text is not empty                              (else EMPTY)
    I3  it carries the same placeholders, '{count}' etc.   (else {..}!)
        -- a translated placeholder '{prozent}' crashes the formatter at
        run time, in German only, on the battery screen only.
    I4  it has no key that en.json does not have           (else STALE)

HOW: the catalogues are JSON; the test reads them and prints the MATRIX,
keys down (in the order of en.json, stale keys below a rule), languages
across. 'ok' where all four rules hold. Below it, the coverage per language
and the detail of every placeholder mismatch: what the source has, what the
translation has.

CHOICES
    good     ten keys in en, de, fr, es -- all 'ok'.
    broken   fr lost two keys; de translated a placeholder and kept an old
             key 'menu.close'; es has an empty 'button.ok'.

HWUT CONCEPTS
    constraints  'gaps': the number of cells that are not 'ok'. 'gaps == 0'
                 for good is the requirement; 'gaps > 0' for broken -- the
                 violation is reported, the matrix says where. Key and
                 language counts are exact text ('keys: 10', 'languages:
                 4'): a wrong glob, which yields an empty and perfect
                 matrix, changes them.
    exact lines  the matrix; the catalogues' non-ASCII text (accents, umlauts,
                 the Spanish question mark) passes through hwut
                 untouched -- it is only text.

READING THE GOOD: every column of the matrix should read 'ok' top to bottom.
______________________________________________________________________________
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def placeholders(text):
    return sorted(set(re.findall(r"\{(\w+)\}", text)))


def main(choice):
    directory = os.path.join(HERE, "..", choice, "locales")
    catalog_db = {os.path.splitext(f)[0]: json.load(open(os.path.join(directory, f), encoding="utf-8"))
                  for f in sorted(os.listdir(directory)) if f.endswith(".json")}
    source = catalog_db["en"]
    language_list = [l for l in catalog_db if l != "en"]
    stale_list = sorted({k for l in language_list for k in catalog_db[l] if k not in source})

    print("catalogues of '%s': en (source) + %s" % (choice, " ".join(language_list)))
    print()
    print("MATRIX   ok | MISSING | EMPTY | {..}! placeholder differs | STALE key not in en")
    print("         | . not applicable: the key is not in en, so its absence is no gap")
    print("%-22s %-8s" % ("key", "en") + "".join("%-9s" % l for l in language_list).rstrip())
    gaps, detail_list = 0, []
    for key in list(source) + ["----- not in en -----"] + stale_list:
        if key.startswith("-----"):
            if stale_list:
                print(key)
            continue
        cell_list = []
        for l in language_list:
            text = catalog_db[l].get(key)
            if key not in source:
                cell = "STALE" if text is not None else "."
            elif text is None:
                cell = "MISSING"
            elif not text.strip():
                cell = "EMPTY"
            elif placeholders(text) != placeholders(source[key]):
                cell = "{..}!"
                detail_list.append("%s %s: en {%s}  %s {%s}" % (
                    l, key, "} {".join(placeholders(source[key])), l, "} {".join(placeholders(text))))
            else:
                cell = "ok"
            gaps += cell not in ("ok", ".")
            cell_list.append(cell)
        en = "src" if key in source else "-"
        print("%-22s %-8s" % (key, en) + "".join("%-9s" % c for c in cell_list).rstrip())
    print()
    print("COVERAGE  keys of en translated, per language")
    for l in language_list:
        done = sum(1 for k in source if catalog_db[l].get(k, "").strip()
                   and placeholders(catalog_db[l][k]) == placeholders(source[k]))
        bar = "#" * done + "." * (len(source) - done)
        print("  %-3s [%s] %2d of %d" % (l, bar.replace("#", "="), done, len(source)))
    for d in detail_list:
        print("PLACEHOLDER " + d)
    print()
    print("keys: %d   languages: %d   gaps ((gaps: %d))   law == 0   %s"
          % (len(source), len(catalog_db), gaps, "kept" if gaps == 0 else "BROKEN"))


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in ("good", "broken"):
        print("choices: good, broken")
        sys.exit(1)
    main(choice)
    print("<hwut-end>")
