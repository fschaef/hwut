#! /usr/bin/env perl
#
# @hwut {
#     title    = "Demo: a garage's space counter -- a space, a stream and races, generated"
#     interactive = true
#     choices {
#         space       { features = ["space-from-hocon", "space-iterator", "hwut-runner"]
#                       tolerance { constraints = ["mismatches == 0"] } }
#         random      { features = ["deterministic-stream", "hwut-runner"]
#                       tolerance { constraints = ["mismatches == 0"] } }
#         race-naive  { features = ["deterministic-timeline", "space-iterator", "hwut-runner"]
#                       tolerance { constraints = ["overbooked > 0"] } }
#         race-atomic { features = ["deterministic-timeline", "space-iterator", "hwut-runner"]
#                       tolerance { constraints = ["overbooked == 0"] } }
#     }
# }
#
#______________________________________________________________________________
# SUBJECT  the counter of free spaces at a garage's gates: which cars it
#          admits, which it refuses, and how many stand inside.
# REQUIREMENT  The garage admits a car only while a space is free, lets a car
#              out only while one stands inside, and never holds more cars
#              than it has spaces -- also when two gates admit at once.
#
# No choice writes its cases out by hand. Each GENERATES them, with one of
# hwut's helpers for writing tests (hwut/support/test_writing/perl):
#
# space        'garage-space.hocon' states the tested space -- capacities,
#              cars arriving, cars leaving -- in hwut's HOCON, read by
#              'Hwut::Hocon'. A reviewer edits the space without reading
#              Perl. 'Hwut::SpaceIterator' walks every combination: 3 x 5 x
#              4 = 60 cases. Each is printed as one cell of a matrix, and
#              checked against the model: admitted = min(arriving,
#              capacity), out = min(leaving, admitted).
#
# random       'Hwut::DeterministicStream->new(4711)' draws 1000 cars arriving and
#              leaving at a garage of 5. The draw is the same on every
#              machine and in every language hwut supports -- the stream is
#              a linear congruential generator, not Perl's 'rand' -- so
#              the GOOD is exact, and a failing run can be replayed by its
#              seed.
#
# race-naive   two gates, one free space. A gate CHECKS whether a space is
#              free, and later ADMITS its car. 'Hwut::TriggerDispatcher'
#              runs the two gates as Hwut::Triggers on timelines drawn as
#              strings -- '1 1 ' fires at tick 0 and tick 2 -- so every
#              interleaving is played exactly, not hoped for with sleeps.
#              'Hwut::SpaceIterator' generates all six interleavings of two
#              two-step gates in four ticks. Where both gates check before
#              either admits, both admit: the garage is overbooked. The law
#              is 'overbooked > 0': the GOOD is the accepted violation
#              report.
#
# race-atomic  the same six interleavings, the gate checking and admitting
#              in ONE step under the counter's lock. 'overbooked == 0'.
#
# THE FRONT END is hwut's Hwut::Runner: the choice map below is the whole
# command line, '--hwut-info' included. The header says
# 'interactive = true': hwut starts the application ONCE and asks for the
# choices one after another in that one process -- an accelerator only: a
# choice's output equals what it prints when run alone.
#______________________________________________________________________________
use strict;
use warnings;
use FindBin;
use lib $FindBin::Bin;
use SupportPath;
use Hwut::SpaceIterator qw(space_points);
use Hwut::Hocon;
use Hwut::DeterministicRandom;
use Hwut::DeterministicTimeline;
use Hwut::Runner;
use Hwut::PyText;

my $HERE = $FindBin::Bin;


package Garage;
# The unit under test: a counter of the spaces a garage has.

sub new {
    # RETURN: Garage, empty, of 'capacity' spaces.
    my ($class, $capacity) = @_;
    return bless { capacity => $capacity, occupied => 0 }, $class;
}

sub free {
    # RETURN: integer, the number of spaces free now -- negative where the
    #         garage is overbooked.
    my ($self) = @_;
    return $self->{capacity} - $self->{occupied};
}

sub arrive {
    # RETURN: 1, a car was admitted, if a space was free;
    #         0, else (the car is refused).
    my ($self) = @_;
    return 0 if $self->free <= 0;
    $self->{occupied} += 1;
    return 1;
}

sub leave {
    # RETURN: 1, a car drove out, if one stood inside;
    #         0, else.
    my ($self) = @_;
    return 0 if $self->{occupied} == 0;
    $self->{occupied} -= 1;
    return 1;
}


package main;

# _____________________________________________________________________________
# space -- the tested space from HOCON, walked by Hwut::SpaceIterator
#
sub read_space {
    # RETURN: list of [name, [values]], the dimensions of the space in 'path',
    #         in the order written.
    # Every fault the HOCON reader found is printed with '!!' first.
    my ($path) = @_;
    open(my $fh, "<", $path) or die "garage.pl: $path: $!\n";
    my @text = map { s/\n$//r } <$fh>;
    close $fh;
    my @line = map { Hwut::Hocon::SourceLine->new($text[$_], $_ + 1, 0) } 0 .. $#text;
    my ($document, $fault_list) = Hwut::Hocon::parse(\@line, "garage-space.hocon");
    print "!! $_\n" for @$fault_list;
    my $space = $document->get("space")->node;
    return map { [$_->key, [map { $_->value } $_->node->item_list]] } $space->entry_list;
}

sub space {
    # RETURN: nothing. Prints every case of the space as a matrix cell.
    my @dimension = read_space("$HERE/garage-space.hocon");
    my @value     = map { $_->[1] } @dimension;
    print "space: ", join("  x  ", map { "$_->[0] " . Hwut::PyText::list_repr($_->[1]) } @dimension), "\n";
    print "cell: cars inside / cars refused at the gate ('!!' differs from the model)\n";
    my ($mismatch_n, %row) = (0);
    for my $point (space_points(\@value)) {
        my ($capacity, $arriving, $leaving) = @$point;
        my $garage   = Garage->new($capacity);
        my $refused  = grep { !$_ } map { $garage->arrive } 1 .. $arriving;
        $garage->leave for 1 .. $leaving;
        my $admitted = $arriving < $capacity ? $arriving : $capacity;
        my @expected = ($admitted - ($leaving < $admitted ? $leaving : $admitted), $arriving - $admitted);
        my $differ_f = $garage->{occupied} != $expected[0] || $refused != $expected[1];
        $mismatch_n += $differ_f ? 1 : 0;
        push @{$row{"$capacity,$arriving"}},
             sprintf("%d/%d%s", $garage->{occupied}, $refused, $differ_f ? "!!" : "  ");
    }
    for my $capacity (@{$value[0]}) {
        (my $head = sprintf("capacity %d   %s", $capacity,
                            join("  ", map { sprintf("leave %-3d", $_) } @{$value[2]}))) =~ s/\s+$//;
        print "$head\n";
        for my $arriving (@{$value[1]}) {
            (my $line = sprintf("  arrive %d   %s", $arriving,
                                join("  ", map { sprintf("%-9s", $_) } @{$row{"$capacity,$arriving"}}))) =~ s/\s+$//;
            print "$line\n";
        }
    }
    printf "cases %d, differing from the model ((mismatches: %d))\n",
           scalar(keys %row) * @{$value[2]}, $mismatch_n;
}

# _____________________________________________________________________________
# random -- a deterministic stream of arrivals and departures
#
sub random_stream {
    # RETURN: nothing. Prints the summary of 1000 drawn cars, model-checked.
    my $stream = Hwut::DeterministicStream->new(4711);
    my $garage = Garage->new(5);
    my $model  = 0;
    my %count  = (arrive => 0, refused => 0, leave => 0, empty => 0);
    my @histogram = (0) x 6;
    my ($mismatch_n, $strip) = (0, "");
    for (1 .. 1000) {
        if ($stream->coin(0.55)) {
            $count{arrive} += 1;
            $count{refused} += 1 unless $garage->arrive;
            $model = $model + 1 < 5 ? $model + 1 : 5;
            $strip .= "+";
        }
        else {
            $count{leave} += 1;
            $count{empty} += 1 unless $garage->leave;
            $model = $model - 1 > 0 ? $model - 1 : 0;
            $strip .= "-";
        }
        $mismatch_n += $garage->{occupied} != $model ? 1 : 0;
        $histogram[$garage->{occupied}] += 1;
    }
    print "seed 4711, garage of 5, 1000 cars drawn: '+' arrives, '-' leaves\n";
    print "first 60: ", substr($strip, 0, 60), "\n";
    printf "arrivals %d, refused %d; departures %d, from an empty garage %d\n",
           @count{qw(arrive refused leave empty)};
    print "cars inside after each event:\n";
    printf "    %d  %4d  %s\n", $_, $histogram[$_], "#" x int($histogram[$_] / 10) for 0 .. $#histogram;
    printf "steps differing from the model ((mismatches: %d))\n", $mismatch_n;
}

# _____________________________________________________________________________
# race -- two gates on drawn timelines
#
package Gate;
use parent -norequire, "Hwut::Trigger";
# A gate on a timeline: its first tick checks, its second admits.

sub new {
    # RETURN: Gate named 'name' on 'timeline' at 'garage'; it tells what it
    #         does to the code ref 'log'.
    my ($class, $name, $timeline, $garage, $atomic_f, $log) = @_;
    my $self = Hwut::Trigger::new($class, $timeline, $name);
    @$self{qw(garage atomic_f log step saw_free_f)} = ($garage, $atomic_f, $log, 0, 0);
    return $self;
}

sub fire {
    # RETURN: nothing. Performs the gate's next step at 'pseudo_time'.
    my ($self, $pseudo_time) = @_;
    my ($name, $garage) = ($self->name, $self->{garage});
    if ($self->{step} == 0 && $self->{atomic_f}) {
        $self->{saw_free_f} = $garage->arrive;
        $self->{log}->($self->{saw_free_f} ? "$name checks+admits" : "$name refuses");
    }
    elsif ($self->{step} == 0) {
        $self->{saw_free_f} = $garage->free > 0;
        $self->{log}->(sprintf("%s sees %d free", $name, $garage->free));
    }
    elsif ($self->{atomic_f}) {
        $self->{log}->($self->{saw_free_f} ? "$name opens" : "$name stays shut");
    }
    elsif ($self->{saw_free_f}) {
        $garage->{occupied} += 1;                        # the naive admit
        $self->{log}->("$name admits");
    }
    else {
        $self->{log}->("$name refuses");
    }
    $self->{step} += 1;
}


package main;

sub interleaving_list {
    # RETURN: list of [string, string], every pair of timelines in four ticks
    #         in which each of two gates fires twice, never at the same tick:
    #         gate A's and gate B's.
    my $line = sub { my ($x, $y) = @_; join("", map { $_ == $x || $_ == $y ? "1" : " " } 0 .. 3) };
    my @result;
    for my $point (space_points([([0 .. 3]) x 4])) {
        my ($a1, $a2, $b1, $b2) = @$point;
        my %distinct = map { $_ => 1 } @$point;
        push @result, [$line->($a1, $a2), $line->($b1, $b2)]
            if $a1 < $a2 && $b1 < $b2 && keys %distinct == 4;
    }
    return @result;
}

sub race {
    # RETURN: nothing. Plays every interleaving of two gates at one space.
    my ($atomic_f) = @_;
    print "one free space, two gates, one car at each; timelines: a digit fires\n";
    print "    gate A  gate B  what happens                                    inside\n";
    my $overbooked_n = 0;
    my @interleaving = interleaving_list();
    for my $pair (@interleaving) {
        my ($timeline_a, $timeline_b) = @$pair;
        my ($garage, @event) = (Garage->new(1));
        my $log = sub { push @event, $_[0] };
        Hwut::TriggerDispatcher->new([Gate->new("A", $timeline_a, $garage, $atomic_f, $log),
                                      Gate->new("B", $timeline_b, $garage, $atomic_f, $log)])->run;
        my $over_f = $garage->{occupied} > $garage->{capacity};
        $overbooked_n += $over_f ? 1 : 0;
        (my $text = sprintf("    \"%s\"  \"%s\"  %-46s  %d %s", $timeline_a, $timeline_b,
                            join(", ", @event), $garage->{occupied}, $over_f ? "!!" : "  ")) =~ s/\s+$//;
        print "$text\n";
    }
    printf "interleavings overbooking the garage ((overbooked: %d)) of %d\n",
           $overbooked_n, scalar @interleaving;
}

sub race_naive {
    # RETURN: nothing. The gates check, then admit, in two steps.
    race(0);
}

sub race_atomic {
    # RETURN: nothing. The gates check and admit in one step.
    race(1);
}


Hwut::Runner->new(argv  => \@ARGV,
                  title => "Demo: a garage's space counter -- a space, a stream and races, generated;",
                  choice_map => { "space"       => \&space,
                                  "random"      => \&random_stream,
                                  "race-naive"  => \&race_naive,
                                  "race-atomic" => \&race_atomic })->run;
