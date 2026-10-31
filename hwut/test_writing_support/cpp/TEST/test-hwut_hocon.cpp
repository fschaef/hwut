/* @hwut {
 *     title      = "HOCON parser: subset (A), annotated tree"
 *     build      { framework = "make", executable = "%.exe" }
 *     choices {
 *         comments  { features = ["cpp-hocon"] }
 *         faults    { features = ["cpp-hocon"] }
 *         fuzz      { features = ["cpp-hocon"] }
 *         numbers   { features = ["cpp-hocon"] }
 *         oneline   { features = ["cpp-hocon"] }
 *         positions { features = ["cpp-hocon"] }
 *         quoting   { features = ["cpp-hocon"] }
 *         refused   { features = ["cpp-hocon"] }
 *         scalars   { features = ["cpp-hocon"] }
 *         structure { features = ["cpp-hocon"] }
 *         triple    { features = ["cpp-hocon"] }
 *         unclosed  { features = ["cpp-hocon"] }
 *     }
 *     interactive = true
 * }
 *
 * SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * PURPOSE: The C++ port of 'python/TEST/test-hwut_hocon.py', choice for
 *          choice, held against its GOOD files by '.link'. A value prints as
 *          Python's '%r (type)' prints it; the fuzz draws the same edits from
 *          the same seed ('deterministic_random') and bounds every parse by
 *          a timer. A parse past the bound cannot be abandoned from C++: the
 *          timer ends the choice, saying the text (the GOOD wants 0 hangs).
 * _____________________________________________________________________________
 */
#include <array>
#include <csignal>
#include <cstdio>
#include <cstring>
#include <exception>
#include <string>
#include <vector>
#include <sys/time.h>
#include <unistd.h>
#include "hwut_runner.hpp"
#include "hwut_hocon.hpp"
#include "deterministic_random.hpp"

namespace hocon = hwut::hocon;

static void banner(const std::string& label) { std::printf("\n--- %s ---\n", label.c_str()); }

static std::vector<hocon::SourceLine>
lines(const std::string& text, int line_offset = 0, int column_offset = 0)
/* RETURN: 'text' split at every newline (an ending one gives a last, empty
 *         line, as Python's 'split'), offsets applied uniformly.          */
{
    std::vector<hocon::SourceLine> result;
    size_t                         begin = 0;
    while( true ) {
        size_t end = text.find('\n', begin);
        result.push_back({ text.substr(begin, end == std::string::npos ? std::string::npos : end - begin),
                           (int)result.size() + 1 + line_offset, column_offset });
        if( end == std::string::npos ) return result;
        begin = end + 1;
    }
}

static void
show(const hocon::Node& node, int indent = 0)
/* RETURN: nothing; the annotated tree is printed, positions included.     */
{
    std::string pad(4 * (size_t)indent, ' ');
    switch( node.kind() ) {
    case hocon::Node::OBJECT:
        std::printf("%s{ at %s\n", pad.c_str(), node.position().to_string().c_str());
        for(const auto& entry : node.entry_list()) {
            std::printf("%s  key '%s' at %s ->\n", pad.c_str(), entry.key.c_str(), entry.key_position.to_string().c_str());
            show(entry.node, indent + 1);
        }
        std::printf("%s}\n", pad.c_str());
        break;
    case hocon::Node::LIST:
        std::printf("%s[ at %s\n", pad.c_str(), node.position().to_string().c_str());
        for(const auto& item : node.item_list()) show(item, indent + 1);
        std::printf("%s]\n", pad.c_str());
        break;
    default:
        std::printf("%s%s (%s) at %s\n", pad.c_str(), node.value_repr().c_str(), node.type_name().c_str(),
                    node.position().to_string().c_str());
    }
}

static void
run(const std::string& label, const std::string& text, int line_offset = 0, int column_offset = 0)
/* RETURN: nothing; 'text' is parsed, its tree and faults printed.         */
{
    banner(label);
    auto [document, fault_list] = hocon::parse(lines(text, line_offset, column_offset), "f.hocon");
    show(document);
    for(const auto& fault : fault_list) std::printf("FAULT %s\n", fault.to_string().c_str());
}

static void
run_scalars()
{
    run("scalars",
        "a = bare\n"
        "b = \"quoted \\\"x\\\" and \\n\"\n"
        "c = 42\n"
        "d = -3.14\n"
        "e = 1e-6\n"
        "f = true\n"
        "g = no\n"
        "h = make %.exe\n"
        "i: \"colon-bound\"\n"
        "j = null\n"
        "k = nihil\n"
        "l =\n");
}

static void
run_numbers()
{
    run("decimal, with sign and exponent",
        "a = 42\n" "b = -0.12\n" "c = +7e212\n" "d = 6.02e23\n" "e = .5\n");
    run("the visual helper enters no value",
        "a = 1_000\n" "b = 7_000.5_5\n");
    run("hexadecimal, binary, octal",
        "a = 0xDEAD_BEEF\n" "b = 0b0111_11_01\n" "c = 0o3124\n" "d = 0XFF\n" "e = -0b1010\n");
    run("roman",
        "a = 0rIV\n" "b = 0rMCMLXXXIV\n" "c = -0rX\n");
    run("a sign standing apart from its digits",
        "a = - 0.12\n" "b = + 7\n" "c = - 0xFF\n" "d = - -1.5e3\n");
    run("what spells no number is a string, and carries quotes",
        "a = 1.2.3\n" "b = 0x\n" "c = 0b012\n" "d = 1__0\n" "e = 0rIIII\n" "f = 0rVX\n");
    run("no arithmetic: this language computes nothing",
        "a = 5 - 1\n");
}

static void
run_quoting()
{
    run("quoted: blanks, comment markers and binders are content",
        "a = \"make %.exe\"\n" "b = \"not # a comment\"\n" "c = \"x = y\"\n" "d = \"yes\"\n");
    run("unquoted: refused, and shown in the quotes it wants",
        "a = make\n" "b = strip.pype\n" "c = [one, two]\n" "d = 1\n");
}

static void
run_structure()
{
    run("nesting and key-brace",
        "outer {\n" "    inner = { deep = 1 }\n" "    braced { x = 2 }\n" "}\n");
    run("lists",
        "commas   = [one, two, three]\n"
        "newlines = [\n" "    1\n" "    2\n" "]\n"
        "objects  = [ { a = 1 }, { a = 2 } ]\n"
        "empty    = []\n");
}

static void
run_oneline()
{
    run("two entries, one line, no comma", "caps { timeout_sec = 30  network = false }\n");
    run("a quoted value with blanks, beside a following key", "a { build = \"make %.exe\"  timeout_sec = 5 }\n");
    run("three entries, one line", "x { a = 1  b = \"two\"  c = { d = 3 } }\n");
}

static void
run_comments()
{
    run("comments",
        "# whole line\n" "a = 1   # trailing\n" "// slashes too\n" "b = 2   // trailing slashes\n"
        "c = bare value # comment cut\n");
}

static void
run_refused()
{
    run("refused, each by name",
        "include \"other.conf\"\n" "a = ${outside.value}\n" "b += appended\n" "d = survives\n");
}

static void
run_triple()
{
    run("several lines: indentation and blank ends go",
        "doc = \"\"\"\n" "    First line.\n" "\n" "      indented more\n" "    last line\n" "    \"\"\"\n" "after = 1\n");
    run("on one line; beside another entry; in a list",
        "a = \"\"\"one line\"\"\"  b = 2\n" "c = [\"\"\"x\"\"\", \"y\"]\n");
    run("as written: a quote, a backslash-n, a comment marker",
        "a = \"\"\"says \"no\" \\n # not a comment\"\"\"\n");
    run("never closed: a fault, at its beginning",
        "a = 1\n" "b = \"\"\"open\n" "c = 2\n");
}

static void
run_faults()
{
    run("faults accumulate",
        "a = 1\n" "a = 2\n" "b = \"unterminated\n" "}\n" "c {\n" "    d = 3\n");
}

static void
run_unclosed()
{
    run("a list closed by the object's brace", "@hwut { title = \"B\" choices = [ }\n" "after = 1\n");
    run("a stray character in a list", "a = [1, ; 2]\n");
}

static void
run_positions()
{
    const std::string text = "@hwut {\n" "    title = \"T\"\n" "}";
    run("plain: as its own file", text);
    run("offset: same text, region begins at line 40, 3 columns stripped", text, 39, 3);
}

/* ------------------------------------------------------------------- fuzz */
static const std::array<std::string, 2> FUZZ_SEED = { {
    "@hwut {\n"
    "    title    = \"T\"\n"
    "    choices  = [\"a\", \"b\"]\n"
    "    tolerance { eq_pattern = [\"x.*\"] }\n"
    "    n        = -1.5e3\n"
    "    f        = true\n"
    "}\n",
    "hwut {\n"
    "    target     { clean = \"./c.sh\" }\n"
    "    dependency { \"a.py\" = [\"b.py one\"] }\n"
    "    ignore     = [\"x\"]   // comment\n"
    "    # comment\n"
    "}\n"
} };
/* WHAT A TYPO IS MADE OF: the characters HOCON gives meaning to, a few that
 * it refuses by name, and some ordinary ones.                             */
static const std::vector<std::string> FUZZ_ALPHABET = {
    "{", "}", "[", "]", "\"", ",", "=", ":", "#", "/", "\\", "$", " ", "\n", "\t", "-", "+", ".", "e", "E",
    "0", "a", "\"\"\"", "${", "//", "+="
};
static const int  FUZZ_INPUT_N = 3000;
static const long FUZZ_BOUND_US = 500000;          // one parse takes well under a millisecond

static std::string
mutated(hwut::DeterministicStream& stream, std::string text)
/* RETURN: 'text' edited by one to four random insertions, deletions and
 *         duplications of a short stretch.                                */
{
    for(int64_t edit = 0, edit_n = stream.next_int(1, 4); edit < edit_n; ++edit) {
        size_t i = (size_t)stream.next_int(0, (int64_t)text.size());
        switch( stream.next_int(0, 2) ) {
        case 0:  text.insert(i, stream.select(FUZZ_ALPHABET)); break;
        case 1:  if( i < text.size() ) text.erase(i, 1);       break;
        default: {
            size_t j = (size_t)stream.next_int(0, (int64_t)text.size());
            text.insert(i, text.substr(j, 5));
        }
        }
    }
    return text;
}

static std::string the_text;                       // what the parse under way reads

static void
alarmed(int)
/* RETURN: never; a parse ran past the bound -- said, with its text, and the
 *         choice ends.                                                     */
{
    static const char said[] = "FIRST HANG:\n";
    if( write(1, said, sizeof(said) - 1) < 0 || write(1, the_text.data(), the_text.size()) < 0 ) {}
    _exit(1);
}

static void
set_timer(long microseconds)
{
    struct itimerval t;
    std::memset(&t, 0, sizeof(t));
    t.it_value.tv_sec  = microseconds / 1000000;
    t.it_value.tv_usec = microseconds % 1000000;
    setitimer(ITIMER_REAL, &t, nullptr);
}

static void
run_fuzz()
{
    hwut::DeterministicStream stream(4711);
    int         clean = 0, with_faults = 0, hang = 0, exception = 0;
    std::string first_exception;
    std::signal(SIGALRM, alarmed);
    for(int k = 0; k < FUZZ_INPUT_N; ++k) {
        std::string text = mutated(stream, stream.select(FUZZ_SEED));
        the_text = text;
        try {
            set_timer(FUZZ_BOUND_US);
            auto fault_list = hocon::parse(lines(text), "f.hocon").second;
            set_timer(0);
            if( fault_list.empty() ) ++clean; else ++with_faults;
        } catch( const std::exception& error ) {
            set_timer(0);
            ++exception;
            if( first_exception.empty() ) first_exception = std::string(error.what()) + "\n" + text;
        }
    }
    banner(std::to_string(FUZZ_INPUT_N) + " mutated headers");
    std::printf("    %-12s %d\n", "clean", clean);
    std::printf("    %-12s %d\n", "with faults", with_faults);
    std::printf("    %-12s %d\n", "hang", hang);
    std::printf("    %-12s %d\n", "exception", exception);
    if( ! first_exception.empty() ) std::printf("FIRST EXCEPTION:\n%s\n", first_exception.c_str());
}

int
main(int argc, char** argv)
{
    hwut::HwutRunner runner(argc, argv, "HOCON parser: subset (A), annotated tree;", {
        { "scalars", run_scalars }, { "numbers", run_numbers }, { "quoting", run_quoting },
        { "structure", run_structure }, { "oneline", run_oneline }, { "comments", run_comments },
        { "refused", run_refused }, { "triple", run_triple }, { "unclosed", run_unclosed },
        { "fuzz", run_fuzz }, { "faults", run_faults }, { "positions", run_positions },
    });
    return runner.run();
}
