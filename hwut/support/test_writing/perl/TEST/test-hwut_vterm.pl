#! /usr/bin/env perl
#
# @hwut {
#     title      = "A terminal's screen read by a test: libvterm through FFI::Platypus."
#     choices {
#         attributes { features = ["perl-vterm"] }
#         colours    { features = ["perl-vterm"] }
#         events     { features = ["perl-vterm"] }
#         keys       { features = ["perl-vterm"] }
#         missing    { features = ["perl-vterm"] }
#         regions    { features = ["perl-vterm"] }
#         screen     { features = ["perl-vterm"] }
#         text       { features = ["perl-vterm"] }
#         unnoticed  { features = ["perl-vterm"] }
#     }
# }
#
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# PURPOSE: The Perl port of 'python/TEST/test-hwut_vterm.py', choice for
#          choice, held against its GOOD files by '.link'. WANTS libvterm and
#          FFI::Platypus. The two APPLICATIONS a Terminal runs here are the
#          Python test's, unchanged: they are the system under test, and what
#          they print is in the shared GOOD files.
#______________________________________________________________________________
use strict;
use warnings;
use utf8;
use FindBin;
use lib "$FindBin::Bin/..";
use Hwut::Runner;
use Hwut::Vterm;
use Hwut::PyText qw(str_repr bytes_repr tuple_repr bool_text);

my $ESC = "\e";

sub shown {
    my ($screen) = @_;
    my @line = $screen->line_list;
    for my $row (0 .. $#line) { print "    $row |$line[$row]|\n" if $line[$row] ne "" }
    print "    cursor ", tuple_repr([$screen->cursor]), "\n";
}

sub error_of {
    # RETURN: Hwut::Vterm::Error, the death '$@' -- dies on with anything else.
    my ($error) = @_;
    die $error unless ref $error && $error->isa("Hwut::Vterm::Error");
    return $error;
}

sub probe {
    my ($function) = @_;
    return sub {
        binmode STDOUT, ":encoding(UTF-8)";
        eval { $function->(); 1 } and return;
        my $error = error_of($@);
        die $error unless $error->kind eq "LibraryMissing";
        print "NOT PROBED: ", $error->message, "\n";
    };
}

sub screen { Hwut::Vterm::Screen->new(@_) }

sub run_text {
    my $s = screen(4, 12);
    print "-- plain, then carriage return and line feed\n";
    $s->feed("hello\r\nworld");
    shown($s); $s->close;

    $s = screen(4, 12);
    print "-- UTF-8: two bytes, one cell; a wide character, two\n";
    $s->feed("ä日x");
    shown($s);
    for my $column (0 .. 3) {
        my $cell = $s->cell(0, $column);
        printf "    column %d: %-6s width %d\n", $column, str_repr($cell->{text}), $cell->{width};
    }
    $s->close;

    $s = screen(3, 5);
    print "-- seven characters on five columns: the line wraps\n";
    $s->feed("abcdefg");
    shown($s); $s->close;

    $s = screen(2, 4);
    print "-- a str is sent as UTF-8; the bytes taken are counted\n";
    printf "    taken: %d\n", $s->feed("aä");
    print "-- a place off the screen\n";
    eval { $s->cell(2, 0); 1 } or print "    IndexError: ", error_of($@)->message, "\n";
    $s->close;
}

sub run_screen {
    my $s = screen(5, 20);
    print "-- three lines, then '<esc>[2;4H' (it counts from 1) and 'X'\n";
    $s->feed("first line\r\nsecond line\r\nthird line");
    $s->feed("$ESC\[2;4HX");
    shown($s);
    print "-- erase to the end of that line\n";
    $s->feed("$ESC\[K");
    shown($s);
    print "-- clear the screen, home, one word\n";
    $s->feed("$ESC\[2J$ESC\[Hclean");
    shown($s);
    $s->close;
}

sub run_attributes {
    my $s = screen(3, 20);
    for my $pair (@Hwut::Vterm::ATTRIBUTE_SGR) {
        my ($name, $code) = @$pair;
        $s->feed(sprintf("%s[%sm%s%s[0m", $ESC, $code, substr($name, 0, 1), $ESC));
    }
    print "-- one cell per attribute, set by its own code\n";
    my $column = 0;
    for my $pair (@Hwut::Vterm::ATTRIBUTE_SGR) {
        my $cell = $s->cell(0, $column++);
        my $said = $cell->attribute_text || "(none)";
        $said = "conceal, or (none) on libvterm 0.1" if $pair->[0] eq "conceal";
        printf "    %s  %s\n", str_repr($cell->{text}), $said;
    }
    print "-- bold, underline and reverse at once; then reset\n";
    $s->feed("\r\n$ESC\[1;4;7mA$ESC\[0mB");
    for my $c (0, 1) {
        my $cell = $s->cell(1, $c);
        printf "    %s  %s\n", str_repr($cell->{text}), $cell->attribute_text || "(none)";
    }
    print "-- double underline (SGR 21) is underlined\n";
    $s->feed("$ESC\[21mD");
    printf "    %s  %s\n", str_repr("D"), $s->cell(1, 2)->attribute_text;
    $s->close;
}

sub colour_text { my ($c) = @_; return defined $c ? tuple_repr($c) : "None" }

sub run_colours {
    my $s = screen(2, 20);
    $s->feed("d$ESC\[31mr$ESC\[0m$ESC\[38;5;196mp$ESC\[0m$ESC\[38;2;10;20;30mt$ESC\[0m");
    $s->feed("$ESC\[48;2;1;2;3mb$ESC\[0m");
    my @what = ("default", "indexed 31", "palette 196", "direct 10;20;30", "background 1;2;3");
    for my $column (0 .. $#what) {
        my $cell = $s->cell(0, $column);
        my $said;
        if ($what[$column] eq "indexed 31") {
            my ($red, $green, $blue) = @{$cell->{foreground}};
            my $max = $green > $blue ? $green : $blue;
            $said = "fg mostly red: " . bool_text($red > 2 * $max);
        }
        else {
            $said = "fg " . colour_text($cell->{foreground}) . "  bg " . colour_text($cell->{background});
        }
        printf "    %-18s %s  %s\n", $what[$column], str_repr($cell->{text}), $said;
    }
    $s->close;
}

#  THE APPLICATIONS UNDER OBSERVATION -- the Python test's own, word for word:
#  the system under test is the same, so the GOOD files can be.
my $SEEING_APP = <<'END';

import os, sys, tty, termios
print("streams are terminals: %s %s %s"
      % (sys.stdin.isatty(), sys.stdout.isatty(), sys.stderr.isatty()))
try:    os.close(os.open("/dev/tty", os.O_RDWR)); print("controlling terminal: yes")
except OSError: print("controlling terminal: no")
print("size: %d columns, %d rows" % tuple(os.get_terminal_size()))
print("TERM=%s COLUMNS=%s" % (os.environ.get("TERM"), os.environ.get("COLUMNS")))
old = termios.tcgetattr(0); tty.setraw(0)
sys.stdout.write("\x1b[6;9H\x1b[6n"); sys.stdout.flush()
reply = b""
while not reply.endswith(b"R"): reply += os.read(0, 1)
sys.stdout.write("\r\x1b[7;1Hthe terminal answered: %r" % reply); sys.stdout.flush()
while True:
    key = os.read(0, 32)
    sys.stdout.write("\x1b[9;1H\x1b[Kread: %r" % key); sys.stdout.flush()
    if key == b"q": break
termios.tcsetattr(0, termios.TCSADRAIN, old)
print("\r\nleaving"); sys.exit(3)
END

my $DRAWING_APP = <<'END';

import os, sys, tty, termios
old = termios.tcgetattr(0); tty.setraw(0)
count, foot = 0, "q=quit"
def draw():
    out = "\x1b[2J\x1b[1;1H\x1b[7m the head \x1b[0m"
    out += "\x1b[3;1Hcount: %d\x1b[4;1H(press n)" % count
    out += "\x1b[8;1H%s" % foot
    sys.stdout.write(out); sys.stdout.flush()
draw()
while True:
    key = os.read(0, 1)
    if   key == b"n": count += 1
    elif key == b"f": foot = "q=quit  f=pressed"
    elif key == b"q": break
    draw()
termios.tcsetattr(0, termios.TCSADRAIN, old)
END

sub terminal { Hwut::Vterm::Terminal->new(@_) }

sub run_unnoticed {
    local $ENV{COLUMNS} = "300";
    my $t = terminal(10, 44);
    print "-- still running after its first screen: ",
          bool_text($t->run(["python3", "-c", $SEEING_APP])), "\n";
    shown($t);
    $t->send("q");
    print "-- after 'q': exit status ", $t->wait, "\n";
    shown($t);
    $t->close;
}

sub run_keys {
    my $t = terminal(10, 44);
    $t->region("read", row => 8);
    my $pressed = "(start)";
    $t->on_change(sub { my ($name, $line) = @_; printf "    %-22s %s\n", $pressed, $line->[0] });
    $t->run(["python3", "-c", $SEEING_APP]);
    for my $press (["up"], ["enter"], ["tab"], ["escape"], ["f5"], ["delete"],
                   ["c", "ctrl"], ["x", "alt"], ["up", "shift"]) {
        my ($key, @modifier) = @$press;
        $pressed = join(" ", @modifier, $key);
        $t->press($key, @modifier);
    }
    $pressed = "send 'ä'";
    $t->send("ä");
    $pressed = "send 'q'";
    $t->send("q");
    $t->wait;
    $t->close;
}

sub run_regions {
    #  A LONGER PAUSE THAN THE DEFAULT: three redraws typed at once must be ONE
    #  report on a loaded machine too.
    my $t = terminal(8, 30, settle_s => 0.3);
    $t->region("head", row => 0);
    $t->region("body", row => 2, row_n => 2);
    $t->region("foot", row => -1);
    $t->on_change(sub { my ($name, $line) = @_;
                        printf "    changed  %-5s %s\n", $name, Hwut::PyText::list_repr($line, 1) });
    for my $act (["run",                         sub { $t->run(["python3", "-c", $DRAWING_APP]) }],
                 ["'n'",                         sub { $t->send("n") }],
                 ["'n'",                         sub { $t->send("n") }],
                 ["'r': a redraw, nothing new",  sub { $t->send("r") }],
                 ["'f'",                         sub { $t->send("f") }],
                 ["'nnn', typed at once",        sub { $t->send("nnn") }],
                 ["'q'",                         sub { $t->send("q") }]) {
        print "-- $act->[0]\n";
        $act->[1]->();
    }
    my $status = $t->wait;
    print "-- exit status $status; a region asked by name: ",
          Hwut::PyText::list_repr([$t->region_text("body")], 1), "\n";
    eval { $t->region_text("nosuch"); 1 }
        or print "-- no such region: KeyError ", error_of($@)->message, "\n";
    $t->close;
}

sub run_events {
    my $t = terminal(4, 20);
    $t->on_event(sub { print "    $_[0]\n" });
    for my $fed (["'ab'",                                      "ab"],
                 ["a line feed and 'c'",                       "\r\nc"],
                 ["the cursor to row 4, hidden",               "$ESC\[4;1H$ESC\[?25l"],
                 ["the alternate screen",                      "$ESC\[?1049h"],
                 ["the bell",                                  "\x07"],
                 ["nothing that draws: a reset of attributes", "$ESC\[0m"]) {
        print "-- fed: $fed->[0]\n";
        $t->feed($fed->[1]);
    }
    print "-- asked where the cursor is, nobody running: the answer waits\n";
    $t->feed("$ESC\[2;5H$ESC\[6n");
    print "    answer() = ", bytes_repr($t->answer), "\n";
    print "-- a key pressed with nobody running\n";
    $t->press("f1", { react_s => 0 });
    print "    answer() = ", bytes_repr($t->answer), "\n";
    $t->close;
}

sub run_missing {
    $ENV{$Hwut::Vterm::LIBRARY_VARIABLE} = "/nowhere/libvterm.so";
    Hwut::Vterm::reset_library();
    if (eval { Hwut::Vterm::Screen->new; 1 }) {
        print "a Screen stands on a library that is not there\n";
        return;
    }
    my $error = error_of($@);
    #  THE SYSTEM'S OWN WORDS for the failed load are left out; what this
    #  module says -- the line, and the way to install -- stands.
    my @line = split /\n/, $error->message;
    print $error->kind, ": ", (split / -- /, $line[0])[0], "\n";
    print "$_\n" for @line[1 .. $#line];
}

Hwut::Runner->new(
    argv       => \@ARGV,
    title      => "A terminal's screen read by a test: libvterm through FFI::Platypus.",
    choice_map => {
        text       => probe(\&run_text),
        screen     => probe(\&run_screen),
        attributes => probe(\&run_attributes),
        colours    => probe(\&run_colours),
        unnoticed  => probe(\&run_unnoticed),
        keys       => probe(\&run_keys),
        regions    => probe(\&run_regions),
        events     => probe(\&run_events),
        missing    => \&run_missing,
    },
)->run;
