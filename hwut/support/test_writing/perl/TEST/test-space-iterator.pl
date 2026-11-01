#! /usr/bin/env perl
#
# @hwut {
#     title      = "space_iterator: every combination of a parameter basis"
#     choices {
#         product { features = ["perl-space"] }
#         edges   { features = ["perl-space"] }
#     }
#     interactive = true
# }
#
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# PURPOSE: The Perl port of 'python/TEST/test-space-iterator.py', held against
#          its GOOD files by '.link'.
#______________________________________________________________________________
use strict;
use warnings;
use FindBin;
use lib "$FindBin::Bin/..";
use Hwut::Runner;
use Hwut::SpaceIterator qw(space_iterator);

sub banner { my ($label) = @_; print "\n--- $label ---\n" }

sub points {
    my ($basis) = @_;
    my ($next, $n) = (space_iterator($basis), 0);
    while (my $point = $next->()) {
        print "  (", join(", ", @$point), ")\n";
        $n += 1;
    }
    print "  $n point(s)\n";
}

sub run_product {
    banner("[0, 2, 4] x [otto, heinz] x [1, 2] -- 3 * 2 * 2 points");
    points([[0, 2, 4], ["otto", "heinz"], [1, 2]]);
}

sub run_edges {
    banner("an EMPTY basis -- one point, the empty one");
    points([]);
    banner("a basis with an EMPTY dimension -- nothing");
    points([[1, 2], [], [3]]);
    banner("ONE dimension -- its values one by one");
    points([["a", "b", "c"]]);
}

Hwut::Runner->new(
    argv       => \@ARGV,
    title      => "space_iterator: every combination of a parameter basis",
    choice_map => { product => \&run_product, edges => \&run_edges },
)->run;
