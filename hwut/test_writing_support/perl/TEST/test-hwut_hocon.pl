#! /usr/bin/env perl
#
# @hwut {
#     title      = "HOCON parser: subset (A), annotated tree"
#     choices {
#         comments  { features = ["perl-hocon"] }
#         faults    { features = ["perl-hocon"] }
#         fuzz      { features = ["perl-hocon"] }
#         numbers   { features = ["perl-hocon"] }
#         oneline   { features = ["perl-hocon"] }
#         positions { features = ["perl-hocon"] }
#         quoting   { features = ["perl-hocon"] }
#         refused   { features = ["perl-hocon"] }
#         scalars   { features = ["perl-hocon"] }
#         structure { features = ["perl-hocon"] }
#         triple    { features = ["perl-hocon"] }
#         unclosed  { features = ["perl-hocon"] }
#     }
#     interactive = true
# }
#
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# PURPOSE: The Perl port of 'python/TEST/test-hwut_hocon.py', choice for
#          choice, held against its GOOD files by '.link': the two parsers
#          owe the same tree, the same positions, the same faults -- and, in
#          'fuzz', the same verdict on 3000 mutated headers drawn from the
#          same seed.
#______________________________________________________________________________
use strict;
use warnings;
use FindBin;
use lib "$FindBin::Bin/..";
use Time::HiRes qw(ualarm);
use Hwut::Runner;
use Hwut::Hocon;
use Hwut::DeterministicRandom;
use Hwut::PyText qw(float_repr str_repr);

sub banner { my ($label) = @_; print "\n--- $label ---\n" }

sub lines {
    # RETURN: array ref of SourceLines, 'text' split, offsets applied.
    my ($text, $line_offset, $column_offset) = @_;
    my @text = split /\n/, $text, -1;
    return [map { Hwut::Hocon::SourceLine->new($text[$_], $_ + 1 + ($line_offset // 0),
                                               $column_offset // 0) } 0 .. $#text];
}

#  THE VALUE AS PYTHON'S TEST PRINTS IT: '%r (<type name>)'.
my %TYPE_NAME = (str => "str", int => "int", float => "float", bool => "bool", null => "NoneType");

sub value_repr {
    my ($node) = @_;
    my $kind = $node->kind;
    return "None"                          if $kind eq "null";
    return $node->value ? "True" : "False" if $kind eq "bool";
    return str_repr($node->value)          if $kind eq "str";
    return float_repr($node->value)        if $kind eq "float";
    return $node->value;
}

sub show {
    my ($node, $indent) = @_;
    $indent //= 0;
    my $pad = "    " x $indent;
    if ($node->isa("Hwut::Hocon::Object")) {
        print "$pad\{ at ", $node->position, "\n";
        for my $entry ($node->entry_list) {
            print "$pad  key '", $entry->key, "' at ", $entry->key_position, " ->\n";
            show($entry->node, $indent + 1);
        }
        print "$pad}\n";
    }
    elsif ($node->isa("Hwut::Hocon::List")) {
        print "$pad\[ at ", $node->position, "\n";
        show($_, $indent + 1) for $node->item_list;
        print "$pad]\n";
    }
    else {
        printf "%s%s (%s) at %s\n", $pad, value_repr($node), $TYPE_NAME{$node->kind}, $node->position;
    }
}

sub run {
    my ($label, $text, $line_offset, $column_offset) = @_;
    banner($label);
    my ($document, $fault_list) = Hwut::Hocon::parse(lines($text, $line_offset, $column_offset), "f.hocon");
    show($document);
    print "FAULT $_\n" for @$fault_list;
}

sub test_scalars {
    run("scalars",
        "a = bare\n"
      . "b = \"quoted \\\"x\\\" and \\n\"\n"
      . "c = 42\n"
      . "d = -3.14\n"
      . "e = 1e-6\n"
      . "f = true\n"
      . "g = no\n"
      . "h = make %.exe\n"
      . "i: \"colon-bound\"\n"
      . "j = null\n"
      . "k = nihil\n"
      . "l =\n");
}

sub test_numbers {
    run("decimal, with sign and exponent",
        "a = 42\nb = -0.12\nc = +7e212\nd = 6.02e23\ne = .5\n");
    run("the visual helper enters no value",
        "a = 1_000\nb = 7_000.5_5\n");
    run("hexadecimal, binary, octal",
        "a = 0xDEAD_BEEF\nb = 0b0111_11_01\nc = 0o3124\nd = 0XFF\ne = -0b1010\n");
    run("roman",
        "a = 0rIV\nb = 0rMCMLXXXIV\nc = -0rX\n");
    run("a sign standing apart from its digits",
        "a = - 0.12\nb = + 7\nc = - 0xFF\nd = - -1.5e3\n");
    run("what spells no number is a string, and carries quotes",
        "a = 1.2.3\nb = 0x\nc = 0b012\nd = 1__0\ne = 0rIIII\nf = 0rVX\n");
    run("no arithmetic: this language computes nothing",
        "a = 5 - 1\n");
}

sub test_quoting {
    run("quoted: blanks, comment markers and binders are content",
        "a = \"make %.exe\"\nb = \"not # a comment\"\nc = \"x = y\"\nd = \"yes\"\n");
    run("unquoted: refused, and shown in the quotes it wants",
        "a = make\nb = strip.pype\nc = [one, two]\nd = 1\n");
}

sub test_structure {
    run("nesting and key-brace",
        "outer {\n    inner = { deep = 1 }\n    braced { x = 2 }\n}\n");
    run("lists",
        "commas   = [one, two, three]\n"
      . "newlines = [\n    1\n    2\n]\n"
      . "objects  = [ { a = 1 }, { a = 2 } ]\n"
      . "empty    = []\n");
}

sub test_oneline {
    run("two entries, one line, no comma",
        "caps { timeout_sec = 30  network = false }\n");
    run("a quoted value with blanks, beside a following key",
        "a { build = \"make %.exe\"  timeout_sec = 5 }\n");
    run("three entries, one line",
        "x { a = 1  b = \"two\"  c = { d = 3 } }\n");
}

sub test_comments {
    run("comments",
        "# whole line\na = 1   # trailing\n// slashes too\nb = 2   // trailing slashes\n"
      . "c = bare value # comment cut\n");
}

sub test_refused {
    run("refused, each by name",
        "include \"other.conf\"\na = \${outside.value}\nb += appended\nd = survives\n");
}

sub test_triple {
    my $q = '"""';
    run("several lines: indentation and blank ends go",
        "doc = $q\n    First line.\n\n      indented more\n    last line\n    $q\nafter = 1\n");
    run("on one line; beside another entry; in a list",
        "a = ${q}one line$q  b = 2\nc = [${q}x$q, \"y\"]\n");
    run("as written: a quote, a backslash-n, a comment marker",
        "a = ${q}says \"no\" \\n # not a comment$q\n");
    run("never closed: a fault, at its beginning",
        "a = 1\nb = ${q}open\nc = 2\n");
}

sub test_faults {
    run("faults accumulate",
        "a = 1\na = 2\nb = \"unterminated\n}\nc {\n    d = 3\n");
}

sub test_unclosed {
    run("a list closed by the object's brace",
        "\@hwut { title = \"B\" choices = [ }\nafter = 1\n");
    run("a stray character in a list",
        "a = [1, ; 2]\n");
}

my @FUZZ_SEED = (
    "\@hwut {\n"
  . "    title    = \"T\"\n"
  . "    choices  = [\"a\", \"b\"]\n"
  . "    tolerance { eq_pattern = [\"x.*\"] }\n"
  . "    n        = -1.5e3\n"
  . "    f        = true\n"
  . "}\n",
    "hwut {\n"
  . "    target     { clean = \"./c.sh\" }\n"
  . "    dependency { \"a.py\" = [\"b.py one\"] }\n"
  . "    ignore     = [\"x\"]   // comment\n"
  . "    # comment\n"
  . "}\n");

#  WHAT A TYPO IS MADE OF -- the Python test's alphabet, in its order.
my @FUZZ_ALPHABET = ((split //, "{}[]\",=:#/\\\$ \n\t-+.eE0a"), '"""', '${', '//', '+=');
my $FUZZ_INPUT_N  = 3000;
my $FUZZ_BOUND_US = 500_000;

sub mutated {
    # RETURN: string, 'text' edited by one to four random insertions,
    #         deletions and duplications of a short stretch -- the Python
    #         test's edits, draw for draw.
    my ($stream, $text) = @_;
    for (1 .. $stream->next_int(1, 4)) {
        my $i = $stream->next_int(0, length $text);
        my $how = $stream->next_int(0, 2);
        if ($how == 0) {
            $text = substr($text, 0, $i) . $stream->select(\@FUZZ_ALPHABET) . substr($text, $i);
        }
        elsif ($how == 1) {
            $text = substr($text, 0, $i) . ($i + 1 <= length $text ? substr($text, $i + 1) : "");
        }
        else {
            my $j = $stream->next_int(0, length $text);
            $text = substr($text, 0, $i) . substr($text, $j, 5) . substr($text, $i);
        }
    }
    return $text;
}

sub test_fuzz {
    my $stream = Hwut::DeterministicStream->new(4711);
    my %tally  = ("clean" => 0, "with faults" => 0, "hang" => 0, "exception" => 0);
    my %example;
    for (1 .. $FUZZ_INPUT_N) {
        my $text = mutated($stream, $stream->select(\@FUZZ_SEED));
        my $ok = eval {
            local $SIG{ALRM} = sub { die "Hang\n" };
            ualarm($FUZZ_BOUND_US);
            my (undef, $fault_list) = Hwut::Hocon::parse(lines($text), "f.hocon");
            ualarm(0);
            $tally{@$fault_list ? "with faults" : "clean"} += 1;
            1;
        };
        next if $ok;
        ualarm(0);
        if ($@ eq "Hang\n") { $tally{hang} += 1; $example{hang} //= $text }
        else                { $tally{exception} += 1; $example{exception} //= "$@\n$text" }
    }
    banner("$FUZZ_INPUT_N mutated headers");
    printf "    %-12s %d\n", $_, $tally{$_} for ("clean", "with faults", "hang", "exception");
    for my $key (grep { exists $example{$_} } ("hang", "exception")) {
        print "FIRST ", uc $key, ":\n$example{$key}\n";
    }
}

sub test_positions {
    my $text = "\@hwut {\n    title = \"T\"\n}";
    run("plain: as its own file", $text);
    run("offset: same text, region begins at line 40, 3 columns stripped", $text, 39, 3);
}

Hwut::Runner->new(
    argv       => \@ARGV,
    title      => "HOCON parser: subset (A), annotated tree;",
    choice_map => {
        scalars   => \&test_scalars,
        numbers   => \&test_numbers,
        quoting   => \&test_quoting,
        structure => \&test_structure,
        oneline   => \&test_oneline,
        comments  => \&test_comments,
        refused   => \&test_refused,
        triple    => \&test_triple,
        unclosed  => \&test_unclosed,
        fuzz      => \&test_fuzz,
        faults    => \&test_faults,
        positions => \&test_positions,
    },
)->run;
