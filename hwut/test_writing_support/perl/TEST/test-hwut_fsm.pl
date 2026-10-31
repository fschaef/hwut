#! /usr/bin/env perl
#
# @hwut {
#     title      = "hwut_fsm: a state machine as the test's model of the system"
#     choices {
#         syntax    { features = ["perl-fsm"] }
#         refused   { features = ["perl-fsm"] }
#         dfa       { features = ["perl-fsm"] }
#         nfa       { features = ["perl-fsm"] }
#         forbidden { features = ["perl-fsm"] }
#         model     { features = ["perl-fsm"] }
#         report    { features = ["perl-fsm"] }
#         masks     { features = ["perl-fsm"] }
#     }
# }
#
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# PURPOSE: The Perl port of 'python/TEST/test-hwut_fsm.py', choice for choice,
#          held against its GOOD files by '.link'. What Python prints of its
#          own values -- True, None, a tuple -- is printed so here
#          ('Hwut::PyText'), since the GOOD file is one.
#______________________________________________________________________________
use strict;
use warnings;
use FindBin;
use lib "$FindBin::Bin/..";
use Hwut::Runner;
use Hwut::Fsm;
use Hwut::PyText qw(bool_text tuple_repr);

my $PROTOCOL = <<'END';

    initial:   idle
    forbidden: crashed
    final:     idle
    idle    ---( request )---> waiting ---( grant )---> busy
    busy    ---( release )---> idle
    :       ---( fault )--->   crashed       # the state that began line 6
    waiting ---( cancel )---> idle
END

sub banner { my ($label) = @_; print "\n--- $label ---\n" }

sub path_text {
    # RETURN: string, a path as Python prints the tuple 'path_to' returns --
    #         'None' where there is none.
    my ($path) = @_;
    return defined $path ? tuple_repr($path, 1) : "None";
}

sub error_line {
    # RETURN: string, 'FsmError: <message>' for a Hwut::FsmError; dies on with
    #         anything else.
    my ($error) = @_;
    die $error unless ref $error && $error->isa("Hwut::FsmError");
    return "FsmError: " . $error->message;
}

sub run_syntax {
    banner("the protocol, written back");
    print Hwut::Fsm->from_string($PROTOCOL)->to_string, "\n";
    banner("the author's form: 'state', a chain, ':', blanks around '-->'");
    print Hwut::Fsm->from_string(<<'END')->to_string, "\n";

        state A ---( event )---> state B
        :                ---(event2)---> state C ---(event) --> state D
        state E          # no transition yet
END
}

sub run_refused {
    for my $text ("A ---( x )---> B\n: ---( x )---> C",
                  "A ---(  )---> B",
                  ": ---( x )---> B",
                  "A B ---( x )---> C",
                  "initial: A, B\nA ---( x )---> B",
                  "forbidden: Q\nA ---( x )---> B",
                  "# nothing but a comment") {
        (my $label = $text) =~ s/\n/ | /g;
        banner($label);
        if (eval { Hwut::Fsm->from_string($text); 1 }) { print "accepted\n" }
        else                                          { print error_line($@), "\n" }
    }
}

sub run_dfa {
    my $m = Hwut::Fsm->from_string($PROTOCOL);
    my @event = qw(request release grant release jump request);
    for my $number (1 .. @event) {
        my $event = $event[$number - 1];
        my $moved = $m->fire($event, $number);
        printf "    %-8s -> %-5s now %-8s allowed: %s\n",
               $event, bool_text($moved), $m->state, join(", ", $m->allowed);
    }
    banner("questions where it stands");
    print "can('grant')   ", bool_text($m->can("grant")), "\n";
    print "can('release') ", bool_text($m->can("release")), "\n";
    print "in_state('waiting') ", bool_text($m->in_state("waiting")), "\n";
    print "trace: ", join(" ", map { "$_->[0]:$_->[2]>$_->[3]" } $m->trace), "\n";
}

sub run_nfa {
    my $m = Hwut::Fsm->from_string(<<'END', DFA => 0);

        A ---( x )---> B ---( y )---> D
        : ---( x )---> C ---( y )---> E
        C ---( z )---> F
END
    for my $event (qw(x z y)) {
        $m->fire($event, "t=$event");
        print "    after $event: ", join(", ", $m->current), "\n";
    }
    banner("'state' asked of a set");
    $m->reset; $m->fire("x");
    if (eval { my $s = $m->state; print "$s\n"; 1 }) {}
    else { print error_line($@), "\n" }
}

sub run_forbidden {
    my $m = Hwut::Fsm->from_string($PROTOCOL);
    my @event = qw(request grant fault);
    for my $number (1 .. @event) {
        printf "    %-8s -> %s\n", $event[$number - 1],
               bool_text($m->fire($event[$number - 1], $number));
    }
    print "now in ", $m->state, " -- breaches: ", $m->breach_n, "\n";
}

sub run_model {
    my $m = Hwut::Fsm->from_string($PROTOCOL . "\n    state limbo\n    limbo ---( kick )---> idle\n");
    print "check: ", $m->check, "\n";
    banner("path_to");
    printf "    %-8s %s\n", $_, path_text($m->path_to($_)) for qw(busy crashed limbo idle);
    $m->fire("request");
    print "    busy from now: ", path_text($m->path_to("busy", start => "now")), "\n";
    print "    state_reachable('idle', start='now'): ",
          bool_text($m->state_reachable("idle", start => "now")), "\n";
}

sub run_report {
    my $m = Hwut::Fsm->from_string($PROTOCOL, name => "protocol");
    $m->fire($_) for qw(request grant release request grant);
    print "report returns ", $m->report, "\n";
}

sub run_masks {
    my $m = Hwut::Fsm->from_string($PROTOCOL);
    banner("'grant' disallowed in every state, since line 2");
    $m->disallow("grant", undef, 2);
    $m->fire("request", 3);
    print "    allowed now: ", join(", ", $m->allowed), " -- can('grant'): ",
          bool_text($m->can("grant")), "\n";
    $m->fire("grant", 4);
    print "    path_to('busy'):               ", path_text($m->path_to("busy")), "\n";
    print "    path_to('busy', masked=False): ", path_text($m->path_to("busy", masked => 0)), "\n";
    print "    check(): ", $m->check, "\n";
    print "    check(masked=False): ", $m->check(masked => 0), "\n";

    banner("allowed again; 'busy' forbidden while standing in it");
    $m->allow("grant", undef, 5);
    $m->fire("grant", 6);
    $m->forbid("busy", 7);
    $m->fire("release", 8);
    $m->fire("request", 9);
    $m->fire("grant", 10);

    banner("permitted: 'busy', and the model's own 'crashed'");
    $m->permit("busy", 11);
    $m->permit("crashed", 12);
    my $fault = $m->fire("fault", 13);
    print "    fault -> ", bool_text($fault), " -- now in ", $m->state, "\n";

    banner("a phase: 'release' disallowed in 'busy' for a block");
    $m->reset;
    $m->fire("request"); $m->fire("grant");
    $m->disallowed("release", "busy", "phase", sub { $m->fire("release", 20) });
    $m->fire("release", 21);
    $m->disallow("cancel", undef, 22);
    $m->report;

    banner("refused: a word the model never names");
    for my $call (sub { $m->disallow("jump") }, sub { $m->forbid("limbo") },
                  sub { $m->allow("grant", "nowhere") }) {
        eval { $call->(); 1 } or print error_line($@), "\n";
    }
}

Hwut::Runner->new(
    argv       => \@ARGV,
    title      => "hwut_fsm: a state machine as the test's model of the system",
    choice_map => {
        syntax    => \&run_syntax,
        refused   => \&run_refused,
        dfa       => \&run_dfa,
        nfa       => \&run_nfa,
        forbidden => \&run_forbidden,
        model     => \&run_model,
        report    => \&run_report,
        masks     => \&run_masks,
    },
)->run;
