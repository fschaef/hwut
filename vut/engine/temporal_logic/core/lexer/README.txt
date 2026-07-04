SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
===============================================================================
core/lexer  --  pull-driven regex tokenizer over a generated token spec.
===============================================================================

TOPOLOGY
-------------------------------------------------------------------------------

    GRAMMAR (outer facade) --register_grammar()--> _GRAMMAR
                                                      |
    TERMINAL_DB (parser_generator) ---+              walk string keywords
                                      v               v
                              _generate_token_spec()  (seven tiers)
                                      |
                                      v
        _TOKEN_SPEC --_scanner()--> one compiled re.Pattern, named groups
                                      |
    source text --Lexer.next()--------+--> Token stream --> parser

THE PARTS  (all in lexer.py)
-------------------------------------------------------------------------------

    register_grammar(grammar_dict)
                   The single injection point. Called once by the outer
                   parser facade before the first lex. Flattens a
                   subspace-nested grammar, stores it, and resets the
                   cached token spec and scanner.
    token_spec()   The generated (Terminal, pattern) list, built and
                   cached on first call. A token's identity is the
                   Terminal object that produced it; there is no
                   hand-maintained token-id enum and no author-supplied
                   precedence number. The tiers, in emission order:
                     1. skip groups: '##' comment, whitespace framing
                     2. leading-colon string keywords (':end'), ':word\b'
                     3. trailing-colon string keywords ('mode:'),
                        '\bword', longest-first
                     4. bare keywords: captured terminals and identifier
                        strings, '\bword\b'
                     5. symbols ('=>', '{', '}'): re.escape,
                        longest-first
                     6. regex class terminals (T.regex), declaration
                        order
                     7. mismatch framing ('.'), last
                   Within a tier, order is length (longest-first where
                   listed) then declaration order. The end-of-file
                   terminal carries no pattern; it is synthesized past
                   the text end.
    token_debug_names()
                   Terminal -> friendly name, for parser debug tracing.
    Token          Frozen record: kind (the Terminal), value, and the
                   absolute character span [begin:end].
    SourceMap      Converts an absolute offset to a 1-based (line,
                   column) on demand, independent of tokenization.
    Lexer          The pull-driven tokenizer: the parser calls next()
                   per token. Reads nothing before the first next().
DATA FLOW  (one next() call)
-------------------------------------------------------------------------------

    cursor --scanner.match--> matched group --_GROUP_OF--> Terminal
        skip group?        consume silently, continue
        mismatch?          report non-fatal Diagnostic, return the Token
        otherwise          return Token(kind, value, begin, end)
    text end               return Token(t_fr_eof, "", len, len)

    '{' and '}' are ordinary tokens. A mismatch Token reaches the parser,
    which resyncs at the next anchor. Diagnostics accumulate in the
    injected DiagnosticReporter; Lexer.error_f stays True once any
    author-fixable error was reported.

HOW TO RUN / TEST
-------------------------------------------------------------------------------

    cd TEST
    python3 test-lexer.py --hwut-info     choices: comments_ws, mismatch,
                                          source_map
    python3 test-lexer.py <choice>        diffs byte-exact against
                                          GOOD/test-lexer.py--<choice>.txt

POINTERS
-------------------------------------------------------------------------------

    ../README.txt                        core overview
    ../parser_generator/README.txt       terminal factory T, TERMINAL_DB,
                                         the engine that pulls the tokens
    ../diagnostic.py                     the error model the lexer reports
                                         through
