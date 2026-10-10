"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: ONE ID SCOPE, AND THE SPELLINGS OF AN ID -- the allocation law
         and the texts every numbered thing of the tree shares.

DESCRIPTION
       AN ID SCOPE is a counter. It starts at 'first' (0 or 1), issues
       the number above the highest it ever issued, and never issues a
       number twice (bookkeeper RATIONALE B-2).

           scope                 one per             first  kept in
           --------------------------------------------------------------
           test applications     TEST directory      0      GOOD/book.csv
           choices               test application    0      GOOD/book.csv
           test run groups       TEST directory      0      GOOD/group_ids.dat
           features              TEST directory      1      hwut-features.conf

           IdScope
               mark          the highest number ever issued; 'first - 1'
                             where none was
               next          mark + 1
               allocate()    mark + 1, issued; the mark rises
               give_back(n)  the mark steps back where n is still the
                             last issued, and stands otherwise
               raise_to(n)   the mark lifted to n, where n stands above
               ID_LIMIT      2**32; an allocation that would reach it is
                             refused, 'refusal_text()' naming the scope

       THE NAMES ARE NOT HERE. A scope issues and bounds numbers; which
       name a number carries, and in which file, is its owner's
       ('test_id_db.py', 'group_table.py', the feature file's reader).

       THE MARK LINE. Two files write the mark, each its own way:

           'N:<next>'            register and group table: the id the
                                 scope issues NEXT
           'issued = <mark>'     feature file: the highest id ISSUED

       'next_text()' writes the first, 'mark_text()' the second, and
       'mark_of_text()' reads the second back; the 'N:' line is parsed
       by its file's owner, whose fault wording it carries.

       THE SPELLINGS OF AN ID
           decimal            '47', and '47.66' for a test run with a
                              choice ('decimal_text', 'decimal_parts')
           base 64, at one    the identifiers of a coverage output
           width              ('id_text', 'id_number')

               0-9  A-Z  _  a-z  ~        the digits, in ASCII order

       SORTING THE TEXT SORTS THE NUMBERS where every identifier of an
       output stands at the same width, and none of the formats' own
       signs (',', ';', ':', '@', '*', '+') is a digit.
______________________________________________________________________________
"""

#  THE CEILING OF EVERY ID SCOPE (bookkeeper RATIONALE B-2). Ids are
#  never re-issued, so a scope's count only grows; 2**32 is more tests,
#  choices, groups or features than one directory will ever hold.
ID_LIMIT = 2 ** 32

DIGITS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefghijklmnopqrstuvwxyz~"
BASE   = len(DIGITS)


class IdScope:
    """One counter: the highest number it ever issued, and the law that
    the next one lies above it."""
    __slots__ = ("name", "first", "mark")

    def __init__(self, name, first=0, next_id=None):
        """
        RETURN: IdScope called 'name' (as its refusal spells it),
                counting from 'first'; it issues 'next_id' next, or
                'first' where 'next_id' is None.
        """
        self.name  = name
        self.first = first
        self.mark  = first - 1 if next_id is None else next_id - 1

    @property
    def next(self):
        """RETURN: int, the id this scope issues next (mark + 1)."""
        return self.mark + 1

    @next.setter
    def next(self, next_id):
        self.mark = next_id - 1

    def allocate(self):
        """
        RETURN: int, the newly issued id (mark + 1) if below ID_LIMIT;
                     the mark has risen to it
                None, else; the mark stands -- 'refusal_text()' says
                     why
        """
        if self.next >= ID_LIMIT: return None
        self.mark += 1
        return self.mark

    def give_back(self, number):
        """
        RETURN: True,  'number' was the last id issued; the mark stepped
                       back below it and the scope issues it again
                False, else; something was issued after it, the mark
                       stands and 'number' is retired
        """
        if number != self.mark: return False
        self.mark = number - 1
        return True

    def raise_to(self, number):
        """
        RETURN: True,  'number' stood above the mark; the mark is now
                       'number'
                False, else; the mark stands
        """
        if number <= self.mark: return False
        self.mark = number
        return True

    def issued_f(self, number):
        """
        RETURN: True,  'number' lies in what this scope may have issued:
                       first <= number <= mark
                False, else
        """
        return self.first <= number <= self.mark

    def refusal_text(self):
        """RETURN: str, the refusal of a scope at its ceiling, by name:
        '<name> has issued 4294967296 ids; no more are issued'."""
        return "%s has issued %i ids; no more are issued" \
               % (self.name, ID_LIMIT)

    # -- the mark line --------------------------------------------------
    def next_text(self):
        """RETURN: str, the id issued next, in decimal -- what stands
        behind 'N:'."""
        return "%i" % self.next

    def mark_text(self):
        """RETURN: str, the highest id issued, in decimal -- what stands
        behind 'issued ='."""
        return "%i" % self.mark

    def mark_of_text(self, text):
        """
        RETURN: True,  'text' spells a highest issued id that lies
                       within [first - 1, ID_LIMIT - 1]; it is taken
                False, else; the mark stands
        """
        number = number_of_decimal(text)
        if number is None or not self.first - 1 <= number < ID_LIMIT:
            return False
        self.mark = number
        return True


# -- decimal ------------------------------------------------------------
def number_of_decimal(text):
    """
    RETURN: int, the non-negative number 'text' spells in decimal digits
            None, else -- a sign, a blank inside, a letter, nothing
    """
    text = str(text).strip()
    if not text.isascii() or not text.isdigit(): return None
    return int(text)


def decimal_text(number, sub_number=None):
    """RETURN: str, '47' for a number alone, '47.66' with a number below
    it -- a test run id with a choice."""
    if sub_number is None: return "%i" % number
    return "%i.%i" % (number, sub_number)


def decimal_parts(text):
    """
    RETURN: (int, None), what '47' spells
            (int, int),  what '47.66' spells
            None, else
    """
    part_list = str(text).strip().split(".")
    try:
        if len(part_list) == 1: return int(part_list[0]), None
        if len(part_list) == 2: return int(part_list[0]), int(part_list[1])
    except ValueError:
        pass
    return None


# -- base 64 at one width -----------------------------------------------
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
