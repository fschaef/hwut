# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# PURPOSE: A STATE MACHINE AS A TEST'S MODEL OF THE SYSTEM UNDER TEST -- the
#          port of 'python/hwut_fsm.py' (README-hwut_fsm.txt). The states it
#          may be in, the events that move it, the states it must never reach.
#          A test FIRES the events it observes; every event the model does not
#          allow, and every forbidden state entered, is PRINTED as a line, so
#          it lands in the GOOD file and the comparison judges it.
#
#     use Hwut::Fsm;
#     my $m = Hwut::Fsm->from_string(<<'END');
#         initial: idle
#         forbidden: crashed
#         idle    ---( request )---> waiting ---( grant )---> busy
#         busy    ---( release )---> idle
#         :       ---( fault )--->   crashed
#     END
#     $m->fire("request", 1);      # 1
#     $m->fire("release", 2);      # BREACH line 2: 'release' in 'waiting' -- allowed: grant
#     $m->report;                  # what was visited, what never was
#
# The same model text, the same words, the same sorted reports as the Python
# module. In Perl:
#
#     new(transitions => [[s, e, t], ...], initial => 'A', forbidden => [...],
#         final => [...], DFA => 1, name => 'fsm', write => sub {...},
#         states => [...])
#     from_string($text, DFA => 0, name => ..., write => ...)
#
#     'where' (a breach's place): a number names a line ('line 3'), any
#     other text stands as written.
#
#     The two phases take the block:
#         $m->disallowed($event, $state, $where, sub { ... });
#         $m->forbidding($state, $where, sub { ... });
#     and lift the mask on leaving it -- also where the block dies.
#
#     A model that cannot be meant dies with a Hwut::FsmError: its 'message'
#     is the Python FsmError's text.
#______________________________________________________________________________
package Hwut::FsmError;
use strict;
use warnings;
use overload '""' => sub { $_[0]{message} . "\n" }, fallback => 1;

sub throw {
    # RETURN: never; dies with a Hwut::FsmError carrying 'message'.
    my ($class, $message) = @_;
    die bless { message => $message }, $class;
}

sub message { $_[0]{message} }


package Hwut::Fsm;
use strict;
use warnings;

my $ARROW_RE = qr/-+\s*\(\s*([^()]*?)\s*\)\s*-*>/;
my $NAME_RE  = qr/^(?:state\s+)?([A-Za-z_][\w.\-]*)$/;
my $KEY_RE   = qr/^(initial|forbidden|final)\s*:\s*(.*)$/;
my $ALL      = "\x01*";      # the state of a mask over EVERY state (Python's None)

sub _fault { Hwut::FsmError->throw(sprintf(shift, @_)) }

sub _strip { my ($s) = @_; $s =~ s/^\s+|\s+$//g; return $s }

sub _name_of {
    # RETURN: string, the state 'text' names -- 'A' or 'state A'; dies with a
    #         Hwut::FsmError naming line 'number' else.
    my ($text, $number) = @_;
    my $t = _strip($text);
    return $1 if $t =~ $NAME_RE;
    _fault("line %d: '%s' names no state -- a state is a word ('A', 'state A')",
           $number, $t);
}

sub _where_text {
    # RETURN: string, ' line 3' for a number, ' <text>' for a text, '' for undef.
    my ($where) = @_;
    return ""               if !defined $where;
    return " line $where"   if $where =~ /^-?\d+$/;
    return " $where";
}

sub _since_text {
    # RETURN: string, ' since line 9', ' since <text>', or '' for undef.
    my ($where) = @_;
    return defined $where ? " since" . _where_text($where) : "";
}

sub _edge_key { join "\0", @_ }

sub new {
    # RETURN: Hwut::Fsm, standing in 'initial'; dies with a Hwut::FsmError
    #         where a DFA has two transitions for one (state, event), or an
    #         initial, forbidden or final state is named nowhere else.
    my ($class, %arg) = @_;
    my $self = bless {
        name   => $arg{name} // "fsm",
        dfa_f  => (exists $arg{DFA} ? ($arg{DFA} ? 1 : 0) : 1),
        write  => $arg{write} // sub { print "$_[0]\n" },
        edge   => {},                  # "state\0event" -> { target => 1 }
    }, $class;
    my $initial = $arg{initial};
    my %state   = ($initial => 1, map { $_ => 1 } @{$arg{states} // []});
    for my $triple (@{$arg{transitions} // []}) {
        my ($source, $event, $target) = @$triple;
        my $set = $self->{edge}{_edge_key($source, $event)} //= {};
        if ($self->{dfa_f} && %$set && !$set->{$target}) {
            _fault("'%s' --(%s)--> '%s' and '%s': a DFA moves one way per event -- or 'DFA=False'",
                   $source, $event, (sort keys %$set)[0], $target);
        }
        $set->{$target} = 1;
        @state{$source, $target} = (1, 1);
    }
    $self->{initial}         = $initial;
    $self->{model_forbidden} = { map { $_ => 1 } @{$arg{forbidden} // []} };
    $self->{final}           = { map { $_ => 1 } @{$arg{final} // []} };
    for my $pair (["forbidden", $self->{model_forbidden}], ["final", $self->{final}]) {
        my @unknown = sort grep { !$state{$_} } keys %{$pair->[1]};
        _fault("%s state(s) %s: named nowhere else in the model",
               $pair->[0], join(", ", map { "'$_'" } @unknown)) if @unknown;
    }
    my %all = (%state, %{$self->{model_forbidden}});
    $self->{state_list} = [sort keys %all];
    my %event = map { (split /\0/, $_, 2)[1] => 1 } keys %{$self->{edge}};
    $self->{event_list} = [sort keys %event];
    $self->reset;
    return $self;
}

#  ---------------------------------------------------------------- reading
sub from_string {
    # RETURN: Hwut::Fsm, the model the text states; dies with a Hwut::FsmError
    #         naming the line else. The text is 'python/hwut_fsm.py's: one
    #         statement per line, '#' a comment -- 'initial:', 'forbidden:',
    #         'final:', 'state A', 'A ---( ev )---> B ---( ev2 )---> C', and
    #         ':' for the state that began the line above.
    my ($class, $text, %arg) = @_;
    my $dfa_f = exists $arg{DFA} ? $arg{DFA} : 1;
    my (@triple, %declared, %line_of, $first, $previous_head);
    my @raw = split /\r\n|\n|\r/, $text, -1;
    for my $number (1 .. @raw) {
        my $line = _strip((split /#/, $raw[$number - 1], 2)[0] // "");
        next if $line eq "";
        if ($line =~ $KEY_RE) {
            my ($word, $rest) = ($1, $2);
            my @name = map { _name_of($_, $number) } grep { /\S/ } split /,/, $rest, -1;
            _fault("line %d: 'initial:' names one state", $number)
                if $word eq "initial" && @name != 1;
            push @{$declared{$word}}, @name;
            next;
        }
        my @part = split $ARROW_RE, $line, -1;
        if (@part == 1) {
            my $head = _name_of($line, $number);
            $first //= $head;
            push @triple, [$head, undef, undef];
            $previous_head = $head;
            next;
        }
        for (my $i = 1; $i < @part; $i += 2) {
            _fault("line %d: an arrow names no event -- '---( event )--->'", $number)
                if _strip($part[$i]) eq "";
        }
        my $head_text = _strip($part[0]);
        my $head;
        if ($head_text eq ":") {
            _fault("line %d: ':' stands for the state of the line above, and none stands there",
                   $number) unless defined $previous_head;
            $head = $previous_head;
        }
        else { $head = _name_of($head_text, $number) }
        $first //= $head;
        $previous_head = $head;
        my $source = $head;
        for (my $i = 1; $i < @part; $i += 2) {
            my $target = _name_of($part[$i + 1], $number);
            my $event  = _strip($part[$i]);
            my $key    = _edge_key($source, $event);
            if ($dfa_f && $line_of{$key} && $line_of{$key}[0] ne $target) {
                _fault("line %d: '%s' --(%s)--> '%s', and line %d: --> '%s' -- a DFA moves one way per event, or 'DFA=False'",
                       $number, $source, $event, $target, $line_of{$key}[1], $line_of{$key}[0]);
            }
            $line_of{$key} //= [$target, $number];
            push @triple, [$source, $event, $target];
            $source = $target;
        }
    }
    _fault("the model names no state") if !defined $first && !$declared{initial};
    my $initial = ($declared{initial} // [$first])->[0];
    return $class->new(
        transitions => [grep { defined $_->[1] } @triple],
        initial     => $initial,
        forbidden   => $declared{forbidden} // [],
        final       => $declared{final} // [],
        DFA         => $dfa_f,
        name        => $arg{name} // "fsm",
        write       => $arg{write},
        states      => [map { $_->[0] } grep { !defined $_->[1] } @triple],
    );
}

sub _edge_list {
    # RETURN: list of [state, event, target], every transition, sorted.
    my ($self) = @_;
    my @edge;
    for my $key (keys %{$self->{edge}}) {
        my ($source, $event) = split /\0/, $key, 2;
        push @edge, [$source, $event, $_] for keys %{$self->{edge}{$key}};
    }
    return sort { $a->[0] cmp $b->[0] || $a->[1] cmp $b->[1] || $a->[2] cmp $b->[2] } @edge;
}

sub to_string {
    # RETURN: string, the model in the text 'from_string' reads, one
    #         transition per line, sorted.
    my ($self) = @_;
    my @line = ("initial: $self->{initial}");
    push @line, "forbidden: " . join(", ", sort keys %{$self->{model_forbidden}})
        if %{$self->{model_forbidden}};
    push @line, "final: " . join(", ", sort keys %{$self->{final}}) if %{$self->{final}};
    my %named = ($self->{initial} => 1);
    for my $edge ($self->_edge_list) {
        push @line, "$edge->[0] ---( $edge->[1] )---> $edge->[2]";
        @named{$edge->[0], $edge->[2]} = (1, 1);
    }
    push @line, map { "state $_" }
                grep { !$named{$_} && !$self->{model_forbidden}{$_} } @{$self->{state_list}};
    return join("\n", @line);
}

#  ---------------------------------------------------------------- running
sub reset {
    # RETURN: nothing. The machine stands in its initial state again, under the
    #         model as written: what was seen, every mask and every state
    #         forbidden or permitted since are forgotten.
    my ($self) = @_;
    $self->{mask}    = {};                         # "state\0event" -> since
    $self->{forbid}  = { map { $_ => undef } keys %{$self->{model_forbidden}} };
    $self->{permit}  = {};
    $self->{current} = { $self->{initial} => 1 };
    $self->{visit}   = { $self->{initial} => 1 };
    $self->{taken}   = {};                         # "s\0e\0t" -> count
    $self->{trace}   = [];
    $self->{breach_n} = 0;
}

sub breach_n { $_[0]{breach_n} }
sub _write   { my ($self, $line) = @_; $self->{write}->($line) }

sub fire {
    # RETURN: 1, 'event' moved the machine and entered no forbidden state;
    #         0, it was not allowed where the machine stands -- a BREACH line
    #            is written and the machine stays -- or it entered a forbidden
    #            state, which is written too.
    my ($self, $event, $where) = @_;
    my (%moved, @masked);
    for my $state (sort keys %{$self->{current}}) {
        my $key = _edge_key($state, $event);
        if ($self->_masked_f($state, $event)) {
            push @masked, $state if $self->{edge}{$key};
            next;
        }
        for my $target (sort keys %{$self->{edge}{$key} // {}}) {
            $moved{$target} = 1;
            $self->{taken}{join "\0", $state, $event, $target} += 1;
            push @{$self->{trace}}, [$where, $state, $event, $target];
        }
    }
    if (!%moved) {
        $self->{breach_n} += 1;
        my @allowed = $self->allowed;
        my $hint = @allowed ? "allowed: " . join(", ", @allowed) : "no event leaves it";
        if (!grep { $_ eq $event } @{$self->{event_list}}) {
            $hint = "an event the model never names";
        }
        elsif (@masked) {
            my $own = _edge_key($masked[0], $event);
            my $since = exists $self->{mask}{$own} ? $self->{mask}{$own}
                                                   : $self->{mask}{_edge_key($ALL, $event)};
            $hint = "disallowed" . _since_text($since);
        }
        $self->_write(sprintf("BREACH%s: '%s' in %s -- %s",
                              _where_text($where), $event, $self->_here, $hint));
        return 0;
    }
    $self->{current} = \%moved;
    $self->{visit}{$_} += 1 for keys %moved;
    my @entered = sort grep { exists $self->{forbid}{$_} } keys %moved;
    for my $state (@entered) {
        $self->{breach_n} += 1;
        my $how = ($self->{model_forbidden}{$state} && !defined $self->{forbid}{$state})
                ? "a forbidden state" : "forbidden" . _since_text($self->{forbid}{$state});
        $self->_write(sprintf("BREACH%s: '%s' entered by '%s' -- %s",
                              _where_text($where), $state, $event, $how));
    }
    return @entered ? 0 : 1;
}

#  ------------------------------------------------------ the law, changing
sub forbidden {
    # RETURN: list of strings, the states forbidden NOW, sorted.
    my ($self) = @_;
    return sort keys %{$self->{forbid}};
}

sub _masked_f {
    my ($self, $state, $event) = @_;
    return exists $self->{mask}{_edge_key($ALL, $event)}
        || exists $self->{mask}{_edge_key($state, $event)};
}

sub _known {
    # RETURN: nothing, where 'event' and 'state' are named by the model; dies
    #         with a Hwut::FsmError naming what is not, else.
    my ($self, $event, $state) = @_;
    _fault("'%s': an event the model never names -- events: %s",
           $event, join(", ", @{$self->{event_list}}))
        if defined $event && !grep { $_ eq $event } @{$self->{event_list}};
    _fault("'%s': a state the model never names -- states: %s",
           $state, join(", ", @{$self->{state_list}}))
        if defined $state && !grep { $_ eq $state } @{$self->{state_list}};
}

sub disallow {
    # RETURN: nothing. From now on 'event' is a breach -- in 'state' alone, in
    #         every state where undef -- until 'allow' lifts it.
    my ($self, $event, $state, $where) = @_;
    $self->_known($event, $state);
    my $key = _edge_key($state // $ALL, $event);
    $self->{mask}{$key} = $where unless exists $self->{mask}{$key};
}

sub allow {
    # RETURN: nothing. The mask 'disallow(event, state)' set is lifted; a mask
    #         of another scope stays.
    my ($self, $event, $state) = @_;
    $self->_known($event, $state);
    delete $self->{mask}{_edge_key($state // $ALL, $event)};
}

sub forbid {
    # RETURN: nothing. From now on entering 'state' is a breach, until
    #         'permit'. Where the machine STANDS in it, one BREACH line at once.
    my ($self, $state, $where) = @_;
    $self->_known(undef, $state);
    return if exists $self->{forbid}{$state};
    $self->{forbid}{$state} = $where;
    delete $self->{permit}{$state};
    if ($self->{current}{$state}) {
        $self->{breach_n} += 1;
        $self->_write(sprintf("BREACH%s: stands in '%s' -- forbidden%s",
                              _where_text($where), $state, _since_text($where)));
    }
}

sub permit {
    # RETURN: nothing. 'state' is no longer forbidden -- a state of the model's
    #         own 'forbidden:' too, until 'forbid' again.
    my ($self, $state, $where) = @_;
    $self->_known(undef, $state);
    return unless exists $self->{forbid}{$state};
    delete $self->{forbid}{$state};
    $self->{permit}{$state} = $where if $self->{model_forbidden}{$state};
}

sub _phase {
    # RETURN: what 'code' returns; 'leave' runs after it, also where it dies
    #         (and then the death passes on).
    my ($enter, $leave, $code) = @_;
    $enter->();
    my @result;
    my $ok = eval { @result = $code->(); 1 };
    my $error = $@;
    $leave->();
    die $error unless $ok;
    return wantarray ? @result : $result[0];
}

sub disallowed {
    # RETURN: what the block 'code' returns; 'event' disallowed (see
    #         'disallow') while it runs, allowed again on leaving it.
    my ($self, $event, $state, $where, $code) = @_;
    return _phase(sub { $self->disallow($event, $state, $where) },
                  sub { $self->allow($event, $state) }, $code);
}

sub forbidding {
    # RETURN: what the block 'code' returns; 'state' forbidden (see 'forbid')
    #         while it runs, permitted again on leaving it.
    my ($self, $state, $where, $code) = @_;
    return _phase(sub { $self->forbid($state, $where) },
                  sub { $self->permit($state) }, $code);
}

sub _here {
    # RETURN: string, where the machine stands: "'idle'", or "{'a', 'b'}".
    my ($self) = @_;
    my @state = sort keys %{$self->{current}};
    return "'$state[0]'" if @state == 1;
    return "{" . join(", ", map { "'$_'" } @state) . "}";
}

#  -------------------------------------------------------------- questions
sub state {
    # RETURN: string, the one state the machine stands in; dies with a
    #         Hwut::FsmError where it stands in a set (DFA => 0).
    my ($self) = @_;
    my @state = keys %{$self->{current}};
    _fault("the machine stands in %s: ask 'current()'", $self->_here) if @state != 1;
    return $state[0];
}

sub current  { my ($self) = @_; return sort keys %{$self->{current}} }
sub in_state { my ($self, $state) = @_; return $self->{current}{$state} ? 1 : 0 }

sub can {
    # RETURN: 1, 'event' would move the machine now; 0 else.
    my ($self, $event) = @_;
    for my $state (keys %{$self->{current}}) {
        return 1 if $self->{edge}{_edge_key($state, $event)} && !$self->_masked_f($state, $event);
    }
    return 0;
}

sub allowed {
    # RETURN: list of strings, the events that would move the machine now, sorted.
    my ($self) = @_;
    my %event;
    for my $key (keys %{$self->{edge}}) {
        my ($state, $event) = split /\0/, $key, 2;
        $event{$event} = 1 if $self->{current}{$state} && !$self->_masked_f($state, $event);
    }
    return sort keys %event;
}

sub trace {
    # RETURN: list of [where, state, event, state], every transition fired, in order.
    my ($self) = @_;
    return @{$self->{trace}};
}

#  -------------------------------------------------------- the model alone
sub _successor {
    # RETURN: hash ref, state -> sorted list of [event, state] leaving it --
    #         under the masks where 'masked_f', as written else.
    my ($self, $masked_f) = @_;
    my %found;
    for my $key (keys %{$self->{edge}}) {
        my ($source, $event) = split /\0/, $key, 2;
        next if $masked_f && $self->_masked_f($source, $event);
        push @{$found{$source}}, [$event, $_] for keys %{$self->{edge}{$key}};
    }
    @$_ = sort { $a->[0] cmp $b->[0] || $a->[1] cmp $b->[1] } @$_ for values %found;
    return \%found;
}

sub _masked_arg { my ($arg) = @_; return exists $arg->{masked} ? $arg->{masked} : 1 }

sub path_to {
    # RETURN: array ref, the shortest list of events from 'start' -- the
    #         initial state where undef, 'now' for where the machine stands --
    #         into 'state' (empty where 'start' is 'state'); undef where none
    #         leads there. Among equally short paths the first in event order;
    #         under the masks unless 'masked => 0'.
    my ($self, $state, %arg) = @_;
    my $start = $arg{start};
    my @start = !defined $start   ? ($self->{initial})
              : $start eq "now"   ? (sort keys %{$self->{current}})
              :                     ($start);
    return [] if grep { $_ eq $state } @start;
    my $successor = $self->_successor(_masked_arg(\%arg));
    my @queue = map { [$_, []] } sort @start;
    my %seen  = map { $_ => 1 } @start;
    while (my $entry = shift @queue) {
        my ($here, $path) = @$entry;
        for my $pair (@{$successor->{$here} // []}) {
            my ($event, $target) = @$pair;
            next if $seen{$target};
            return [@$path, $event] if $target eq $state;
            $seen{$target} = 1;
            push @queue, [$target, [@$path, $event]];
        }
    }
    return undef;
}

sub state_reachable {
    # RETURN: 1, 'state' can be reached from 'start' (see 'path_to'); 0 else.
    my ($self, $state, %arg) = @_;
    return defined $self->path_to($state, %arg) ? 1 : 0;
}

sub _forbidden_of {
    my ($self, $masked_f) = @_;
    return $masked_f ? $self->{forbid} : $self->{model_forbidden};
}

sub unreachable {
    # RETURN: list of strings, the states no path from the initial state
    #         reaches, forbidden ones left out, sorted.
    my ($self, %arg) = @_;
    my $masked_f  = _masked_arg(\%arg);
    my $forbidden = $self->_forbidden_of($masked_f);
    return grep { !exists $forbidden->{$_}
                  && !$self->state_reachable($_, masked => $masked_f) } @{$self->{state_list}};
}

sub dead_ends {
    # RETURN: list of strings, the states no event leaves that are neither
    #         final nor forbidden, sorted.
    my ($self, %arg) = @_;
    my $masked_f  = _masked_arg(\%arg);
    my $successor = $self->_successor($masked_f);
    my $forbidden = $self->_forbidden_of($masked_f);
    return grep { !$successor->{$_} && !$self->{final}{$_} && !exists $forbidden->{$_} }
           @{$self->{state_list}};
}

sub forbidden_reachable {
    # RETURN: list of strings, the forbidden states the model lets the system
    #         reach from the initial state, sorted.
    my ($self, %arg) = @_;
    my $masked_f = _masked_arg(\%arg);
    return grep { $self->state_reachable($_, masked => $masked_f) }
           sort keys %{$self->_forbidden_of($masked_f)};
}

sub check {
    # RETURN: integer, how many findings the MODEL has, each written as one
    #         line 'MODEL: ...'; 0 where it has none.
    my ($self, %arg) = @_;
    my $masked_f = _masked_arg(\%arg);
    my @line = map { "MODEL: '$_' cannot be reached" } $self->unreachable(masked => $masked_f);
    push @line, map { "MODEL: '$_' is a dead end -- no event leaves it" }
                $self->dead_ends(masked => $masked_f);
    push @line, map { "MODEL: forbidden '$_' is reachable: "
                      . join(" ", @{$self->path_to($_, masked => $masked_f)}) }
                $self->forbidden_reachable(masked => $masked_f);
    $self->_write($_) for @line;
    return scalar @line;
}

#  ---------------------------------------------------------------- the end
sub report {
    # RETURN: integer, the breaches seen, counting a non-final end; written
    #         before it, sorted, what the events covered of the model.
    my ($self) = @_;
    my @edge = $self->_edge_list;
    my $breach_n = $self->{breach_n};
    my $end_f = !%{$self->{final}} || grep { $self->{final}{$_} } keys %{$self->{current}};
    $breach_n += 1 unless $end_f;
    my @goal    = grep { !$self->{model_forbidden}{$_} } @{$self->{state_list}};
    my @visited = grep { $self->{visit}{$_} } @goal;
    $self->_write(sprintf("%s: %d of %d states visited, %d of %d transitions taken, %d breach%s",
                          $self->{name}, scalar @visited, scalar @goal,
                          scalar keys %{$self->{taken}}, scalar @edge, $breach_n,
                          $breach_n == 1 ? "" : "es"));
    for my $edge (@edge) {
        my $n = $self->{taken}{join "\0", @$edge};
        $self->_write(sprintf("  %s  %s ---( %s )---> %s%s",
                              $n ? "taken    " : "not taken", @$edge,
                              $n && $n > 1 ? "   x$n" : ""));
    }
    $self->_write("  never in   '$_'")
        for grep { !$self->{visit}{$_} && !$self->{model_forbidden}{$_} } @{$self->{state_list}};
    $self->_write("  ended in   " . $self->_here);
    my @mask = sort { $a->[1] cmp $b->[1] || $a->[0] cmp $b->[0] }
               map { my ($s, $e) = split /\0/, $_, 2; [$s eq $ALL ? "" : $s, $e, $self->{mask}{$_}] }
               keys %{$self->{mask}};
    for my $mask (@mask) {
        my ($state, $event, $since) = @$mask;
        $self->_write(sprintf("  disallowed '%s' %s%s", $event,
                              $state eq "" ? "in every state" : "in '$state'", _since_text($since)));
    }
    $self->_write(sprintf("  forbidden  '%s'%s", $_, _since_text($self->{forbid}{$_})))
        for sort grep { !$self->{model_forbidden}{$_} } keys %{$self->{forbid}};
    $self->_write(sprintf("  permitted  '%s'%s", $_, _since_text($self->{permit}{$_})))
        for sort keys %{$self->{permit}};
    $self->_write(sprintf("BREACH: ended in %s -- final: %s", $self->_here,
                          join(", ", sort keys %{$self->{final}}))) unless $end_f;
    return $breach_n;
}

1;
