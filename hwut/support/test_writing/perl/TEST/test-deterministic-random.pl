#! /usr/bin/env perl
#
# @hwut {
#     title      = "DeterministicStream RNG and SelectionMarker spread"
#     choices {
#         gauss      { features = ["perl-random"] }
#         primitives { features = ["perl-random"] }
#         ranges     { features = ["perl-random"] }
#         sample     { features = ["perl-random"] }
#         seed_sweep { features = ["perl-random"] }
#         select     { features = ["perl-random"] }
#         unchosen   { features = ["perl-random"] }
#     }
#     interactive = true
# }
#
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# PURPOSE: The Perl port of 'python/TEST/test-deterministic-random.py', choice
#          for choice. Its GOOD files are the Python test's, by '.link': the
#          two modules owe the same stream, byte for byte.
#______________________________________________________________________________
use strict;
use warnings;
use FindBin;
use lib "$FindBin::Bin/..";
use Hwut::Runner;
use Hwut::DeterministicRandom;
use Hwut::PyText qw(float_repr list_repr);

my $SEED = 0x42;

#  THE ONE PLACE THE LIBM PATH IS TOLERATED, as in the Python test.
my $TOLERANCE_REGION_BEGIN = "##! table numeric={1:1e-12}";
my $REGION_END             = "####";

sub banner { my ($label) = @_; print "\n--- $label ---\n" }
sub stream { Hwut::DeterministicStream->new($SEED) }

sub run_primitives {
    banner("next_int(0, 1000000) -- first 20");
    my $s = stream();
    printf "[%02d] %d\n", $_, $s->next_int(0, 1000000) for 0 .. 19;

    banner("next_float -- first 10 (full precision)");
    $s = stream();
    printf "[%02d] %s\n", $_, float_repr($s->next_float) for 0 .. 9;

    banner("coin(0.5) -- 40 draws");
    $s = stream();
    print join(" ", map { $s->coin(0.5) ? "T" : "F" } 1 .. 40), "\n";
}

sub run_ranges {
    banner("next_int(0, 9) -- 30 draws");
    my $s = stream();
    print join(" ", map { $s->next_int(0, 9) } 1 .. 30), "\n";

    banner("next_int(5, 5) -- degenerate range returns the bound");
    $s = stream();
    print join(" ", map { $s->next_int(5, 5) } 1 .. 5), "\n";

    banner("next_int(-3, 3) -- spanning zero");
    $s = stream();
    print join(" ", map { sprintf "%+d", $s->next_int(-3, 3) } 1 .. 20), "\n";
}

sub run_gauss {
    banner("gauss(0, 1) -- 10 draws (full precision)");
    my $s = stream();
    print "$TOLERANCE_REGION_BEGIN\n";
    printf "[%02d] %s\n", $_, float_repr($s->gauss(0.0, 1.0)) for 0 .. 9;
    print "$REGION_END\n";

    banner("gauss(0, 1) clamped to [-1, 1]");
    $s = stream();
    print "$TOLERANCE_REGION_BEGIN\n";
    printf "[%02d] %s\n", $_, float_repr($s->gauss(0.0, 1.0, -1.0, 1.0)) for 0 .. 9;
    print "$REGION_END\n";

    banner("gauss_int(100, 15) -- 20 draws");
    $s = stream();
    print join(" ", map { $s->gauss_int(100.0, 15.0) } 1 .. 20), "\n";
}

sub run_sample {
    banner("sample_indices(10, 10) -- full permutation");
    my $s = stream();
    print list_repr([$s->sample_indices(10, 10)]), "\n";

    banner("sample_indices(20, 5) -- partial draw");
    $s = stream();
    print list_repr([$s->sample_indices(20, 5)]), "\n";

    banner("choice from a list -- 20 draws");
    $s = stream();
    my @pool = qw(alpha beta gamma delta epsilon);
    print join(" ", map { $s->choice(\@pool) } 1 .. 20), "\n";

    banner("sample(list, 4) -- unique elements");
    $s = stream();
    print list_repr([$s->sample([split //, "ABCDEFGH"], 4)], 1), "\n";
}

sub run_select {
    banner("select over a list -- 20 draws");
    my $s = stream();
    my @pool = qw(a b c d);
    print join(" ", map { $s->select(\@pool) } 1 .. 20), "\n";

    banner("select over a tuple -- 12 draws");
    $s = stream();
    my @branch = qw(p q r);
    print join(" ", map { $s->select(\@branch) } 1 .. 12), "\n";
}

sub run_unchosen {
    banner("stable pool -- three full cycles of 4 elements");
    my $s = stream();
    my @pool = qw(a b c d);
    my $m = Hwut::SelectionMarker->new;
    print join(" ", map { $s->select_unchosen(\@pool, $m) } 1 .. 12), "\n";

    banner("FRESH container each call -- identical to the stable pool above");
    $s = stream();
    $m = Hwut::SelectionMarker->new;
    my @out;
    for (1 .. 12) {
        my @fresh = qw(a b c d);            # a new array every call
        push @out, $s->select_unchosen(\@fresh, $m);
    }
    print join(" ", @out), "\n";

    banner("sub-pool coherence -- draw from [a,b] then the full [a,b,c,d]");
    $s = stream();
    $m = Hwut::SelectionMarker->new;
    my @full = qw(a b c d);
    my @sub  = qw(a b);
    my $first = $s->select_unchosen(\@sub, $m);
    my @rest  = map { $s->select_unchosen(\@full, $m) } 1 .. 3;
    print "first(from sub): $first  then(from full): ", join(" ", @rest), "\n";

    banner("reset() restarts the cycle");
    $s = stream();
    @pool = qw(a b c d);
    $m = Hwut::SelectionMarker->new;
    my @before = map { $s->select_unchosen(\@pool, $m) } 1 .. 4;
    $m->reset;
    my @after  = map { $s->select_unchosen(\@pool, $m) } 1 .. 4;
    print "before reset: ", join(" ", @before), "\n";
    print "after  reset: ", join(" ", @after), "\n";
}

sub run_seed_sweep {
    banner("first next_int(0, 1000000) per seed 0..15");
    for my $seed (0 .. 15) {
        my $s = Hwut::DeterministicStream->new($seed);
        printf "seed=%2d -> %d\n", $seed, $s->next_int(0, 1000000);
    }
}

Hwut::Runner->new(
    argv       => \@ARGV,
    title      => "DeterministicStream RNG and SelectionMarker spread",
    choice_map => {
        primitives => \&run_primitives,
        ranges     => \&run_ranges,
        gauss      => \&run_gauss,
        sample     => \&run_sample,
        select     => \&run_select,
        unchosen   => \&run_unchosen,
        seed_sweep => \&run_seed_sweep,
    },
)->run;
