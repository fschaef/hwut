"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE IDENTIFIERS OF A COVERAGE OUTPUT (coverage D-42): test run
         ids and test run group ids, numbers in base 64 written at one
         width.

    0-9  A-Z  _  a-z  ~        the digits, in ASCII order

SORTING THE TEXT SORTS THE NUMBERS where every identifier of an output
stands at the same width, and none of the formats' own signs (',', ';',
':', '@', '*', '+') is a digit.
______________________________________________________________________________
"""

DIGITS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefghijklmnopqrstuvwxyz~"
BASE   = len(DIGITS)


def id_text(number, width):
    """
    RETURN: str, 'number' in base 64, padded with '0' to 'width' digits.
    """
    digit_list = []
    while True:
        number, rest = divmod(number, BASE)
        digit_list.append(DIGITS[rest])
        if number == 0: break
    return "".join(reversed(digit_list)).rjust(width, DIGITS[0])


def id_number(text):
    """
    RETURN: int, the number the base-64 identifier 'text' spells.

    Raises ValueError where a character is no digit of the alphabet.
    """
    number = 0
    for character in text:
        number = number * BASE + DIGITS.index(character)
    return number


def group_id_start(run_n):
    """
    RETURN: int, the first group id of an output holding 'run_n' test
            runs: the next ROUND value above the last test run id --
            'g00' after 'f2g', '10' after any single digit.
    """
    last  = max(run_n - 1, 0)
    scale = BASE
    while scale * BASE <= last: scale *= BASE
    return (last // scale + 1) * scale
