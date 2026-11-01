# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# PURPOSE: A DETERMINISTIC EVENT DISPATCHER -- the port of
#          'python/deterministic_timeline.py'. Triggers fire at the ticks their
#          timeline strings mark with a digit; within one tick the LOWER digit
#          fires first, equal digits in registration order:
#
#              Trigger A: "1  12 1"
#              Trigger B: " 1  1 2"
#
#          When the last tick has passed, every trigger is told
#          'on_termination(end_tick)', 'end_tick' being the LONGEST timeline's
#          length. 'stop' leaves early and still announces; a CANCELLED task
#          announces nothing.
#
# USAGE:
#
#     package MyTrigger; use parent -norequire, 'Hwut::Trigger';
#     sub fire { my ($self, $t) = @_; print "[$t] $self->{name} fired\n" }
#
#     Hwut::TriggerDispatcher->new([MyTrigger->new("1 1 3", "SUB")])->run;
#
# THE YIELD WITHOUT COROUTINES. Python's run awaits each firing and then
# 'asyncio.sleep(0)', so a consumer waiting on the trigger runs between ticks.
# Perl has no coroutines in its core, so here a TASK is a step closure: one
# 'step' runs up to the next yield and answers whether more is to come.
# 'Hwut::Task::gather' steps the tasks in turn, in the order given -- the
# order 'asyncio.gather' gives them -- until each is done:
#
#     my $run      = $dispatcher->task;              # the run, as a task
#     my $consumer = Hwut::Task->new(sub { ...; return 1 });   # 1: yield; 0: done
#     Hwut::Task::gather($run, $consumer);
#
# A trigger's 'fire' is a plain method: what it does, it does within its tick.
#______________________________________________________________________________
package Hwut::DeterministicTimeline;
use strict;
use warnings;
1;


package Hwut::Task;
use strict;
use warnings;

sub new {
    # RETURN: Hwut::Task over 'step', a code ref that runs up to its next
    #         yield and returns true where more is to come, false where done.
    my ($class, $step) = @_;
    return bless { step => $step, done_f => 0, cancelled_f => 0 }, $class;
}

sub step {
    # RETURN: 1, the task yielded and goes on; 0, it is done (or cancelled).
    my ($self) = @_;
    return 0 if $self->{done_f};
    $self->{done_f} = 1 unless $self->{step}->();
    return $self->{done_f} ? 0 : 1;
}

sub cancel {
    # RETURN: nothing. The task is abandoned: it is never stepped again, and
    #         whatever it would have done at its end is not done.
    my ($self) = @_;
    @$self{qw(done_f cancelled_f)} = (1, 1);
}

sub await {
    # RETURN: nothing, once the task is done. Dies 'CancelledError' where the
    #         task was cancelled -- as awaiting a cancelled task raises in
    #         Python.
    my ($self) = @_;
    1 while $self->step;
    die "CancelledError\n" if $self->{cancelled_f};
}

sub gather {
    # RETURN: nothing, once every task is done. The tasks are stepped in turn,
    #         in the order given, each up to its next yield.
    my (@task) = @_;
    while (my @live = grep { !$_->{done_f} } @task) {
        $_->step for @live;
    }
}


package Hwut::Trigger;
use strict;
use warnings;

sub new {
    # RETURN: Hwut::Trigger with 'timeline' and 'name' -- a name chosen by the
    #         machine where none is given.
    my ($class, $timeline, $name) = @_;
    my $self = bless { timeline => $timeline // "" }, $class;
    $self->{name} = (defined $name && $name ne "") ? $name
                  : sprintf("trigger-%d", 0 + $self);
    return $self;
}

sub name     { $_[0]{name} }
sub timeline { $_[0]{timeline} }

sub fire {
    # RETURN: never. ABSTRACT: a trigger that does nothing when its tick comes
    #         has no reason to stand in the timeline -- dies
    #         'NotImplementedError'.
    my ($self) = @_;
    die "NotImplementedError: '" . ref($self) . "' does not say what it does at its tick\n";
}

sub on_termination {
    # RETURN: nothing. Optional: a trigger with nothing to wind down says
    #         nothing.
    return;
}


package Hwut::TriggerDispatcher;
use strict;
use warnings;

sub new {
    # RETURN: Hwut::TriggerDispatcher over the array ref 'triggers', its
    #         schedule built: one entry per tick, the (priority, trigger)
    #         pairs due there, lower digit first, registration order between
    #         equal digits.
    my ($class, $triggers) = @_;
    my @trigger = @{$triggers // []};
    my $end_tick = 0;
    for (@trigger) { $end_tick = length $_->{timeline} if length $_->{timeline} > $end_tick }
    my @schedule = map { [] } 1 .. $end_tick;
    for my $trigger (@trigger) {
        my @char = split //, $trigger->{timeline};
        for my $t (0 .. $#char) {
            push @{$schedule[$t]}, [$char[$t], $trigger] if $char[$t] =~ /^[0-9]$/;
        }
    }
    #  Perl's sort is stable since 5.8 ('use sort' aside): equal digits keep
    #  their registration order, as Python's 'list.sort' does.
    @$_ = sort { $a->[0] <=> $b->[0] } @$_ for @schedule;
    return bless { running_f => 1, triggers => \@trigger,
                   schedule => \@schedule, end_tick => $end_tick }, $class;
}

sub stop {
    # RETURN: nothing. The run leaves the timeline at the next firing; it still
    #         announces termination.
    my ($self) = @_;
    $self->{running_f} = 0;
}

sub task {
    # RETURN: Hwut::Task, the run: each step fires the next trigger due and
    #         yields; the last step announces 'on_termination(end_tick)' to
    #         every trigger -- after the end of the timeline, or after 'stop'.
    my ($self) = @_;
    my ($tick, $i) = (0, 0);
    return Hwut::Task->new(sub {
        while ($self->{running_f} && $tick < @{$self->{schedule}}) {
            my $due = $self->{schedule}[$tick];
            if ($i < @$due) {
                $due->[$i++][1]->fire($tick);
                return 1;                                # the yield
            }
            ($tick, $i) = ($tick + 1, 0);
        }
        $_->on_termination($self->{end_tick}) for @{$self->{triggers}};
        return 0;
    });
}

sub run {
    # RETURN: nothing, once the timeline has passed and the triggers are told.
    my ($self) = @_;
    $self->task->await;
}

sub as_text {
    # RETURN: string, the schedule as built -- 'TriggerDispatcher', then one
    #         line per firing, '[tick] (priority)name', in the order of the run.
    my ($self) = @_;
    my @line = ("TriggerDispatcher");
    for my $t (0 .. $#{$self->{schedule}}) {
        push @line, sprintf("[%d] (%d)%s", $t, $_->[0], $_->[1]{name})
            for @{$self->{schedule}[$t]};
    }
    return join("\n", @line);
}

1;
