#! /usr/bin/env python3
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
"""
book_stain -- converts the books of a tree to the one 'stain' column (B-18).

    python3 vut/adm/book_stain.py <directory>            # says what it would do
    python3 vut/adm/book_stain.py <directory> --apply    # does it

Every 'GOOD/book.csv' below <directory> whose header carries the columns
'stain_repeat_n' and 'stain_when' is rewritten with ONE column 'stain' in
their place: a count N becomes 'N repeat'; the instant is dropped. Every
other line -- the register's comment line, the other columns, a row that
ends before its last columns (B-9) -- is kept as it stands. A book already
in the new form is left alone, so a second run does nothing.

ONCE, BEFOREHAND: the framework reads the new form only.
"""
import os
import sys

OLD_PAIR  = ("stain_repeat_n", "stain_when")
NEW_NAME  = "stain"
BOOK_NAME = "book.csv"


def converted_text(text):
    """
    RETURN: str, the book 'text' with the two stain columns joined into
            'stain'.
            None, the book carries no 'stain_repeat_n' column: nothing to do.
    """
    line_list = text.split("\n")
    head_i = next((i for i, line in enumerate(line_list)
                   if line and not line.startswith("#")), None)
    if head_i is None: return None
    head = line_list[head_i].split(";")
    if OLD_PAIR[0] not in head: return None
    count_i = head.index(OLD_PAIR[0])
    when_i  = head.index(OLD_PAIR[1]) if OLD_PAIR[1] in head else None
    result  = []
    for i, line in enumerate(line_list):
        if i < head_i or not line or line.startswith("#"):
            result.append(line)
            continue
        cell_list = line.split(";")
        if i == head_i:
            cell_list[count_i] = NEW_NAME
        elif count_i < len(cell_list) and cell_list[count_i]:
            cell_list[count_i] = "%s repeat" % cell_list[count_i]
        if when_i is not None and when_i < len(cell_list):
            del cell_list[when_i]
        #  A ROW ENDS WITH ITS LAST FACT (B-9).
        while i != head_i and cell_list and cell_list[-1] == "":
            cell_list.pop()
        result.append(";".join(cell_list))
    return "\n".join(result)


def book_path_list(directory):
    """RETURN: list[str], every 'GOOD/book.csv' below 'directory', sorted."""
    result = []
    for root, dir_list, file_list in os.walk(directory):
        dir_list[:] = sorted(d for d in dir_list if not d.startswith("."))
        if os.path.basename(root) == "GOOD" and BOOK_NAME in file_list:
            result.append(os.path.join(root, BOOK_NAME))
    return result


def main(argv):
    """RETURN: int, 0 done; 2 the command line cannot be read."""
    word_list = [a for a in argv if not a.startswith("--")]
    apply_f   = "--apply" in argv
    if len(word_list) != 1 or not os.path.isdir(word_list[0]):
        print(__doc__.strip().split("\n\n")[1])
        return 2
    changed_n = 0
    for path in book_path_list(word_list[0]):
        with open(path, encoding="utf-8") as fh: text = fh.read()
        new = converted_text(text)
        if new is None: continue
        changed_n += 1
        print("%s  %s" % ("converted" if apply_f else "would convert", path))
        if apply_f:
            with open(path, "w", encoding="utf-8") as fh: fh.write(new)
    print("%d book(s) %s" % (changed_n, "converted" if apply_f
                                         else "to convert (--apply)"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
