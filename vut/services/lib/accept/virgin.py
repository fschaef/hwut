"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE NOMINAL TO MERGE AGAINST WHERE NONE STANDS -- a first
         acceptance's opening state.

DESCRIPTION
       A MIRROR, NOT A WRAPPER. The subject is parsed into its chunks by
       compare's own reader, and EACH chunk becomes one
       '##! unaccepted' region holding ONE FILLER LINE PER SUBJECT LINE.
       Chunk counts and order then correspond one to one, and inside
       each region the pairing is 1:1 and TOTAL -- no subject line is
       ever left without a partner.

       ONE REGION WRAPPING EVERYTHING DOES NOT WORK, and it was
       measured: the candidate's lines then appear TWICE -- once as
       nominal-only inside the region, once as subject-only below it --
       and never side by side, which destroys the view's whole premise.

       THE REGION IS NOT FILLED WITH THE SUBJECT'S OWN LINES. Two
       reasons, and either alone would decide it. It would put the
       answer in the file before anybody had looked at it, so 'taking' a
       line would move it onto a copy of itself. And a subject chunk
       that is itself a region carries its own '##!' and '####', which
       inside an unaccepted region is NESTING -- forbidden, and measured
       to close the outer region early where it is not refused outright.

       THE MARKERS ARE STRUCTURE, NOT CONTENT. compare pairs the fillers
       and never sees '##! unaccepted' or '####'. That the viewer draws
       them level with the first and last subject line is a matter of
       layout, and belongs to the viewer.

       THE CLOSING TOKEN STANDS OUTSIDE EVERY REGION, as the last line.
       R-70 asks whether the stream's last line is '<hwut-end>', and it
       still is. Wrapping the token in 'nobody has judged this' would
       assert something false: the run DID complete, and that is not
       undecided.
______________________________________________________________________________
"""
from vut.engine.compare.reading.reading    import lawyer_reading
from vut.services.lib.viewers.keyed.region import filler_region
from vut.services.lib.viewers.keyed.state  import CLOSING_TOKEN

import asyncio
import io


def virgin_nominal(configuration, subject_text):
    """RETURN: str, the nominal to merge against where NO nominal stands
               -- one '##! unaccepted' region per subject chunk, each
               holding one filler line per line of that chunk, with the
               closing token '<hwut-end>' appended OUTSIDE every region
               as the last line.

               None, where 'subject_text' does not end in the closing
               token: such a stream never COMPLETED (R-70), and no merge
               may open on it.
    """
    line_list = subject_text.splitlines()
    if not line_list or line_list[-1].strip() != CLOSING_TOKEN:
        return None

    chunk_line_n_list = asyncio.run(_chunk_line_n_list(configuration,
                                                       line_list[:-1]))
    result = []
    for line_n in chunk_line_n_list:
        result.extend(filler_region(line_n))
    result.append(CLOSING_TOKEN)

    return "\n".join(result) + "\n"


def subject_span_list(configuration, subject_text):
    """RETURN: tuple[(int, int)], the first and last index of every
               subject chunk, both inclusive and the closing token
               excluded -- what each region of the virgin nominal stands
               opposite.

               An empty tuple, where the subject holds nothing but the
               closing token.
    """
    line_list = subject_text.splitlines()
    if line_list and line_list[-1].strip() == CLOSING_TOKEN:
        line_list = line_list[:-1]

    result, first_i = [], 0
    for line_n in asyncio.run(_chunk_line_n_list(configuration, line_list)):
        result.append((first_i, first_i + line_n - 1))
        first_i += line_n
    return tuple(result)


async def _chunk_line_n_list(configuration, line_list):
    """RETURN: list[int], how many lines each chunk of 'line_list' holds,
               in order -- consecutive plain lines counting as ONE chunk,
               and every region a chunk of its own.

               A single-element list holding the whole length, where the
               reader refuses the text: a stream compare cannot frame is
               still one an author may wish to accept, and refusing to
               open a session over it would help nobody.
    """
    if not line_list: return []

    text  = "\n".join(line_list) + "\n"
    queue = asyncio.Queue(maxsize=1000)
    pipe  = lawyer_reading(configuration, io.StringIO(text))
    task  = pipe.create_producer_task(queue)

    result = []
    try:
        while True:
            item = await queue.get()
            if item.is_error():    return [len(line_list)]
            if item.is_terminal(): break
            result.append(_line_n_of(item, len(line_list)))
    finally:
        if not task.done(): task.cancel()

    return [each for each in result if each]


def _line_n_of(chunk, line_n_total):
    """RETURN: int, how many lines of this chunk compare will PAIR -- the
               length of its own 'line_list'.

    NOT the chunk's line SPAN. A region's span counts its '##!' and
    '####', which compare never pairs: they are structure, and its
    'line_list' holds the framed content alone. Sizing the fillers by
    the span would put two too many in every region-bearing chunk, and
    the surplus would pair against whatever followed -- measured, it
    swallowed the closing token.
    """
    return len(chunk.line_list)
