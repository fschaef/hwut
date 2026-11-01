# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# PURPOSE: FRONT END OF A HWUT TEST APPLICATION IN PERL -- the port of
#          'python/hwut_runner.py', the same modes, the same words:
#
#     app --hwut-info      the info block; exit 0.
#     app <choice>         one choice; test output on stdout and stderr,
#                          '<hwut-end>' after it. '-' runs a choice-less test.
#     app --interactive    choices started over stdin, output into two named
#                          sink files per choice, 'done' on the original stdout.
#     app                  the choice-less test; where the application has
#                          choices, refused, naming them.
#
# USAGE:
#
#     use Hwut::Runner;
#     Hwut::Runner->new(
#         argv       => \@ARGV,
#         title      => "What this application tests",
#         choice_map => { plain => \&run_plain, tricky => \&run_tricky },
#     )->run;
#
# 'choice_map' maps a choice name to a code ref; the key '-' alone stands for
# a choice-less test. 'happy' (string or array ref), 'same_f' and 'parallel'
# ('process': one forked child per choice) are as in Python.
#
# THE INTERACTIVE PROTOCOL is Python's, line for line:
#     DOWN  run <choice> <sink-out> <sink-err> | info | quit | q | exit
#     UP    done <choice> <status> | fail <choice> <reason> | info: <line> | bye
#______________________________________________________________________________
package Hwut::Runner;
use strict;
use warnings;
use File::Temp qw(tempfile);
use POSIX      qw(_exit dup dup2 WIFEXITED WEXITSTATUS WIFSIGNALED WTERMSIG);
use IO::Handle;

my $NONE = "-";            # the choice-less test's key, as the command line spells it

#  'exit' IN A CHOICE ENDS THE CHOICE in interactive mode, as SystemExit does
#  in Python -- not the session. Installed when this module loads, which is
#  before the test application's own code is compiled, so every 'exit' it
#  writes comes here; outside a choice run into sinks it is the plain exit.
our $IN_SINK_F = 0;
BEGIN {
    *CORE::GLOBAL::exit = sub {
        die bless({ code => $_[0] // 0 }, "Hwut::Runner::Exit") if $IN_SINK_F;
        CORE::exit($_[0] // 0);
    };
}


sub new {
    # RETURN: Hwut::Runner, ready for '->run'.
    my ($class, %arg) = @_;
    my $choice_map = $arg{choice_map} or die "Hwut::Runner: no 'choice_map'\n";
    die "Hwut::Runner: '-' stands for the choice-less test and stands alone\n"
        if exists $choice_map->{$NONE} && keys %$choice_map > 1;
    my $parallel = $arg{parallel};
    die "Hwut::Runner: 'parallel' is undef or 'process'\n"
        if defined $parallel && $parallel ne "process";
    my $argv  = $arg{argv} // \@ARGV;
    my $happy = $arg{happy};
    my $self  = bless {
        title       => $arg{title} // "",
        argv        => $argv,
        choice      => $argv->[0],
        choice_map  => $choice_map,
        parallel    => $parallel,
        same_f      => $arg{same_f} ? 1 : 0,
        happy       => !defined $happy ? [] : ref $happy ? [@$happy] : [$happy],
        sorted      => exists $choice_map->{$NONE} ? [$NONE] : [sort keys %$choice_map],
        pending     => {},
    }, $class;
    return $self;
}


sub run {
    # RETURN: nothing. Dispatches on the first command line argument.
    my ($self) = @_;
    my $word = $self->{choice};
    my %info = map { $_ => 1 } ("-h", "--hi", "--hwut-info", "--sos", "--wtf");
    if    (defined $word && $info{$word})          { $self->mode_hwut_info }
    elsif (defined $word && $word eq "--interactive") { $self->mode_interactive }
    elsif (!defined $word) {
        exists $self->{choice_map}{$NONE} ? $self->mode_run_test($NONE)
                                          : $self->mode_choice_missing;
    }
    elsif (exists $self->{choice_map}{$word})      { $self->mode_run_test($word) }
    else                                           { $self->mode_choice_does_not_exist($word) }
}


sub mode_choice_missing {
    # RETURN: never; exits 1. The application has choices and none is named.
    my ($self) = @_;
    print "error: a choice is required: ", join(", ", @{$self->{sorted}}),
          " -- name one, or let 'hwut.play' ask.\n";
    exit 1;
}


sub mode_choice_does_not_exist {
    # RETURN: never; exits 1. Names the unavailable choice, the available
    #         ones and the closest by Levenshtein distance.
    my ($self, $word) = @_;
    if (exists $self->{choice_map}{$NONE}) {
        print "error: '$word': this application has no choices -- call it without one.\n";
        exit 1;
    }
    print "error: choice '$word' not available.\n";
    print "error: available: ", join(", ", @{$self->{sorted}}), ".\n";
    my $best = levenshtein_best_match($word, $self->{sorted});
    print "error: did you mean '$best'?\n" if defined $best;
    exit 1;
}


sub mode_run_test {
    # RETURN: nothing. Normal mode: the choice runs, then '<hwut-end>' (R-70).
    my ($self, $choice) = @_;
    $| = 1;
    $self->{choice_map}{$choice}->();
    print "<hwut-end>\n";
}


sub mode_hwut_info {
    # RETURN: never; exits 0. The info block.
    my ($self) = @_;
    print "$_\n" for $self->info_block_lines;
    exit 0;
}


sub info_block_lines {
    # RETURN: list of strings, the lines of the info block: title, CHOICES,
    #         HAPPY, SAME, INTERACTIVE -- each ending in ';'.
    my ($self) = @_;
    my $title = $self->{title};
    my @line  = ($title =~ /;$/ ? $title : "$title;");
    push @line, "CHOICES: " . join(", ", @{$self->{sorted}}) . ";"
        unless exists $self->{choice_map}{$NONE};
    push @line, "HAPPY: $_;" for @{$self->{happy}};
    push @line, "SAME;" if $self->{same_f};
    push @line, "INTERACTIVE;";
    return @line;
}


sub mode_interactive {
    # RETURN: nothing; returns when the session ends ('quit' or end of input).
    #         The original stdout is the UP channel; fd 1 and fd 2 point at a
    #         session stray sink, so output outside a choice never reaches the
    #         protocol.
    my ($self) = @_;
    STDOUT->flush; STDERR->flush;
    open(my $control, ">&", \*STDOUT) or die "Hwut::Runner: dup stdout: $!\n";
    $control->autoflush(1);
    $self->{control} = $control;
    my ($stray_fh, $stray_path) = tempfile("hwut_stray_XXXXXX", SUFFIX => ".txt", TMPDIR => 1);
    $self->{stray_path} = $stray_path;
    open(STDOUT, ">&", $stray_fh) or die; open(STDERR, ">&", $stray_fh) or die;
    close $stray_fh;
    while (defined(my $line = $self->_readline)) {
        last unless $self->_interprete($line);
    }
    $self->_drain_children;
    $self->_up("bye");
}


sub _interprete {
    # RETURN: 1, the session goes on; 0, it ends. Answers on the UP channel;
    #         never dies.
    my ($self, $line) = @_;
    my @field = split ' ', $line;
    if (@field == 1 && $field[0] =~ /^(quit|q|exit)$/) { return 0 }
    if (@field == 1 && $field[0] eq "info") {
        $self->_up("info: $_") for $self->info_block_lines;
        $self->_up("done - 0");
        return 1;
    }
    if (@field == 4 && $field[0] eq "run") {
        my (undef, $token, $sink_out, $sink_err) = @field;
        my ($choice, $found_f) = $self->_find_choice($token);
        if    (!$found_f)                         { $self->_up("fail $token unknown-choice") }
        elsif (($self->{parallel} // "") eq "process") {
            $self->_run_forked($token, $choice, $sink_out, $sink_err);
        }
        else {
            my $status = $self->_run_into_sinks($choice, $sink_out, $sink_err);
            $self->_up("done $token $status");
        }
        return 1;
    }
    $self->_up("fail - bad-command");
    return 1;
}


sub _find_choice {
    # RETURN: (choice, 1), the token names a choice -- by name, by its index
    #         into the sorted choice list, or '-' for the choice-less test;
    #         (undef, 0), else.
    my ($self, $token) = @_;
    my $map = $self->{choice_map};
    return ($NONE, exists $map->{$NONE} ? 1 : 0) if $token eq $NONE;
    return ($token, 1)                           if exists $map->{$token};
    if ($token =~ /^\d+$/ && $token < @{$self->{sorted}}) {
        return ($self->{sorted}[$token], 1);
    }
    return (undef, 0);
}


sub _run_into_sinks {
    # RETURN: integer, 0 where the choice ran and returned; the exit status it
    #         asked for by 'exit'; 1 where it died (the message in the error
    #         sink). fd 1 and 2 point at the sinks meanwhile, and are restored
    #         -- both sinks closed -- before the return.
    my ($self, $choice, $sink_out, $sink_err) = @_;
    STDOUT->flush; STDERR->flush;
    open(my $saved_out, ">&", \*STDOUT) or die; open(my $saved_err, ">&", \*STDERR) or die;
    open(STDOUT, ">", $sink_out) or return 1;
    open(STDERR, ">", $sink_err) or return 1;
    STDOUT->autoflush(1); STDERR->autoflush(1);
    my $status = 0;
    {
        local $IN_SINK_F = 1;
        my $ok = eval { $self->{choice_map}{$choice}->(); 1 };
        if ($ok) {
            print "<hwut-end>\n" unless $ENV{HWUT_NO_TERMINAL};
        }
        elsif (ref $@ eq "Hwut::Runner::Exit") { $status = $@->{code} }
        else                                    { print STDERR $@; $status = 1 }
    }
    STDOUT->flush; STDERR->flush;
    open(STDOUT, ">&", $saved_out) or die; open(STDERR, ">&", $saved_err) or die;
    close $saved_out; close $saved_err;
    return $status;
}


sub _run_forked {
    # RETURN: nothing; the child is registered and runs on its own. Its end is
    #         reported 'done <token> <status>' when it is reaped.
    my ($self, $token, $choice, $sink_out, $sink_err) = @_;
    STDOUT->flush; STDERR->flush;
    my $pid = fork;
    die "Hwut::Runner: fork: $!\n" unless defined $pid;
    if ($pid == 0) {
        my $status = eval { $self->_run_into_sinks($choice, $sink_out, $sink_err) } // 1;
        _exit($status & 0xFF);
    }
    $self->{pending}{$pid} = $token;
    $self->_reap(0);
}


sub _reap {
    # RETURN: nothing. Every child that has ended is reported; with 'block_f'
    #         waits until none is left.
    my ($self, $block_f) = @_;
    while (%{$self->{pending}}) {
        my $pid = waitpid(-1, $block_f ? 0 : POSIX::WNOHANG());
        last if $pid <= 0;
        my $token = delete $self->{pending}{$pid};
        next unless defined $token;
        my $code = WIFEXITED($?) ? WEXITSTATUS($?) : WIFSIGNALED($?) ? -WTERMSIG($?) : 1;
        $self->_up("done $token $code");
    }
}


sub _drain_children {
    # RETURN: nothing; upon return every child is reaped and reported.
    my ($self) = @_;
    $self->_reap(1);
}


sub _up {
    # RETURN: nothing; 'message' is written and flushed on the UP channel.
    my ($self, $message) = @_;
    $self->_reap(0) if %{$self->{pending}} && $message !~ /^done /;
    print { $self->{control} } "$message\n";
}


sub _readline {
    # RETURN: string, the next non-empty stripped line of stdin; undef at the
    #         end of input. Children that ended meanwhile are reported first.
    my ($self) = @_;
    while (1) {
        $self->_reap(0);
        my $line = <STDIN>;
        return undef unless defined $line;
        $line =~ s/^\s+|\s+$//g;
        return $line if length $line;
    }
}


sub levenshtein_best_match {
    # RETURN: string, the element of 'haystack' least distant from 'needle';
    #         undef where 'needle' is undef or 'haystack' is empty.
    my ($needle, $haystack) = @_;
    return undef if !defined $needle || !@$haystack;
    return $needle if grep { $_ eq $needle } @$haystack;
    my ($best_key, $best_dist);
    for my $key (@$haystack) {
        my $dist = levenshtein_distance($needle, $key);
        ($best_key, $best_dist) = ($key, $dist) if !defined $best_dist || $dist < $best_dist;
    }
    return $best_key;
}


sub levenshtein_distance {
    # RETURN: integer >= 0, the Levenshtein distance between 'a' and 'b'.
    my ($a, $b) = @_;
    return 0           if $a eq $b;
    return length $b   if $a eq "";
    return length $a   if $b eq "";
    ($a, $b) = ($b, $a) if length $a < length $b;
    my @prev = (0 .. length $b);
    for my $i (1 .. length $a) {
        my @cur = ($i);
        for my $j (1 .. length $b) {
            my $cost = substr($a, $i - 1, 1) eq substr($b, $j - 1, 1) ? 0 : 1;
            my $min  = $cur[$j - 1] + 1;
            $min = $prev[$j] + 1         if $prev[$j] + 1 < $min;
            $min = $prev[$j - 1] + $cost if $prev[$j - 1] + $cost < $min;
            push @cur, $min;
        }
        @prev = @cur;
    }
    return $prev[-1];
}

1;
