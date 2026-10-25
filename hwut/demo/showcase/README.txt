==============================================================================
showcase -- WHAT A TEXT-JUDGING TEST TOOL CAN TEST
==============================================================================

82 examples from working life and famous failures, 212 test cases, one hwut tree. Each example
states ONE requirement and prints what it finds as a picture -- a tree, a
matrix, a waveform, a timeline, a plot -- so that the GOOD file reads as a
specification sheet: a person or an AI judges it without reading the code.

Every example has a fixture that keeps the requirement and one (or more)
that breaks it. Both are green: the GOOD of the broken one IS the accepted,
readable violation report. Each choice binds its count of findings and
states it as a law -- '== 0' where the requirement holds, '> 0' where the
fixture breaks it -- so a change that breaks the rule anew, or hides a known
violation, fails the law itself, not only the picture.

UNITS (hwut since E-175): where a number carries a unit, it is printed with
it, ((t: 57 ms)), and the law is written in the source's units, t >= 5 ms --
the comparison converts. A temperature difference is printed in K, never
degC (offset unit); genomic bp/kb/cM are not pint units and stay plain text.
Every docstring opens with a SUBJECT line: what the printed output describes.

TO RECORD (hwut since E-165): 'hwut.play <test> <choice>' runs and records;
'hwut.accept <test> <choice> --as-is' blesses a first recording, '--force'
replaces a standing GOOD; accept runs nothing.

    cd showcase && hwut --plain          every test, green
    hwut.report.features                 every requirement, and what proves it
    cd behaviour/uart-decoder/TEST && ./test-uart.py noise
                                         one picture, as the test prints it
                                         (or read GOOD/test-uart.py--noise.txt)

THE SIX AREAS

    conventions/   ARTIFACTS, not running programs: Makefiles, headers,
                   comments, licences, enums, error codes, catalogues,
                   config keys, CLI docs, migrations, layering,
                   whitespace, commit history.         14 examples
    behaviour/     ORDER AND TIME: protocols, debouncing, UART/SPI decoding,
                   watchdogs, backoff, rate limits, queues, locks, caches,
                   event sourcing, state charts, scheduling, pub/sub -- with
                   pype laws over event streams.        15 examples
    data/          VALUES: filters, fits, money, calendars, parsers, logs,
                   conversions, sorting, codecs, file trees, CLI contracts,
                   performance budgets, text layout.     15 examples
    generators/    SPACES: the tested space described by generator
                   instructions -- space_iterator, deterministic_random,
                   deterministic_timeline (races), hwut_runner.
                                                        14 examples
    classics/      FAMOUS FAILURES, each modelled small and caught by its
                   law: Myers' triangle, binary-search overflow, Patriot,
                   Ariane 5, Pentium FDIV, Zune, Y2038, goto fail,
                   Therac-25, Peterson/Dekker, dining philosophers,
                   Cloudflare regex, Mars Climate Orbiter,
                   Gimli Glider, Apollo 11's stolen memory
                   cycles (Verilog), Dirty COW (race
                   model).                              16 examples
    science/       BIOINFORMATICS AND NUMERICS: gene names in spreadsheets,
                   BED vs VCF coordinates, Needleman-Wunsch, reverse
                   complement and translation, FASTQ Phred, SIR model,
                   float summation, Game of Life.        8 examples

Each example: <area>/<name>/ holds the thing under test (C, Make, awk,
bash, perl, node, Python, SQL, YAML, ...), 'good/' and 'broken/' fixtures
where they apply, and TEST/ with the test application, its
'hwut-features.conf' and GOOD/. The docstring of each test application says
the requirement, what each choice shows, which hwut concept carries it, and
why every tolerance is there.

MACHINE -- Python 3.10+, bash, gcc, make, awk, perl, node; hwut on PATH.
classics/apollo11-counters also needs Verilator (apt install verilator).
No network. C and Verilog units are compiled by their test application per
run.
==============================================================================
