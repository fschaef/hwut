#! /usr/bin/env perl
#
# @hwut {
#     title      = "TriggerDispatcher: schedule, priority, and the end of time"
#     choices {
#         abstract    { features = ["perl-timeline"] }
#         cancel      { features = ["perl-timeline"] }
#         edges       { features = ["perl-timeline"] }
#         priority    { features = ["perl-timeline"] }
#         schedule    { features = ["perl-timeline"] }
#         stable      { features = ["perl-timeline"] }
#         stop        { features = ["perl-timeline"] }
#         termination { features = ["perl-timeline"] }
#         yielding    { features = ["perl-timeline"] }
#     }
#     interactive = true
# }
#
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# PURPOSE: The Perl port of 'python/TEST/test-deterministic-timeline.py',
#          choice for choice, held against its GOOD files by '.link'. Where
#          Python awaits, Perl steps a task: 'yielding' and 'cancel' show that
#          the step-wise run interleaves as 'asyncio' does.
#______________________________________________________________________________
use strict;
use warnings;
use FindBin;
use lib "$FindBin::Bin/..";
use Hwut::Runner;
use Hwut::DeterministicTimeline;

sub banner { my ($label) = @_; print "\n--- $label ---\n" }


package SpeakingTrigger {
    use parent -norequire, 'Hwut::Trigger';
    sub new {
        # RETURN: SpeakingTrigger, said at its setup.
        my ($class, $name, $timeline, $silent_termination_f) = @_;
        my $self = Hwut::Trigger::new($class, $timeline, $name);
        $self->{silent_termination_f} = $silent_termination_f;
        printf "SETUP: %-7s |%s|\n", $name, $timeline;
        return $self;
    }
    sub fire {
        my ($self, $t) = @_;
        print "  [t:$t] $self->{name} fires\n";
    }
    sub on_termination {
        my ($self, $end_tick) = @_;
        return if $self->{silent_termination_f};
        print "  [end:$end_tick] $self->{name} notified\n";
    }
}

package MuteTrigger {
    use parent -norequire, 'Hwut::Trigger';
    sub new {
        my ($class, $name, $timeline) = @_;
        my $self = Hwut::Trigger::new($class, $timeline, $name);
        printf "SETUP: %-7s |%s|  (no on_termination override)\n", $name, $timeline;
        return $self;
    }
    sub fire {
        my ($self, $t) = @_;
        print "  [t:$t] $self->{name} fires\n";
    }
}

package BareTrigger {
    use parent -norequire, 'Hwut::Trigger';
}

package main;

sub speaking { SpeakingTrigger->new(@_) }
sub dispatch { Hwut::TriggerDispatcher->new([@_])->run }

sub run_schedule {
    banner("staggered: A at 0, B at 2, C at 4");
    dispatch(speaking("A", "1    "), speaking("B", "  1  "), speaking("C", "    1"));

    banner("a SHORT timeline stops contributing; the long one goes on");
    dispatch(speaking("SHORT", "11"), speaking("LONG", "111111"));

    banner("the SCHEDULE as built -- '[tick] (priority)name'");
    print Hwut::TriggerDispatcher->new([speaking("A", "12"), speaking("B", "21")])->as_text, "\n";
}

sub run_priority {
    banner("digits swap between ticks: B leads at 0, A leads at 1");
    dispatch(speaking("A", "21"), speaking("B", "12"));

    banner("0 is the strongest digit, 9 the weakest");
    dispatch(speaking("WEAK", "9"), speaking("STRONG", "0"));
}

sub run_stable {
    banner("three triggers, all digit 1 at tick 0");
    dispatch(speaking("first", "1"), speaking("second", "1"), speaking("third", "1"));

    banner("registered BACKWARDS -- the order follows registration, not the name");
    dispatch(speaking("third", "1"), speaking("second", "1"), speaking("first", "1"));
}

sub run_termination {
    banner("end_tick is the LENGTH -- 5 characters, last firing at tick 0");
    dispatch(speaking("EARLY", "1    "));

    banner("a trigger that NEVER fires is notified all the same");
    dispatch(speaking("FIRES", "1  "), speaking("SILENT", "   "));

    banner("the LONGEST timeline sets end_tick for everybody");
    dispatch(speaking("SHORT", "1"), speaking("LONG", "1      "));

    banner("a trigger that does not override is simply silent at the end");
    dispatch(speaking("SPEAKS", "1 "), MuteTrigger->new("MUTE", "1 "));
}

package ProducingTrigger {
    use parent -norequire, 'Hwut::Trigger';
    sub new {
        my ($class, $name, $timeline) = @_;
        my $self = Hwut::Trigger::new($class, $timeline, $name);
        @$self{qw(item finished)} = (undef, 0);
        printf "SETUP: %-7s |%s|\n", $name, $timeline;
        return $self;
    }
    sub fire {
        my ($self, $t) = @_;
        $self->{item} = "item\@$t";
        print "  [t:$t] $self->{name} prepared $self->{item}\n";
    }
    sub on_termination {
        my ($self, $end_tick) = @_;
        $self->{finished} = 1;
        print "  [end:$end_tick] $self->{name} announced end-of-stream\n";
    }
}

package main;

sub run_yielding {
    banner("producer fires at every tick; consumer waits between them");
    my $producer = ProducingTrigger->new("PROD", "111");
    my $taken    = 0;
    #  THE CONSUMER, one step per yield: takes the item where one stands,
    #  ends where the end was announced, waits (yields) else.
    my $consumer = Hwut::Task->new(sub {
        while (1) {
            if (!defined $producer->{item}) {
                if ($producer->{finished}) {
                    print "  consumer saw end-of-stream after $taken item(s)\n";
                    return 0;
                }
                return 1;
            }
            $taken += 1;
            print "        consumer took $producer->{item}\n";
            $producer->{item} = undef;
        }
    });
    Hwut::Task::gather(Hwut::TriggerDispatcher->new([$producer])->task, $consumer);
    print "\n";
    print "Each item was taken BEFORE the next tick prepared one: the run yields.\n";
}

package StoppingTrigger {
    use parent -norequire, 'SpeakingTrigger';
    sub fire {
        my ($self, $t) = @_;
        $self->SUPER::fire($t);
        print "  ... asks the dispatcher to stop\n";
        $self->{dispatcher}->stop;
    }
}

package main;

sub run_stop {
    banner("stop() after the first tick -- ticks 1.. are not walked, the announcement still comes");
    my $stopper    = StoppingTrigger->new("STOPPER", "1111");
    my $bystander  = speaking("OTHER", "1111");
    my $dispatcher = Hwut::TriggerDispatcher->new([$stopper, $bystander]);
    $stopper->{dispatcher} = $dispatcher;
    $dispatcher->run;
    print "\n";
    print "end_tick is still the timeline's length, not the tick the run stopped at.\n";
}

sub run_cancel {
    banner("cancel() the task carrying run() -- no announcement follows");
    my $dispatcher = Hwut::TriggerDispatcher->new([speaking("A", "1111111111")]);
    my $task       = $dispatcher->task;
    $task->step;                                  # one tick passes
    $task->cancel;
    eval { $task->await; 1 } or do {
        print "  run() was cancelled\n" if $@ =~ /^CancelledError/;
    };
    print "\n";
    print "No '[end:..]' line above: the triggers were abandoned, not ended.\n";
}

sub run_edges {
    banner("an EMPTY timeline -- end_tick 0");
    dispatch(speaking("EMPTY", ""));

    banner("a timeline of BLANKS -- no digit, so nothing fires");
    dispatch(speaking("BLANK", "    "));

    banner("NO TRIGGERS at all -- nothing to announce, and no failure");
    dispatch();
    print "  (dispatcher ran; nothing was scheduled)\n";

    banner("a timeline of blanks beside one that fires");
    dispatch(speaking("BLANK", "   "), speaking("FIRES", " 1 "));
}

sub run_abstract {
    banner("the BASE 'fire' is abstract -- it refuses");
    eval { dispatch(BareTrigger->new("1", "BARE")); 1 } or do {
        print "  NotImplementedError -- as owed: a trigger must say what it does\n"
            if $@ =~ /^NotImplementedError/;
    };

    banner("the BASE 'on_termination' is optional -- it is silent");
    my $bare = BareTrigger->new("", "BARE");
    $bare->on_termination(0);
    print "  returned quietly; nothing raised, nothing printed\n";

    banner("a NAME given is the name kept");
    print "  name: ", Hwut::Trigger->new("1", "GIVEN")->name, "\n";
}

Hwut::Runner->new(
    argv       => \@ARGV,
    title      => "TriggerDispatcher: schedule, priority, and the end of time",
    choice_map => {
        schedule    => \&run_schedule,
        priority    => \&run_priority,
        stable      => \&run_stable,
        termination => \&run_termination,
        yielding    => \&run_yielding,
        stop        => \&run_stop,
        cancel      => \&run_cancel,
        edges       => \&run_edges,
        abstract    => \&run_abstract,
    },
)->run;
