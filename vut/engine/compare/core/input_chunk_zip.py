"""SPDX-License: MIT; (C) Frank-Rene Schäfer; Project: hwut
_______________________________________________________________________________

PURPOSE: Yielding pairs of 'InputChunk'-s from subject and nominal to be
         compared.

The 'ChunkPipe' interprets the input streams of subject and nominal. An
input chunk can be:

   -- LineSequence: set of lines where the sequence is *relevant*.

   -- Potpourri:    set of lines where the sequence is *unimportant*.

The function 'generate()' yields pairs of those input chunks to be
compared.
_______________________________________________________________________________
"""

from vut.engine.compare.reading.chunk_pipe  import ChunkPipe
from vut.engine.compare.reading.input_chunk import InputChunkVoid, InputChunk_factory
from vut.engine.compare.configuration     import Configuration
from vut.engine.compare.contract.enums    import E_Chunk

from   typeguard import typechecked
import asyncio


@typechecked
async def generate_chunk_pairs(config:        Configuration,
                               subject_pipe:  ChunkPipe,
                               nominal_pipe:  ChunkPipe):
    """YIELDS: [0] subject input chunk
               [1] nominal input chunk

    In general the type of the subject chunk is not equal to the type
    of the nominal chunk.
    """
    # Setup Queues
    q_s, q_n = asyncio.Queue(maxsize=10), asyncio.Queue(maxsize=1000)

    # Start Producers
    tasks = [ subject_pipe.create_producer_task(q_s),
              nominal_pipe.create_producer_task(q_n) ]

    s_item = n_item = InputChunkVoid()
    try:
        while True:
            # Futures: stream exhausted use 'sleep(0)', else use 'queue.get()'
            coro_s = asyncio.sleep(0, result=s_item) if s_item.is_terminal() else q_s.get()
            coro_n = asyncio.sleep(0, result=n_item) if n_item.is_terminal() else q_n.get()

            # Wait in parallel for subject and nominal queue
            s_item, n_item = await asyncio.gather(coro_s, coro_n)

            # A producer-side error (e.g. RegionSyntaxError) must surface
            # HERE, in the consumer's context -- never look like EOF.
            if s_item.is_error(): raise s_item.error
            if n_item.is_error(): raise n_item.error

            # Termination Check
            if s_item.is_terminal() and n_item.is_terminal(): break

            # Yield with Padding (EOF == InputChunkTerminal)
            yield s_item, n_item

    finally:
        for t in tasks:
            if not t.done(): t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

@typechecked
async def generate_chunk_pairs_type_aligned(config:       Configuration,
                                            subject_pipe: ChunkPipe,
                                            nominal_pipe: ChunkPipe):
    """
    YIELDS: (SubjectChunk | None, NominalChunk | None)
    """
    # Setup Queues
    q_s, q_n = asyncio.Queue(maxsize=10), asyncio.Queue(maxsize=1000)

    # Start Producers
    tasks = [ subject_pipe.create_producer_task(q_s),
              nominal_pipe.create_producer_task(q_n) ]

    async def _get_checked(q):
        # A producer-side error (e.g. RegionSyntaxError) must surface HERE,
        # in the consumer's context -- never look like EOF.
        item = await q.get()
        if item.is_error(): raise item.error
        return item

    #  ONE CHUNK OF NOMINAL LOOK-AHEAD, for the content-anchored split
    #  (C-10): a plain subject chunk facing a RUN of nominal chunks --
    #  'region | plain | region', the shape every take leaves behind --
    #  is split to face them, and where a region ends is told by the
    #  first line of the plain chunk AFTER it.
    n_peek = []

    async def _get_nominal():
        if n_peek: return n_peek.pop(0)
        return await _get_checked(q_n)

    async def _peek_nominal():
        if not n_peek: n_peek.append(await _get_checked(q_n))
        return n_peek[0]

    try:
        # Initial Fetch
        s_prev, n_prev = await asyncio.gather(_get_checked(q_s), _get_nominal())

        # Loop while BOTH are valid (not EOF)
        while not s_prev.is_terminal() and not n_prev.is_terminal():

            #  THE SPLIT, before any pairing: give the nominal chunk the
            #  subject lines that are ITS, and carry the rest forward.
            n_after = await _peek_nominal()
            head, tail = _split_to_face(s_prev, n_prev, n_after, config)
            if tail is not None:
                yield (head, n_prev)
                s_prev = tail
                n_prev = await _get_nominal()
                continue

            if _pairs_f(s_prev, n_prev):
                # MATCH
                yield (s_prev, n_prev)
                s_prev, n_prev = await asyncio.gather(_get_checked(q_s), _get_nominal())

            else:
                # MISMATCH
                s_next, n_next = await asyncio.gather(_get_checked(q_s), _get_nominal())

                if not n_next.is_terminal() and _pairs_f(s_prev, n_next):
                    yield (None, n_prev)     # Flush the extra Nominal
                    yield (s_prev, n_next)   # Pair held Subject with next Nominal
                    s_prev = s_next
                    n_prev = await _get_nominal() # fill the slot of the consumed n_prev

                elif not s_next.is_terminal() and _pairs_f(s_next, n_prev):
                    yield (s_prev, None)     # pair extra subject with nominal 'None'
                    yield (s_next, n_prev)   # pair matching next subject with previous nominal
                    s_prev = await _get_checked(q_s) # fill the slot of the consumed 's_prev'
                    n_prev = n_next

                else: # No way to heal a mismatch of subject and nominal by one look-ahead
                    yield (None, n_prev)     # pair 'None' with prev. nominal
                    yield (s_prev, None)     # pair prev. subject with nominal 'None'
                    s_prev = s_next          # take next into previous
                    n_prev = n_next

        # If Nominal still has data (Subject hit EOF)
        while not n_prev.is_terminal():
            yield (None, n_prev)
            n_prev = await _get_nominal()
        # If Subject still has data (Nominal hit EOF)
        while not s_prev.is_terminal():
            yield (s_prev, None)
            s_prev = await _get_checked(q_s)

    finally:
        for t in tasks:
            if not t.done(): t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


def _pairs_f(subject_chunk, nominal_chunk):
    """RETURN: bool, True where these two chunks stand opposite one
               another and are to be compared as a pair.

               False, where they are of different kinds and the nominal
               is not an UNACCEPTED region -- two different READINGS of
               the text cannot be laid against each other.

    AN 'unaccepted' NOMINAL CHUNK PAIRS WITH ANY SUBJECT CHUNK (C-10).
    Every other handler says HOW a stretch is to be read, and two
    readings cannot both claim one line. 'unaccepted' says only WHETHER
    anybody has looked at it, which is a statement about the nominal's
    history and not about how to read the subject -- so it takes
    whatever stands opposite, and 'region/unaccepted/associate.py' zips
    the two line by line as SUBSTITUTE.

    Without this the two streams DOUBLE on screen: the region's lines
    appear as nominal-only, the subject's as subject-only, and never
    side by side -- which is no use to somebody merging them.
    """
    if subject_chunk.type() == nominal_chunk.type(): return True
    return nominal_chunk.type() == E_Chunk.UNACCEPTED


def _split_to_face(subject_chunk, nominal_chunk, nominal_after, config):
    """RETURN: (InputChunk, InputChunk), the subject chunk cut in two --
               the HEAD, which is the nominal chunk's to pair with, and
               the TAIL, which faces whatever nominal chunk comes next.

               (subject_chunk, None), where no cut is called for: the
               subject chunk is not a plain line sequence, or the whole
               of it belongs to this nominal chunk.

    PLAIN CHUNKS ANCHOR; REGIONS TAKE WHAT LIES BETWEEN (C-10). A taken
    line IS its subject line, byte for byte -- that is what taking
    means -- so a plain nominal chunk is found in the subject by
    CONTENT, exactly, and monotone. An UNACCEPTED region then receives
    the subject lines lying between its neighbours' anchors. Not by
    line offset: the first N != M take breaks offsets for good.
    """
    if subject_chunk.type() is not E_Chunk.LINE_SEQUENCE: return (subject_chunk, None)
    s_list = list(subject_chunk.line_list)
    if len(s_list) < 2: return (subject_chunk, None)

    n_type = nominal_chunk.type()
    if n_type is E_Chunk.UNACCEPTED:
        #  Where does this region END in the subject? At the anchor of
        #  the plain chunk after it; failing that, at its own length.
        cut = _anchor_of(nominal_after, s_list)
        if cut is None: cut = min(len(nominal_chunk.line_list), len(s_list))
    elif n_type is E_Chunk.LINE_SEQUENCE:
        #  ONLY BESIDE A REGION. A plain nominal chunk facing a plain
        #  subject chunk with no region in sight pairs as it always has
        #  (P-13): the association is compare's, and this cut is not to
        #  second-guess it. The cut is for the post-take run --
        #  'region | plain | region' -- where the plain chunk is a
        #  taken stretch and owns the subject lines that ARE its lines.
        if not _unaccepted_f(nominal_after): return (subject_chunk, None)
        cut = _last_anchor_of(nominal_chunk, s_list)
        if cut is None: return (subject_chunk, None)
    else:
        return (subject_chunk, None)

    if cut <= 0 or cut >= len(s_list): return (subject_chunk, None)

    first_n = subject_chunk.start_line_n
    head = InputChunk_factory(E_Chunk.LINE_SEQUENCE, first_n, first_n + cut,
                              s_list[:cut], config)
    tail = InputChunk_factory(E_Chunk.LINE_SEQUENCE, first_n + cut,
                              subject_chunk.end_line_n, s_list[cut:], config)
    return (head, tail)


def _unaccepted_f(chunk):
    """RETURN: bool, True where 'chunk' is an unaccepted region -- and
               False for None, the terminal, or any other kind.
    """
    if chunk is None or chunk.is_terminal(): return False
    return chunk.type() is E_Chunk.UNACCEPTED


def _text_of(line):
    """RETURN: str, the line's raw text, newline stripped."""
    return line._string.rstrip("\n")


def _anchor_of(nominal_chunk, s_list):
    """RETURN: int, the index in 's_list' of the first line of a PLAIN
               nominal chunk -- where the region before it ends.

               None, where the chunk is not plain, is empty, or its
               first line stands nowhere in the subject.
    """
    if nominal_chunk is None or nominal_chunk.is_terminal():        return None
    if nominal_chunk.type() is not E_Chunk.LINE_SEQUENCE:            return None
    n_list = list(nominal_chunk.line_list)
    if not n_list:                                                   return None
    wanted = _text_of(n_list[0])
    for i, line in enumerate(s_list):
        if _text_of(line) == wanted: return i
    return None


def _last_anchor_of(nominal_chunk, s_list):
    """RETURN: int, one past the index in 's_list' where the plain
               nominal chunk's LAST line stands, searched monotone from
               where its first line stands.

               None, where the chunk's lines cannot be found in order.
    """
    n_list = list(nominal_chunk.line_list)
    if not n_list: return None
    i = _anchor_of(nominal_chunk, s_list)
    if i is None: return None
    for n_line in n_list[1:]:
        wanted = _text_of(n_line)
        while i + 1 < len(s_list) and _text_of(s_list[i + 1]) != wanted:
            i += 1
        if i + 1 >= len(s_list): return None
        i += 1
    return i + 1
