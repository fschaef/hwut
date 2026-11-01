# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# PURPOSE: EVERY COMBINATION OF A PARAMETER BASIS -- the port of
#          'python/space_iterator.py': the cartesian product, the RIGHTMOST
#          dimension changing fastest.
#
#     use Hwut::SpaceIterator qw(space_iterator space_points);
#
#     my $next = space_iterator([[0, 2, 4], ["otto", "heinz"], [1, 2]]);
#     while (my $point = $next->()) {
#         my ($x, $name, $number) = @$point;
#         ...
#     }
#
#     for my $point (space_points($basis)) { ... }      # all at once
#
# yields  0 otto 1,  0 otto 2,  0 heinz 1,  0 heinz 2,  2 otto 1,  ...
#
# An empty basis yields exactly one point, the empty one; a basis with an
# empty dimension yields nothing -- as Python's 'itertools.product'.
#______________________________________________________________________________
package Hwut::SpaceIterator;
use strict;
use warnings;
use Exporter 'import';

our @EXPORT_OK = qw(space_iterator space_points);


sub space_iterator {
    # RETURN: code ref, which returns the next point -- an array ref holding
    #         one value of each dimension of the array ref 'basis', in order
    #         -- on each call, and undef once every point was returned.
    my ($basis) = @_;
    my @dimension = map { [@$_] } @$basis;
    my $empty_f   = grep { !@$_ } @dimension;
    my @index     = (0) x @dimension;
    my $done_f    = $empty_f ? 1 : 0;
    return sub {
        return undef if $done_f;
        my @point = map { $dimension[$_][$index[$_]] } 0 .. $#dimension;
        #  THE ODOMETER: the rightmost index steps; one that wraps carries left.
        my $i = $#dimension;
        while ($i >= 0) {
            last if ++$index[$i] < @{$dimension[$i]};
            $index[$i--] = 0;
        }
        $done_f = 1 if $i < 0;
        return \@point;
    };
}


sub space_points {
    # RETURN: list of array refs, every point of the array ref 'basis', in the
    #         order 'space_iterator' returns them.
    my ($basis) = @_;
    my $next = space_iterator($basis);
    my @point;
    while (my $p = $next->()) { push @point, $p }
    return @point;
}

1;
