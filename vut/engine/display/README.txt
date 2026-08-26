==============================================================================
display -- THE CONSOLE REPORT TIER
==============================================================================

The modules:

    word.py     the phrase table and the ink -- the ONE place a wire
                token becomes English, and the ONE colour decision
    plain.py    the tier-1 renderer: CPlainFlow, a receiver that
                writes console lines
    console.py  the console's own words: the tier flags, the colour
                flags, the width policy. 'parse_rendering()' and
                'console_view()' -- what a face calls.

A face calls 'console.py' and nothing else. 'plain.py' and 'word.py'
are reached through it.

LAYERING LAW: this component imports the orchestrator's vocabulary,
receiver and summary; nothing imports display back. The queue is the
only door between the run and the screen. Its mirror stands in
'orchestrator/run/README.txt': that component is operational only.

THREE KINDS OF WORD, THREE PARSERS. A face parses SELECTION (the wish,
'plan/wish.py') and EXECUTION (--jobs, --no-store, --directory); this
component parses RENDERING. A face never decides how something looks;
this component never decides what runs. 'parse_rendering()' raises
'RenderingError' where the words cannot want anything; the face turns
that into REFUSED, exactly as it does for 'WishError'.

THE QUEUE IS THE ONLY DOOR
The face ('services/run.py') reads the queue live and hands
each event to 'CPlainFlow.dispatch()'; a suite may call 'render()'
with a list instead. The closing 'None' is a no-op to dispatch; the
tail blocks are written by 'CPlainFlow.tail()' after the loop.

THE LINE FORMAT
Every event becomes one line:

    hh:mm:ss | NNN | [EVENT] NICK:base [choice] ...

'hh:mm:ss' is the event's own 'when' relative to the stream's first
instant -- the display never reads a clock of its own. A 'when' that
is not an ISO-8601 instant prints verbatim, right-aligned to 8. 'NNN'
is the count of parallel executions AFTER the event. '[SKIP ]' marks a
'run-ended' that never had a 'run-begun'. The failing line carries
its phrase inline; the cause node is appended with '<-'.

THE CLOSING BLOCKS
After the flow, in order: DIRECTORIES (the roll-call of every
directory, ok/fail counts, elapsed time), FAULTS (QUIET only), and
FAILURES (the not-ok nodes, phrase and cause). Nothing in the SILENT
tier.

THE TIERS ('display/plain.py', 'E_Tier')
    VERBOSE   every event, the swallowed ones included (frames,
              good runs, DONE and TREE lines)
    PLAIN     the flow (DIR, START, END, SKIP, FAULT, NOTE), the
              roll-call, FAILURES (the default)
    QUIET     no flow; the roll-call, FAULTS block, FAILURES
    SILENT    nothing on stdout; faults go to 'write_error',
              prefixed and nicknamed exactly as in the flow

NICKNAME DERIVATION ('derive_nickname')
The nickname of a directory path is deterministic: the initials of
its hyphen/underscore/dot-separated words, a trailing 'TEST' component
dropped, upper-cased. A single-word remainder yields its first four
letters. '.' yields 'ROOT'. Collisions in 'CPlainFlow' are resolved
by appending 2, 3, ... in first-seen order.

COLOUR GATES ('word.colour_decision')
The decision is taken ONCE at 'main', handed down as a flag; no line
re-sniffs. '--colour' ('force_f=True') beats every gate, NO_COLOR
included. '--no-colour' ('veto_f=True') refuses. Otherwise ALL must
pass: stdout is a terminal, NO_COLOR is unset, CI is unset, TERM is
set and not 'dumb', and on Windows ANSI is known enabled.

THE ONE ENGLISH DOOR ('word.py')
Every wire token becomes a phrase through 'phrase()'. The PHRASE_DB
maps verdict words and every 'E_TestRunResult' value. A token the
table does not carry prints with its hyphens opened -- the stability
promise: the wire grows, the display keeps reading.
