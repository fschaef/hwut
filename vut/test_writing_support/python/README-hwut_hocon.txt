==============================================================================
hwut_hocon -- THE SPECIFICATION LANGUAGE
==============================================================================

A HWUT specification is written in a subset of HOCON. This file states the
subset: what it admits, what it refuses, and what each form means. It is
support for WRITING TESTS, given to every language HWUT supports; the Python
implementation stands here and its GOOD files are the description the other
ports are measured against.

The parser depends on nothing but the standard library and names no engine
type. It hands back an ANNOTATED TREE -- every key, every value and every
block carrying its position in the file -- and a list of faults. It never
raises.


1  THE GRAMMAR
______________________________________________________________________________

    document    = entry*
    entry       = key ( "=" | ":" ) value
                | key object
    key         = bare-token | string
    value       = object | list | string | number | boolean | nothing

    object      = "{" entry* "}"
    list        = "[" value* "]"

Blanks, newlines and commas separate; none of them means anything more. A
comma is admitted wherever a blank is, and is required nowhere:

    choices = ["one", "two"]        choices = ["one" "two"]
    a = 1  b = 2                    a = 1, b = 2

A brace directly after a key binds without a sign:

    caps { timeout_sec = 30 }       caps = { timeout_sec = 30 }

A dot inside a key is a literal character, never a path: 'test-gen.c' is one
key, and there is no key called 'test' with a member called 'gen'.


2  STRINGS CARRY QUOTES
______________________________________________________________________________

    build   = "make"                choices = ["one", "two"]
    pype    = "strip.pype"          app     = "sub/dir/test.py"

Real HOCON admits the unquoted string and pays for it: an unquoted value
runs to the end of the line, so a comment marker ends a value, two entries
cannot share a line without ambiguity, and 'yes' is a boolean while 'yes
please' is a string. Here a bare token is a boolean, a number, or a spelling
of nothing -- and it ends at a blank. Anything else is a string and carries
quotes.

What quotes preserve, that nothing else can:

    a = "not # a comment"           the marker is content
    a = "x = y"                     the binder is content
    a = "make %.exe"                the blanks are content

Inside a string, '\\n', '\\t', '\\"' and '\\\\' are the escapes.

A KEY may stand bare -- a key is not a value. A key carrying a blank
carries quotes:

    test-gen.c    = 1               bare
    "test-a.py two" = 1             a target naming a choice


3  NUMBERS
______________________________________________________________________________

    decimal     42      -0.12     +7e212     6.02e23     .5
    hexadecimal 0xDEAD_BEEF        0XFF
    binary      0b0111_11_01
    octal       0o3124
    roman       0rIV    0rMCMLXXXIV          -0rX

'_' is a VISUAL HELPER: it may stand anywhere between digits, and it enters
no value. It may not begin or end the digits, and two in a row are refused.

A SIGN MAY STAND APART from its digits, in any radix:

    timeout_sec = - 0.12            reads as -0.12

The roman form is the strict one: 'IIII' and 'VX' are refused, 'IV' and
'MCMLXXXIV' are read.

There is NO ARITHMETIC. '5 - 1' is not four; it is the number five followed
by something that is not a key.

What spells no number in any radix is a string, and carries quotes: '1.2.3'
is a version, '0x' is a fragment, '0b012' is not binary.


4  BOOLEANS AND NOTHING
______________________________________________________________________________

    true    yes                     false   no
    null    nil     none    nihil   and a value left empty

The four spellings of nothing mean one thing, and an empty value means the
same:

    analogy =                       analogy = null
    analogy = nihil                 analogy = none

What NOTHING means is each key's own affair, and the parser decides none of
it. In a HWUT specification, a key bound to nothing switches a feature off
where the key has an off, and is refused where a value is required -- see
the exploration component's README.


5  COMMENTS
______________________________________________________________________________

    # to the end of the line        // to the end of the line

A comment may follow a value on the same line. Inside a string, neither
marker means anything.


6  REFUSED, BY NAME
______________________________________________________________________________

    include "other.conf"        a specification refers to nothing
    a = ${outside.value}        outside its own file
    a += "appended"             no accumulation
    a = """triple"""            no triple-quoted strings

Each is refused with its own message, saying what does not exist rather
than what was unexpected. The first two are refused for one reason: a
specification is read from the file it stands in, and from nowhere else.

Real HOCON's object merging, value concatenation, path expressions
('a.b.c = 1'), duration and size units ('30s', '4MB') are not here either.
A duplicate key is a fault: the first stands, the second is refused.


7  FAULTS
______________________________________________________________________________

Faults are VALUES, not exceptions. The parser accumulates them, recovers at
the next line, and completes: a file with four mistakes reports four, not
the first.

Every fault carries a position -- the line and column an editor shows. The
positions are FILE-RELATIVE even when the specification lives inside a
comment block of another language: the caller hands the parser lines that
carry their own offsets ('SourceLine'), and the parser adds them to
everything it reports.

    ParseFault(kind, file, position, message)
    E_ParseFault.SYNTAX     the text does not parse
    E_ParseFault.REFUSED    a construct that does not exist here

The engine converts these into its own fault record; this component knows
nothing of that record.


8  WHAT THE PARSER HANDS BACK
______________________________________________________________________________

    parse(line_list, file) -> (ObjectNode, [ParseFault])

    ObjectNode      position, entry_list
    Entry           key, key_position, node
    ScalarNode      value, position          str | int | float | bool | None
    ListNode        item_list, position

'SourceLine(text, line, column_offset)' is the parser's input record: one
line as the parser reads it, tied to where it stands on disk.
