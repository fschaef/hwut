# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# PURPOSE: Parse the HOCON subset of the specification language into the
#          ANNOTATED TREE -- the port of 'python/hwut_hocon.py'
#          (README-hwut_hocon.txt): every key, every value and every block
#          carries its file-relative position. A test author in any language
#          meets this grammar, and every language is given a parser that
#          behaves the same way: the same tree, the same faults, the same
#          words.
#
#     use Hwut::Hocon;
#     my @line = map { Hwut::Hocon::SourceLine->new($text[$_], $_ + 1, 0) } 0 .. $#text;
#     my ($document, $fault_list) = Hwut::Hocon::parse(\@line, "f.hocon");
#
#     $document->entry_list      [ Entry { key, key_position, node }, ... ]
#     $document->get("key")      the entry, or undef
#     Scalar  { value, kind, position }    kind: str int float bool null
#     List    { item_list, position }
#     Object  { position, entry_list }
#     Position, Fault            stringify as 'line:column' and
#                                'file:line:column: KIND: message'
#
# THE SUBSET: nested objects, lists, numbers in every radix, booleans
# (true/false/yes/no), the spellings of nothing, '#' and '//' comments, '='
# or ':' before a value, a brace directly after a key. A string value is
# written in double quotes; a text of several lines in three. Refused by
# name: 'include', '${...}', '+='. The parser accumulates faults and recovers
# at the next line; it never dies.
#
# THE KIND IS PYTHON'S TYPE, said: Perl has one scalar, so a value carries
# the kind Python's parser gives it -- 'int' for '42', 'float' for '42.0'.
#______________________________________________________________________________
package Hwut::Hocon;
use strict;
use warnings;

#  ------------------------------------------------------------ the records
package Hwut::Hocon::Position {
    use overload '""' => sub { "$_[0]{line}:$_[0]{column}" }, fallback => 1;
    sub new    { my ($c, $l, $col) = @_; bless { line => $l, column => $col }, $c }
    sub line   { $_[0]{line} }
    sub column { $_[0]{column} }
}

package Hwut::Hocon::Fault {
    use overload '""' => sub { my $f = $_[0];
                               "$f->{file}:$f->{position}: $f->{kind}: $f->{message}" },
                 fallback => 1;
    sub new { my ($c, %a) = @_; bless {%a}, $c }
    sub kind     { $_[0]{kind} }            # 'SYNTAX' or 'REFUSED'
    sub file     { $_[0]{file} }
    sub position { $_[0]{position} }
    sub message  { $_[0]{message} }
}

package Hwut::Hocon::SourceLine {
    sub new { my ($c, $text, $line, $offset) = @_;
              bless { text => $text, line => $line, column_offset => $offset // 0 }, $c }
}

package Hwut::Hocon::Scalar {
    sub new      { my ($c, $value, $kind, $pos) = @_; bless { value => $value, kind => $kind, position => $pos }, $c }
    sub value    { $_[0]{value} }
    sub kind     { $_[0]{kind} }
    sub position { $_[0]{position} }
}

package Hwut::Hocon::List {
    sub new       { my ($c, $items, $pos) = @_; bless { item_list => $items, position => $pos }, $c }
    sub item_list { @{$_[0]{item_list}} }
    sub position  { $_[0]{position} }
}

package Hwut::Hocon::Entry {
    sub new          { my ($c, $k, $kp, $n) = @_; bless { key => $k, key_position => $kp, node => $n }, $c }
    sub key          { $_[0]{key} }
    sub key_position { $_[0]{key_position} }
    sub node         { $_[0]{node} }
}

package Hwut::Hocon::Object {
    sub new        { my ($c, $pos) = @_; bless { position => $pos, entry_list => [] }, $c }
    sub position   { $_[0]{position} }
    sub entry_list { @{$_[0]{entry_list}} }
    sub get {
        # RETURN: Hwut::Hocon::Entry named 'key'; undef where none is.
        my ($self, $key) = @_;
        for (@{$self->{entry_list}}) { return $_ if $_->{key} eq $key }
        return undef;
    }
    sub keys { map { $_->{key} } @{$_[0]{entry_list}} }
}

#  --------------------------------------------------------------- the cursor
package Hwut::Hocon::Cursor {
    sub new {
        my ($c, $lines) = @_;
        bless { line_list => $lines, line_n => scalar @$lines, i_line => 0, i_col => 0,
                text => @$lines ? $lines->[0]{text} : "" }, $c;
    }
    sub at_end { $_[0]{i_line} >= $_[0]{line_n} }
    sub peek {
        # RETURN: string, the character 'ahead' places from here on this line;
        #         "\n" at its end; '' beyond the last line.
        my ($self, $ahead) = @_;
        return "" if $self->{i_line} >= $self->{line_n};
        my $i = $self->{i_col} + ($ahead // 0);
        return $i < length $self->{text} ? substr($self->{text}, $i, 1) : "\n";
    }
    sub skip { $_[0]{i_col} += $_[1] }
    sub skip_line {
        my ($self) = @_;
        $self->{i_line} += 1;
        $self->{i_col}   = 0;
        $self->{text}    = $self->{i_line} < $self->{line_n}
                         ? $self->{line_list}[$self->{i_line}]{text} : "";
    }
    sub position {
        my ($self) = @_;
        if ($self->{i_line} >= $self->{line_n}) {
            return Hwut::Hocon::Position->new(1, 1) unless @{$self->{line_list}};
            my $last = $self->{line_list}[-1];
            return Hwut::Hocon::Position->new($last->{line},
                                              $last->{column_offset} + length($last->{text}) + 1);
        }
        my $line = $self->{line_list}[$self->{i_line}];
        return Hwut::Hocon::Position->new($line->{line}, $line->{column_offset} + $self->{i_col} + 1);
    }
}

package Hwut::Hocon;

my %BOOL      = (true => 1, yes => 1, false => 0, no => 0);
my %NULL      = map { $_ => 1 } qw(null nil none nihil);
my $DECIMAL_RE = qr/^[-+]?(?:[0-9](?:_?[0-9])*(?:\.(?:[0-9](?:_?[0-9])*)?)?|\.[0-9](?:_?[0-9])*)(?:[eE][-+]?[0-9](?:_?[0-9])*)?$/;
my %RADIX     = ("0x" => 16, "0X" => 16, "0b" => 2, "0B" => 2, "0o" => 8, "0O" => 8);
my %RADIX_DIGIT = (16 => "0123456789abcdefABCDEF", 2 => "01", 8 => "01234567");
my $ROMAN_RE  = qr/^M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$/;
my %ROMAN     = (I => 1, V => 5, X => 10, L => 50, C => 100, D => 500, M => 1000);
my $NOT_A_TOKEN = \"not a token";
my $TOKEN_RE  = qr/\G[^\s{}\[\]=,:"#]*/;
my $QUOTED_PLAIN_RE = qr/\G([^"\\\n]*)"/;
my %ESCAPE    = (n => "\n", t => "\t", '"' => '"', "\\" => "\\");
my $TRIPLE    = '"""';

sub _fault {
    my ($list, $kind, $file, $position, $message) = @_;
    push @$list, Hwut::Hocon::Fault->new(kind => $kind, file => $file,
                                         position => $position, message => $message);
}

sub _token_at {
    # RETURN: string, the token -- a run of no binder, opener, closer,
    #         separator or blank -- at column 'i' of 'text'.
    my ($text, $i) = @_;
    pos($text) = $i;
    return $text =~ /$TOKEN_RE/gc ? substr($text, $-[0], $+[0] - $-[0]) : "";
}

sub _strip { my ($s) = @_; $s =~ s/^\s+|\s+$//g; return $s }

sub parse {
    # RETURN: (Hwut::Hocon::Object, array ref of Hwut::Hocon::Fault) -- the
    #         document, every entry of the outermost level, possibly empty;
    #         and every fault found, empty on a clean parse. 'line_list' are
    #         SourceLines; 'file' names the file for faults.
    my ($line_list, $file) = @_;
    my @fault;
    my $cursor   = Hwut::Hocon::Cursor->new($line_list);
    my $document = _parse_body($cursor, undef, $file, \@fault);
    return ($document, \@fault);
}

sub _parse_body {
    my ($cursor, $terminator, $file, $fault) = @_;
    my $result = Hwut::Hocon::Object->new($cursor->position);
    while (1) {
        _skip_blank($cursor);
        if ($cursor->at_end) {
            _fault($fault, "SYNTAX", $file, $cursor->position,
                   "unterminated object: '$terminator' missing") if defined $terminator;
            return $result;
        }
        my $c = $cursor->peek;
        if (defined $terminator && $c eq $terminator) { $cursor->skip(1); return $result }
        elsif ($c eq "}") {
            _fault($fault, "SYNTAX", $file, $cursor->position, "unmatched '}'");
            $cursor->skip(1);
        }
        else { _parse_entry($cursor, $result, $file, $fault) }
    }
}

sub _parse_entry {
    my ($cursor, $object, $file, $fault) = @_;
    my $key_position = $cursor->position;
    my $key = _parse_key($cursor, $file, $fault);
    if (!defined $key) { $cursor->skip_line; return }
    if ($key eq "include") {
        _fault($fault, "REFUSED", $file, $key_position,
               "'include' does not exist here: a specification refers to nothing outside its file");
        $cursor->skip_line;
        return;
    }
    _skip_space($cursor);
    my $c = $cursor->peek;
    if ($c eq "=" || $c eq ":") { $cursor->skip(1); _skip_space($cursor) }
    elsif ($c eq "{") { }
    elsif ($c eq "+" && $cursor->peek(1) eq "=") {
        _fault($fault, "REFUSED", $file, $cursor->position, "'+=' does not exist here");
        $cursor->skip_line;
        return;
    }
    else {
        _fault($fault, "SYNTAX", $file, $cursor->position,
               "expected '=', ':' or '{' after key '$key'");
        $cursor->skip_line;
        return;
    }
    my $node = _parse_value($cursor, $file, $fault, 0);
    return unless defined $node;
    if (defined $object->get($key)) {
        _fault($fault, "SYNTAX", $file, $key_position,
               "duplicate key '$key'; the first stands, this one is refused");
        return;
    }
    push @{$object->{entry_list}}, Hwut::Hocon::Entry->new($key, $key_position, $node);
}

sub _parse_key {
    my ($cursor, $file, $fault) = @_;
    return _parse_quoted($cursor, $file, $fault) if $cursor->peek eq '"';
    my $text = _token_at($cursor->{text}, $cursor->{i_col});
    if ($text eq "") {
        _fault($fault, "SYNTAX", $file, $cursor->position,
               "expected a key, found '" . _strip($cursor->peek) . "'");
        return undef;
    }
    $cursor->skip(length $text);
    return $text;
}

sub _parse_value {
    my ($cursor, $file, $fault, $in_list_f) = @_;
    _skip_space($cursor);
    my $position = $cursor->position;
    my $c = $cursor->peek;
    if ($c eq "{") { $cursor->skip(1); return _parse_body($cursor, "}", $file, $fault) }
    if ($c eq "[") { $cursor->skip(1); return _parse_list($cursor, $position, $file, $fault) }
    if ($c eq '"' && $cursor->peek(1) eq '"' && $cursor->peek(2) eq '"') {
        my $value = _parse_triple_quoted($cursor, $file, $fault);
        return defined $value ? Hwut::Hocon::Scalar->new($value, "str", $position) : undef;
    }
    if ($c eq '"') {
        my $value = _parse_quoted($cursor, $file, $fault);
        return defined $value ? Hwut::Hocon::Scalar->new($value, "str", $position) : undef;
    }
    if ($c eq '$' && $cursor->peek(1) eq "{") {
        _fault($fault, "REFUSED", $file, $position,
               "substitutions '\${...}' do not exist here: a specification refers to nothing outside its file");
        $cursor->skip_line;
        return undef;
    }
    return _parse_bare($cursor, $position, $file, $fault, $in_list_f);
}

sub _parse_list {
    my ($cursor, $position, $file, $fault) = @_;
    my @item;
    while (1) {
        _skip_blank($cursor);
        if ($cursor->at_end) {
            _fault($fault, "SYNTAX", $file, $cursor->position, "unterminated list: ']' missing");
            last;
        }
        my $c = $cursor->peek;
        if    ($c eq "]") { $cursor->skip(1); last }
        elsif ($c eq ",") { $cursor->skip(1) }
        elsif ($c eq "}") {
            _fault($fault, "SYNTAX", $file, $cursor->position,
                   "unterminated list: ']' missing before '}'");
            last;
        }
        else {
            my @before = @$cursor{qw(i_line i_col)};
            my $item = _parse_value($cursor, $file, $fault, 1);
            push @item, $item if defined $item;
            $cursor->skip(1) if !defined $item
                             && $cursor->{i_line} == $before[0] && $cursor->{i_col} == $before[1];
        }
    }
    return Hwut::Hocon::List->new(\@item, $position);
}

sub cleandoc {
    # RETURN: string, 'text' laid out as Python's 'inspect.cleandoc' lays out
    #         a docstring: tabs expanded, the first line's leading blanks and
    #         the indentation common to the other lines removed, empty lines
    #         at both ends dropped.
    my ($text) = @_;
    my @line = map { _expandtabs($_) } split /\n/, $text, -1;
    my $margin;
    for my $line (@line[1 .. $#line]) {
        (my $content = $line) =~ s/^\s+//;
        next unless length $content;
        my $indent = length($line) - length($content);
        $margin = $indent if !defined $margin || $indent < $margin;
    }
    $line[0] =~ s/^\s+// if @line;
    if (defined $margin) {
        $_ = length($_) >= $margin ? substr($_, $margin) : "" for @line[1 .. $#line];
    }
    pop @line   while @line && $line[-1] eq "";
    shift @line while @line && $line[0] eq "";
    return join("\n", @line);
}

sub _expandtabs {
    my ($line) = @_;
    my $out = "";
    for my $c (split //, $line) {
        if ($c eq "\t") { $out .= " " x (8 - length($out) % 8) }
        else            { $out .= $c; $out = "" if $c eq "\n" }
    }
    return $out;
}

sub _parse_triple_quoted {
    my ($cursor, $file, $fault) = @_;
    my $begin = $cursor->position;
    $cursor->skip(3);
    my @piece;
    while (!$cursor->at_end) {
        my $text = $cursor->{text};
        my $end  = index($text, $TRIPLE, $cursor->{i_col});
        if ($end >= 0) {
            push @piece, substr($text, $cursor->{i_col}, $end - $cursor->{i_col});
            $cursor->{i_col} = $end + 3;
            return cleandoc(join("\n", @piece));
        }
        push @piece, substr($text, $cursor->{i_col});
        $cursor->skip_line;
    }
    _fault($fault, "SYNTAX", $file, $begin,
           "unterminated triple-quoted string: closing '\"\"\"' missing");
    return undef;
}

sub _parse_quoted {
    my ($cursor, $file, $fault) = @_;
    my $begin = $cursor->position;
    my $text  = $cursor->{text};
    my $i     = $cursor->{i_col} + 1;
    pos($text) = $i;
    if ($text =~ /$QUOTED_PLAIN_RE/gc) {
        $cursor->{i_col} = $+[0];
        return $1;
    }
    my $piece = "";
    while (1) {
        if ($i >= length $text) {
            _fault($fault, "SYNTAX", $file, $begin, "unterminated string");
            $cursor->{i_col} = $i;
            return undef;
        }
        my $c = substr($text, $i, 1);
        if ($c eq '"') { $cursor->{i_col} = $i + 1; return $piece }
        if ($c eq "\\") {
            $i += 1;
            my $escaped = $i < length $text ? substr($text, $i, 1) : "";
            $piece .= exists $ESCAPE{$escaped} ? $ESCAPE{$escaped} : $escaped;
            $i += 1;
        }
        else { $piece .= $c; $i += 1 }
    }
}

sub _parse_bare {
    my ($cursor, $position, $file, $fault, $in_list_f) = @_;
    my $raw = _token_at($cursor->{text}, $cursor->{i_col});
    #  A SIGN STANDING APART from its digits: '- 0.12'.
    if ($raw eq "+" || $raw eq "-") {
        my $text  = $cursor->{text};
        my $start = _blank_end($text, $cursor->{i_col} + 1);
        my $after = _token_at($text, $start);
        if ($after ne "" && !_is_not_token(_number($after))) {
            $cursor->{i_col} = $start + length $after;
            return Hwut::Hocon::Scalar->new(_number($raw . $after), $position);
        }
    }
    if (substr($raw, 0, 2) eq '${') {
        _fault($fault, "REFUSED", $file, $cursor->position, "substitutions '\${...}' do not exist here");
        $cursor->skip_line;
        return undef;
    }
    my $i_comment = index($raw, "//");
    $raw = substr($raw, 0, $i_comment) if $i_comment != -1;
    $cursor->skip(length $raw);
    if ($raw eq "") {
        if ($in_list_f) {
            _fault($fault, "SYNTAX", $file, $position,
                   "expected a value, found '" . _strip($cursor->peek) . "'");
            return undef;
        }
        return Hwut::Hocon::Scalar->new(undef, "null", $position);
    }
    my @value = _interpret($raw);
    if (_is_not_token($value[0])) {
        _fault($fault, "SYNTAX", $file, $position, "a string is written in double quotes: \"$raw\"");
        return undef;
    }
    return Hwut::Hocon::Scalar->new(@value, $position);
}

sub _is_not_token { my ($v) = @_; return ref $v && $v == $NOT_A_TOKEN }

sub _interpret {
    # RETURN: (value, kind) -- what the bare text says: (undef, 'null') for
    #         the spellings of nothing, (1|0, 'bool'), or a number; or
    #         ($NOT_A_TOKEN) where it is an unquoted string.
    my ($raw) = @_;
    return (undef, "null")       if $NULL{$raw};
    return ($BOOL{$raw}, "bool") if exists $BOOL{$raw};
    return _number($raw);
}

sub _number {
    # RETURN: (value, 'int' | 'float') -- the number the text spells in
    #         whatever radix; ($NOT_A_TOKEN) where it spells none.
    my ($raw) = @_;
    my $first = substr($raw, 0, 1);
    my $body  = ($first eq "+" || $first eq "-") ? substr($raw, 1) : $raw;
    my $sign  = $first eq "-" ? -1 : 1;
    my $prefix = substr($body, 0, 2);
    if ($prefix eq "0r" || $prefix eq "0R") {
        my $value = _roman(substr($body, 2));
        return _is_not_token($value) ? ($value) : ($sign * $value, "int");
    }
    if (my $radix = $RADIX{$prefix}) {
        my $digit = _without_helper(substr($body, 2), $RADIX_DIGIT{$radix});
        return ($NOT_A_TOKEN) unless defined $digit;
        my $value = 0;
        $value = $value * $radix + index($RADIX_DIGIT{16}, lc $_) for split //, $digit;
        return ($sign * $value, "int");
    }
    return ($NOT_A_TOKEN) unless $raw =~ $DECIMAL_RE;
    (my $text = $raw) =~ s/_//g;
    return ($text + 0.0, "float") if $text =~ /[.eE]/;
    return ($text + 0, "int");
}

sub _without_helper {
    my ($text, $digit_set) = @_;
    return undef if $text eq "" || substr($text, 0, 1) eq "_" || substr($text, -1) eq "_";
    return undef if index($text, "__") >= 0;
    (my $stripped = $text) =~ s/_//g;
    return undef if $stripped eq "";
    for my $c (split //, $stripped) { return undef if index($digit_set, $c) < 0 }
    return $stripped;
}

sub _roman {
    my ($text) = @_;
    return $NOT_A_TOKEN if $text eq "" || $text !~ $ROMAN_RE;
    my ($total, $previous) = (0, 0);
    for my $c (reverse split //, $text) {
        my $value = $ROMAN{$c};
        $total = $value < $previous ? $total - $value : $total + $value;
        $previous = $value if $value > $previous;
    }
    return $total;
}

sub _blank_end {
    my ($text, $i) = @_;
    my $n = length $text;
    $i++ while $i < $n && (substr($text, $i, 1) eq " " || substr($text, $i, 1) eq "\t");
    return $i;
}

sub _skip_space {
    my ($cursor) = @_;
    my $text = $cursor->{text};
    my $i = _blank_end($text, $cursor->{i_col});
    $cursor->{i_col} = $i;
    $cursor->skip_line if $i < length $text
                       && (substr($text, $i, 1) eq "#" || substr($text, $i, 2) eq "//");
}

sub _skip_blank {
    my ($cursor) = @_;
    while ($cursor->{i_line} < $cursor->{line_n}) {
        my $text = $cursor->{text};
        my $n = length $text;
        my $i = $cursor->{i_col};
        $i++ while $i < $n && substr($text, $i, 1) =~ /^[ \t,]$/;
        if ($i >= $n) { $cursor->skip_line; next }
        $cursor->{i_col} = $i;
        my $c = substr($text, $i, 1);
        if ($c eq "#" || ($c eq "/" && substr($text, $i, 2) eq "//")) { $cursor->skip_line; next }
        return;
    }
}

1;
