==============================================================================
showcase -- WHAT A TEXT-JUDGING TEST TOOL CAN TEST
==============================================================================

93 examples from working life and famous failures, 239 test cases, one
hwut tree. Each example states ONE requirement and prints what it finds as a picture -- a tree, a
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
                                                        13 examples
    classics/      FAMOUS FAILURES, each modelled small and caught by its
                   law:
                     numbers   Myers' triangle, binary-search overflow,
                               Pentium FDIV, Ariane 5, Bitcoin's value
                               overflow (2010), Vancouver's truncated
                               index (1982)
                     time      Patriot, Zune, Y2038, the counter wraps
                               (Boeing 787, GPS week, Y2K), the leap
                               second (2017)
                     units     Mars Climate Orbiter, Gimli Glider
                     memory    Heartbleed (a fuzzer and a guard page),
                               CrowdStrike (2024), goto fail
                     races     Therac-25, Peterson/Dekker, dining
                               philosophers, Dirty COW, The DAO's
                               reentrancy (2016)
                     systems   Apollo 11's stolen memory cycles
                               (Verilog), AT&T's cascade (1990), Mars
                               Polar Lander, Knight Capital (2012),
                               Cloudflare regex, Debian OpenSSL's 32768
                               keys, Spotify's user names (2013)
                                                        27 examples
    science/       BIOINFORMATICS AND NUMERICS: gene names in spreadsheets,
                   BED vs VCF coordinates, Needleman-Wunsch, reverse
                   complement and translation, FASTQ Phred, SIR model,
                   float summation, Game of Life.        8 examples

FIND AN EXAMPLE BY ITS SHAPE -- a task is matched by what its test must
see, not by its domain:

    SHAPE                                   EXAMPLES
    order free, facts fixed                 parallel-count, job-queue
    some order matters (cause, once, end)   pipe-conversation, pubsub-retained,
                                            event-sourcing
    transitions only along a chart          tcp-handshake, traffic-light
    every interleaving                      interleavings, bank-race,
                                            therac-25, peterson-dekker, the-dao
    every combination of a boundary space   sat-add, myers-triangle,
                                            date-valid, header-matrix,
                                            bitcoin-overflow
    against a model or a brute force        ring-model, needleman-wunsch,
                                            expr-parser
    round trip                              cobs-roundtrip, gene-names-excel,
                                            bed-vs-vcf-coordinates
    a function applied twice is applied     spotify-unicode
    once (idempotence)
    several sources must agree              cli-options, i18n-catalogs,
                                            error-codes, crowdstrike-2024,
                                            knight-capital
    a house rule over artifacts             conventions/*
    a contract matrix (input x exit x       cli-matrix
    stream)
    a noisy number within a band            kalman-baro, ntc-fit
    a law over time, in units               watchdog, token-bucket, debounce,
                                            retry-backoff, mars-polar-lander
    a counter that wraps                    patriot-clock, zune-leap-year,
                                            y2038, counter-wraps, leap-second
    a growth law (fitted exponent)          perf-budget, regex-backtracking
    exact to the last digit                 money-vat, unit-convert,
                                            float-summation, vancouver-index
    reads outside its input                 heartbleed, crowdstrike-2024,
                                            binary-search-overflow
    the space of what can come out          seed-sweep, debian-openssl
    the same everywhere                     stream-portability
    a cascade through a network             att-1990

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
