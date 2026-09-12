#! /usr/bin/env python3
#
# @hwut {
#     title      = "The zip beside an 'unaccepted' region (C-10)"
#     choices    = ["posttake", "token", "virgin"]
#     tolerance { regions = false }
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: C-10, measured -- an 'unaccepted' nominal chunk pairs with
         whatever subject chunk stands opposite; a plain subject chunk
         facing a post-take run is split by CONTENT anchors; the closing
         token is a chunk of its own on both sides and pairs with itself.
______________________________________________________________________________
"""
import asyncio, io, sys
from vut.engine.compare.configuration      import Configuration
from vut.engine.compare.reading.reading    import lawyer_reading
from vut.engine.compare.core.input_chunk_zip import generate_chunk_pairs_type_aligned


def text_of(chunk):
    """RETURN: list[str], the chunk's raw lines; None for an absent side."""
    if chunk is None: return None
    return [line._string.rstrip("\n") for line in chunk.line_list]


def zip_of(subject, nominal):
    """RETURN: None. Prints every chunk pair the type-aligned zip yields."""
    async def go():
        cfg = Configuration()
        s_pipe = lawyer_reading(cfg, io.StringIO(subject))
        n_pipe = lawyer_reading(cfg, io.StringIO(nominal))
        async for s, n in generate_chunk_pairs_type_aligned(cfg, s_pipe, n_pipe):
            s_kind = "-" if s is None else s.type().name
            n_kind = "-" if n is None else n.type().name
            print("   %-14s %-28s | %-12s %s"
                  % (s_kind, text_of(s), n_kind, text_of(n)))
    asyncio.run(go())


def test_virgin():
    print("THE MIRROR: one region per subject chunk, fillers one per line,")
    print("the token outside -- every chunk finds its partner, nothing doubles")
    zip_of("alpha\nbeta\n##! table\n a | b\n c | d\n####\ngamma\n<hwut-end>\n",
           "##! unaccepted\n--?--\n--?--\n####\n"
           "##! unaccepted\n--?--\n--?--\n####\n"
           "##! unaccepted\n--?--\n####\n<hwut-end>\n")


def test_posttake():
    print("AFTER TWO TAKES: one subject chunk faces region|plain|region|plain.")
    print("Plain chunks ANCHOR by content; regions take what lies between.")
    zip_of("alpha\nbeta\ngamma\ndelta\n<hwut-end>\n",
           "##! unaccepted\n--?--\n####\nbeta\n"
           "##! unaccepted\n--?--\n####\ndelta\n<hwut-end>\n")
    print()
    print("N != M: 'beta' was taken as three lines; the anchors still hold")
    zip_of("alpha\nb1\nb2\nb3\ngamma\n<hwut-end>\n",
           "##! unaccepted\n--?--\n####\nb1\nb2\nb3\n"
           "##! unaccepted\n--?--\n####\n<hwut-end>\n")
    print()
    print("PLAIN/PLAIN WITH NO REGION IN SIGHT pairs as it always has (P-13)")
    zip_of("one\ntwo\nthree\n<hwut-end>\n", "one\nTWO\nthree\n<hwut-end>\n")


def test_token():
    print("THE CLOSING TOKEN is a chunk of its own on EVERY stream,")
    print("and only where it is the LAST line")
    zip_of("a\nb\n<hwut-end>\n", "a\nb\n<hwut-end>\n")
    print()
    zip_of("a\n<hwut-end>\nb\n", "a\n<hwut-end>\nb\n")
    print()
    print("token only:")
    zip_of("<hwut-end>\n", "<hwut-end>\n")


CHOICE_DB = {"virgin": test_virgin, "posttake": test_posttake, "token": test_token}
CHOICE_DB[sys.argv[1] if len(sys.argv) > 1 else "virgin"]()
print("<hwut-end>")
