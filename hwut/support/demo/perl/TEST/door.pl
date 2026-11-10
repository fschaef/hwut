#! /usr/bin/env perl
#
# @hwut {
#     title   = "Demo: a door's state machine, watched by a pype"
#     pype    = "door.pype"
#     choices {
#         kept   { features = ["demo-perl", "demo-perl+cover-fsm-law-kept"] }
#         broken { features = ["demo-perl", "demo-perl+cover-fsm-law-broken"] }
#     }
# }
#
#______________________________________________________________________________
# A DOOR CONTROLLER THAT REPORTS WHAT IT DOES -- and a model that says what it
# may do.
#
# The application prints its log as it happens: noise, and a line 'door:
# <event>' for each thing the door does. It prints no '<hwut-end>': the
# header names 'door.pype', which stands between it and the comparison and
# closes the stream at '<eof>'.
#
# 'door.pype' parses the log and fires every event into a state machine
# ('hwut_fsm', support/test_writing/python -- a pype is Python):
#
#     closed ---( open )---> open ---( close )---> closed
#     closed ---( lock )---> locked ---( unlock )---> closed
#     open   ---( slam )---> jammed          # forbidden
#
# kept     the door does what the model allows; the report shows which
#          transitions were taken and which not, and 'ended in closed'.
# broken   the controller locks an open door, slams it into a jam and
#          tries to unlock it: each surprise is ONE 'BREACH' line in the
#          output, the jam included, and the end outside the final states
#          is one more. The GOOD file
#          holds them and a run that stops breaching -- or breaches
#          differently -- shows up as a difference.
#
# Both choices pass on every run: what they print does not depend on time.
#______________________________________________________________________________
use strict;
use warnings;

my %STORY = (kept   => [qw(open close lock unlock open close)],
             broken => [qw(open lock slam unlock)]);


sub main {
    # RETURN: integer, 0 -- the log of the door for 'choice', printed.
    my ($choice) = @_;
    print "controller 2.1 up\n";
    my $number = 0;
    for my $event (@{$STORY{$choice}}) {
        $number += 1;
        print "tick $number: sensors read\n";
        print "door: $event\n";
    }
    print "controller down\n";
    return 0;
}


if (@ARGV != 1 || !$STORY{$ARGV[0]}) {
    print "error: a choice is required: ", join(", ", sort keys %STORY), "\n";
    exit 1;
}
exit main($ARGV[0]);
