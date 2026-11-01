#! /usr/bin/env perl
#
# @hwut {
#     title   = "Demo: a recursive build, serial and parallel -- one summary, by a pype system"
#     pype    = "build.pypes"
#     same    = true
#     choices = ["serial", "parallel"]
#     features = ["pype-in-header", "pype-system", "same-nominal", "choices-as-list",
#                 "pype-push-pop", "pype-entry-exit", "pype-import", "pype-repeat-group",
#                 "pype-quantity", "pype-anchors-globs-flush"]
#     tolerance { constraints = ["compile < 5 s", "breaches == 0"] }
# }
#
#______________________________________________________________________________
# SUBJECT  the log of a recursive build -- configure, then the directories
#          'lib', 'app' and, inside 'app', 'app/plugins' -- and the summary
#          a pype system makes of it.
# REQUIREMENT  A parallel build builds what the serial build builds: the same
#              sources, the same warnings, the same archives and the same
#              program, linked from the same parts.
#
# The application only REPORTS the build as it happens, as 'make -w' would.
# The header's 'pype = "build.pypes"' puts a SYSTEM of two pype scripts
# between it and the comparison (hwut runs it; the application prints no
# '<hwut-end>'):
#
#     build.pypes       --> normalise.pype         stdin to the first
#                       normalise.pype --> build.pype
#     normalise.pype    a parallel build tags each line with its job,
#                       'job2: cc -c ...'; the tag goes, every other line
#                       passes unchanged ('flush')
#     build.pype        the summary, sorted -- see its own comments: modes
#                       pushed on 'Entering directory' and popped on
#                       'Leaving' (nested: 'app/plugins' inside 'app'),
#                       '<entry>'/'<exit>' around each, a vocabulary
#                       imported from 'compiler.pype', a repeat group over
#                       the parts of a link, durations read as quantities
#
# 'same = true': BOTH CHOICES SHARE ONE GOOD, 'GOOD/build.pl.txt'. Serial or
# parallel, the summary must be the same -- that is the requirement, and
# the header says it once. 'choices' is a list: no choice states anything
# of its own.
#
# The laws: the compile times sum to under 5 s ('((compile: ...))', in
# s, whatever unit the log used), and nothing in the log broke the build's
# grammar ('((breaches: 0))').
#
# A HEADER'S PYPE READS THE OUTPUT AFTER THE RUN: the whole stream at once.
# Time as the pype sees it -- 'pype.time()', 'tick:' -- is no time of the
# build here; a pype that judges time is fed live ('protocol.sh slow').
#______________________________________________________________________________
use strict;
use warnings;
use threads;
use threads::shared;
use Time::HiRes qw(sleep time);

$| = 1;

#  What each directory does: its sources, warnings and products.
my %DIRECTORY = (
    "lib" =>
        { source_list => ["lib/str.c", "lib/num.c", "lib/map.c"],
          warning     => { "lib/num.c" => "lib/num.c:14:9: warning: unused variable 'n'" },
          product     => "ar rcs lib/libcore.a lib/str.o lib/num.o lib/map.o" },
    "app/plugins" =>
        { source_list => ["app/plugins/png.c", "app/plugins/svg.c"],
          warning     => { "app/plugins/svg.c" => "app/plugins/svg.c:3:1: warning: implicit declaration of 'xml_open'" },
          product     => "ar rcs app/plugins/libplug.a app/plugins/png.o app/plugins/svg.o" },
    "app" =>
        { source_list => ["app/main.c", "app/cli.c"],
          warning     => {},
          product     => "ld -o app/demo app/main.o app/cli.o lib/libcore.a app/plugins/libplug.a" },
);


sub compile_lines {
    # RETURN: list of strings, what building directory 'name' prints, its
    #         sources compiled in the time each takes.
    my ($name) = @_;
    my $spec = $DIRECTORY{$name};
    my @line;
    for my $source (@{$spec->{source_list}}) {
        my $took = 0.04 + rand(0.08);
        sleep $took;
        my $spent = $took < 0.1 ? sprintf("%d ms", $took * 1000) : sprintf("%.2f s", $took);
        (my $object = $source) =~ s/\.c$/.o/;
        push @line, "cc -c $source -o $object (took $spent)";
        push @line, $spec->{warning}{$source} if exists $spec->{warning}{$source};
    }
    return @line;
}


sub directory_block {
    # RETURN: list of strings, the block 'make -w' prints for 'name' at
    #         'level', the block of 'inner' nested before the product.
    my ($name, $level, $inner) = @_;
    my @line = ("make[$level]: Entering directory '$name'");
    push @line, compile_lines($name);
    push @line, directory_block($inner, $level + 1) if defined $inner;
    push @line, $DIRECTORY{$name}{product};
    push @line, "make[$level]: Leaving directory '$name'";
    return @line;
}


sub configure {
    # RETURN: nothing. Prints what 'configure' prints, and that make enters
    #         the top directory.
    print "configure: checking for cc... cc\n";
    print "configure: checking for ar... ar\n";
    print "make: Entering directory 'demo'\n";
}


sub serial {
    # RETURN: nothing. Builds one directory after the other.
    configure();
    print "$_\n" for directory_block("lib", 1), directory_block("app", 1, "app/plugins");
    print "make: Leaving directory 'demo'\n";
}


sub parallel {
    # RETURN: nothing. Builds 'lib' and 'app' at once. Each job prints its
    #         block whole when done ('make -O'), every line tagged with the
    #         job; which job finishes first is the scheduler's.
    configure();
    my $lock :shared;
    my $job = sub {
        my ($slot, $seed, $name, $inner) = @_;
        srand($seed);                                  # a stream of its own
        my @block = directory_block($name, 1, $inner);
        lock $lock;
        print "job$slot: $_\n" for @block;
    };
    my @pool = (threads->create($job, 1, int rand 2**31, "lib"),
                threads->create($job, 2, int rand 2**31, "app", "app/plugins"));
    $_->join for @pool;
    print "make: Leaving directory 'demo'\n";
}


my %CHOICE = (serial => \&serial, parallel => \&parallel);

srand(int(time * 1e6) % 2**31);
my $choice = $ARGV[0] // "";
unless ($CHOICE{$choice}) {
    print "choices: serial, parallel\n";
    exit 1;
}
$CHOICE{$choice}->();
