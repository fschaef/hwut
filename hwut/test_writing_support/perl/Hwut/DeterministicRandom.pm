# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# PURPOSE: A RANDOM STREAM THAT IS THE SAME EVERYWHERE -- the port of
#          'python/deterministic_random.py'. The same seed gives the same
#          numbers as the Python module, draw for draw: the core is Park-Miller
#          MINSTD, 'state = 48271 * state mod (2^31 - 1)', integer arithmetic
#          that fits a 64-bit integer exactly.
#
#     my $s = Hwut::DeterministicStream->new(0x42);
#     $s->next_int(0, 9);         $s->next_float;       $s->coin(0.5);
#     $s->select(\@pool);         $s->choice(\@pool);   $s->gauss(0, 1);
#     $s->sample_indices(10, 3);  $s->sample(\@pool, 3);
#
#     my $m = Hwut::SelectionMarker->new;
#     $s->select_unchosen(\@pool, $m);   # prefers what 'm' has not seen
#
# 'gauss' is the one path through the platform's libm, as in Python: a last
# bit may differ between languages, so a GOOD that prints a draw tolerates
# the last digits.
#
# IDENTITY IN PERL: Python's marker remembers candidates by 'id(object)'. A
# Perl list of strings holds copies, not objects, so here a candidate is
# remembered by its REFERENCE where it is one, and by its value where it is a
# plain scalar -- two equal strings are then one candidate.
#______________________________________________________________________________
package Hwut::DeterministicRandom;
use strict;
use warnings;
1;


package Hwut::SelectionMarker;
use strict;
use warnings;

sub new {
    # RETURN: Hwut::SelectionMarker, with nothing chosen yet.
    my ($class) = @_;
    return bless { chosen => {} }, $class;
}

sub reset {
    # RETURN: nothing. Forgets every chosen candidate; the next cycle restarts.
    my ($self) = @_;
    %{$self->{chosen}} = ();
}

sub key_of {
    # RETURN: string, how the marker names 'candidate': its address where it is
    #         a reference, its value else.
    my ($class, $candidate) = @_;
    return ref $candidate ? "ref:" . (0 + $candidate) : "val:$candidate";
}


package Hwut::DeterministicStream;
use strict;
use warnings;
use POSIX ();

my $MODULUS = 2147483647;
my $PI      = 4 * atan2(1, 1);

sub new {
    # RETURN: Hwut::DeterministicStream, seeded with 'seed' (0x42 where none).
    my ($class, $seed) = @_;
    $seed //= 0x42;
    return bless { state => $seed & 0x7FFFFFFF }, $class;
}

sub next_int {
    # RETURN: integer, uniform in [v_min, v_max]. The state steps even where
    #         the range is a single value.
    my ($self, $v_min, $v_max) = @_;
    $self->{state} = (48271 * $self->{state}) % $MODULUS;
    return $v_min if $v_min == $v_max;
    return $v_min + ($self->{state} % ($v_max - $v_min + 1));
}

sub next_float {
    # RETURN: number, in [0, 1): 1000001 values, 'next_int(0, 1000000) / 1000001'.
    my ($self) = @_;
    return $self->next_int(0, 1000000) / 1000001.0;
}

sub coin {
    # RETURN: 1 with probability 'p', 0 else -- resolved in steps of 1/1000001.
    my ($self, $p) = @_;
    return $self->next_float < $p ? 1 : 0;
}

sub select {
    # RETURN: one element of the array ref 'candidates', uniformly drawn.
    my ($self, $candidates) = @_;
    return $candidates->[$self->next_int(0, $#$candidates)];
}

sub choice {
    # RETURN: one element of the array ref 'seq', uniformly drawn.
    my ($self, $seq) = @_;
    return $seq->[$self->next_int(0, $#$seq)];
}

sub select_unchosen {
    # RETURN: one candidate the marker has not seen, uniformly drawn among those
    #         -- recorded in the marker. Where every candidate was seen, the
    #         marker is reset and the draw is over all of them.
    my ($self, $candidates, $marker) = @_;
    my @unchosen = grep { !$marker->{chosen}{Hwut::SelectionMarker->key_of($_)} } @$candidates;
    if (!@unchosen) {
        $marker->reset;
        @unchosen = @$candidates;
    }
    my $choice = $unchosen[$self->next_int(0, $#unchosen)];
    $marker->{chosen}{Hwut::SelectionMarker->key_of($choice)} = 1;
    return $choice;
}

sub gauss {
    # RETURN: number, a draw of the normal distribution (mu, sigma) by the
    #         Box-Muller transform, clipped to [lower, upper] where given.
    my ($self, $mu, $sigma, $lower, $upper) = @_;
    my $u1 = $self->next_float + 1e-9;
    my $u2 = $self->next_float;
    my $z0 = sqrt(-2.0 * log($u1)) * cos(2.0 * $PI * $u2);
    my $result = $z0 * $sigma + $mu;
    return $lower if defined $lower && $result < $lower;
    return $upper if defined $upper && $result > $upper;
    return $result;
}

sub gauss_int {
    # RETURN: integer, 'gauss' rounded to the nearest -- a half to the even one,
    #         as Python's 'round'.
    my ($self, $mu, $sigma, $lower, $upper) = @_;
    return 0 + sprintf("%.0f", $self->gauss($mu, $sigma, $lower, $upper));
}

sub sample_indices {
    # RETURN: list of 'k' distinct indices of 0 .. population_size - 1, drawn by
    #         Fisher-Yates.
    my ($self, $population_size, $k) = @_;
    die "sample_indices: $k > $population_size\n" if $k > $population_size;
    my @index = (0 .. $population_size - 1);
    my @result;
    for my $i (0 .. $k - 1) {
        my $j = $self->next_int($i, $population_size - 1);
        @index[$i, $j] = @index[$j, $i];
        push @result, $index[$i];
    }
    return @result;
}

sub sample {
    # RETURN: list of 'n' distinct elements of the array ref 'population'.
    my ($self, $population, $n) = @_;
    return map { $population->[$_] } $self->sample_indices(scalar @$population, $n);
}

1;
