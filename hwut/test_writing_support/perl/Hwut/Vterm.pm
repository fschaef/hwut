# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# PURPOSE: A TERMINAL'S SCREEN, READ BY A TEST -- 'libvterm' through
#          FFI::Platypus; the port of 'python/hwut_vterm.py'
#          (README-hwut_vterm.txt).
#
#     A program that draws a screen writes escape sequences; what a person
#     SEES is what a terminal makes of them. This module is that terminal:
#     bytes go in, and the grid of cells -- characters, attributes, colours,
#     the cursor -- is read back as plain values a test prints.
#
#         use Hwut::Vterm;
#         my $screen = Hwut::Vterm::Screen->new(24, 80);
#         $screen->feed("\e[1mbold\e[0m plain");
#         print $screen->line(0);              # 'bold plain'
#         print $screen->cell(0, 0)->{bold_f}; # 1
#         my ($row, $column) = $screen->cursor; # (0, 10)
#         $screen->close;
#
# WANTS, beside libvterm ('libvterm0' on Debian): the Perl module
# FFI::Platypus (Debian: 'libffi-platypus-perl'; CPAN: FFI::Platypus) --
# Perl's core has no binding to a C library, as Python's has 'ctypes'.
# Where libvterm is not found, 'Screen->new' dies with a
# Hwut::Vterm::LibraryMissing whose text says how to install it; where
# FFI::Platypus is not, loading this module dies naming it.
#
# THE CELL'S LAYOUT IS MEASURED, NOT ASSUMED, as in Python: libvterm's
# 'VTermScreenCell' changed between versions ('strike' 0x40 in 0.1, 0x80 from
# 0.2 on), so once per library a scratch terminal is fed one attribute at a
# time and the bit that changed is where that attribute stands.
#
# TWO CLASSES:
#     Hwut::Vterm::Screen     the grid alone: bytes in, cells out.
#     Hwut::Vterm::Terminal   a Screen an APPLICATION RUNS IN, on a
#                             pseudo-terminal; keys in as a keyboard sends
#                             them; observation by callback, raw ('on_event')
#                             or by named region ('on_change').
#
# A FAULT DIES WITH A Hwut::Vterm::Error whose 'kind' is Python's exception
# name -- 'IndexError', 'KeyError', 'TimeoutError', 'RuntimeError',
# 'LibraryMissing' -- and whose 'message' is Python's text.
#______________________________________________________________________________
package Hwut::Vterm;
use strict;
use warnings;
use FFI::Platypus 2.00;
use FFI::Platypus::Buffer qw(scalar_to_buffer buffer_to_scalar);
use POSIX ();

our $LIBRARY_VARIABLE = "HWUT_LIBVTERM";
my $CHARS_PER_CELL_N  = 6;
my $CHARS_BYTE_N      = 4 * $CHARS_PER_CELL_N;
my $CELL_BYTE_N       = 128;

#  THE ATTRIBUTES A CELL IS ASKED FOR, each with the SGR code that sets it --
#  in this order, the order 'attribute_text' names them in.
our @ATTRIBUTE_SGR = ([bold => "1"], [italic => "3"], [underline => "4"], [blink => "5"],
                      [reverse => "7"], [conceal => "8"], [strike => "9"]);

our $INSTALL_HINT = join("\n",
    "HINT: install the library, or name its file:",
    "    Debian, Ubuntu   apt install libvterm0",
    "    Fedora           dnf install libvterm",
    "    Arch             pacman -S libvterm",
    "    macOS            brew install libvterm",
    "    elsewhere        export $LIBRARY_VARIABLE=<path>/libvterm.so",
    "    or work inside   hwut.dev.podman.enter   (the image holds it)");

my $DAMAGE_MERGE_ROW = 1;
our %PROPERTY = (1 => ["cursor-visible", 1], 2 => ["cursor-blink", 1],
                 3 => ["alternate-screen", 1], 4 => ["title", 0], 5 => ["icon-name", 0],
                 6 => ["reverse-video", 1], 7 => ["cursor-shape", 1], 8 => ["mouse", 1],
                 9 => ["focus-report", 1]);
our %KEY = (enter => 1, tab => 2, backspace => 3, escape => 4, up => 5, down => 6,
            left => 7, right => 8, insert => 9, delete => 10, home => 11, end => 12,
            pageup => 13, pagedown => 14, map { ("f$_" => 256 + $_) } 1 .. 12);
our %MODIFIER = (shift => 1, alt => 2, ctrl => 4);

package Hwut::Vterm::Error {
    use overload '""' => sub { $_[0]{message} }, fallback => 1;
    sub throw   { my ($c, $kind, $message) = @_; die bless { kind => $kind, message => $message }, $c }
    sub kind    { $_[0]{kind} }
    sub message { $_[0]{message} }
}

package Hwut::Vterm::Pos  { use FFI::Platypus::Record; record_layout_1(int => 'row', int => 'col') }
package Hwut::Vterm::Rect { use FFI::Platypus::Record;
                            record_layout_1(int => 'start_row', int => 'end_row',
                                            int => 'start_col', int => 'end_col') }

package Hwut::Vterm;

sub _fail { Hwut::Vterm::Error->throw(@_) }

my ($FFI, %F, $LIBRARY_NAME, $LAYOUT);

sub library {
    # RETURN: FFI::Platypus, 'libvterm' loaded once and its functions bound;
    #         dies with a Hwut::Vterm::Error 'LibraryMissing' where it is not
    #         found or does not load.
    return $FFI if $FFI;
    my $name = $ENV{$LIBRARY_VARIABLE};
    if (!$name) {
        require FFI::CheckLib;
        ($name) = FFI::CheckLib::find_lib(lib => "vterm");
    }
    _fail("LibraryMissing", "libvterm is not installed, and '$LIBRARY_VARIABLE' names no file\n$INSTALL_HINT")
        unless $name;
    require DynaLoader;
    my $handle = DynaLoader::dl_load_file($name, 0);
    unless ($handle) {
        #  THE SYSTEM'S WORDS end in a NUL byte: cut, with trailing blanks.
        (my $why = DynaLoader::dl_error() // "unknown") =~ s/[\0\s]+$//;
        _fail("LibraryMissing", "libvterm cannot be loaded from '$name' -- $why\n$INSTALL_HINT");
    }
    my $ffi = FFI::Platypus->new(api => 2, lib => [$name]);
    $ffi->type('record(Hwut::Vterm::Pos)'  => 'vterm_pos');
    $ffi->type('record(Hwut::Vterm::Rect)' => 'vterm_rect');
    $ffi->type('(opaque, size_t, opaque)->void'              => 'vterm_output_f');
    $ffi->type('(vterm_rect, opaque)->int'                   => 'vterm_damage_f');
    $ffi->type('(vterm_pos, vterm_pos, int, opaque)->int'    => 'vterm_cursor_f');
    $ffi->type('(int, opaque, opaque)->int'                  => 'vterm_property_f');
    $ffi->type('(opaque)->int'                               => 'vterm_bell_f');
    for my $declared (
        [vterm_new                     => ['int', 'int']                  => 'opaque'],
        [vterm_free                    => ['opaque']                      => 'void'],
        [vterm_set_utf8                => ['opaque', 'int']               => 'void'],
        [vterm_input_write             => ['opaque', 'opaque', 'size_t']  => 'size_t'],
        [vterm_obtain_screen           => ['opaque']                      => 'opaque'],
        [vterm_obtain_state            => ['opaque']                      => 'opaque'],
        [vterm_screen_reset            => ['opaque', 'int']               => 'void'],
        [vterm_screen_enable_altscreen => ['opaque', 'int']               => 'void'],
        [vterm_screen_get_cell         => ['opaque', 'vterm_pos', 'opaque'] => 'int'],
        [vterm_state_get_cursorpos     => ['opaque', 'opaque']            => 'void'],
        [vterm_output_set_callback     => ['opaque', 'vterm_output_f', 'opaque'] => 'void'],
        [vterm_keyboard_unichar        => ['opaque', 'uint32', 'int']     => 'void'],
        [vterm_keyboard_key            => ['opaque', 'int', 'int']        => 'void'],
        [vterm_screen_set_callbacks    => ['opaque', 'opaque', 'opaque']  => 'void'],
        [vterm_screen_set_damage_merge => ['opaque', 'int']               => 'void'],
        [vterm_screen_flush_damage     => ['opaque']                      => 'void'],
    ) {
        $F{$declared->[0]} = $ffi->function(@$declared);
    }
    #  ONLY 0.2 AND LATER hold an indexed colour that must be resolved.
    $F{convert} = $ffi->find_symbol("vterm_screen_convert_color_to_rgb")
                ? $ffi->function(vterm_screen_convert_color_to_rgb => ['opaque', 'opaque'] => 'void')
                : undef;
    ($FFI, $LIBRARY_NAME) = ($ffi, $name);
    return $FFI;
}

sub detection_text {
    # RETURN: string, 'libvterm found: <name>' where the library loads; the
    #         text of LibraryMissing -- what is wrong, how to install it -- else.
    my $ok = eval { library(); 1 };
    return "libvterm found: $LIBRARY_NAME" if $ok;
    return "$@";
}

sub reset_library {
    # RETURN: nothing. The library is looked for anew at the next Screen --
    #         after '$ENV{HWUT_LIBVTERM}' was changed (Python: '_library = None').
    ($FFI, $LIBRARY_NAME, $LAYOUT) = (undef, undef, undef);
    %F = ();
}

sub _f { $F{$_[0]} }


#  ------------------------------------------------------------------- Cell
package Hwut::Vterm::Cell {
    sub new { my ($c, %a) = @_; bless { text => "", width => 1, foreground => undef,
                                        background => undef, %a }, $c }
    sub attribute_text {
        # RETURN: string, the attributes that are set, by name in one fixed
        #         order, separated by blanks; '' where none is.
        my ($self) = @_;
        return join(" ", map { $_->[0] } grep { $self->{"$_->[0]_f"} } @Hwut::Vterm::ATTRIBUTE_SGR);
    }
}

#  ----------------------------------------------------------------- Screen
package Hwut::Vterm::Screen;
use FFI::Platypus::Buffer qw(scalar_to_buffer buffer_to_scalar);

sub new {
    # RETURN: Hwut::Vterm::Screen of 'row_n' rows and 'column_n' columns,
    #         blank, the cursor at (0, 0); dies 'LibraryMissing' where
    #         libvterm is not found.
    my ($class, $row_n, $column_n) = @_;
    $row_n //= 24; $column_n //= 80;
    Hwut::Vterm::library();
    my $terminal = Hwut::Vterm::_f("vterm_new")->($row_n, $column_n);
    Hwut::Vterm::_f("vterm_set_utf8")->($terminal, 1);
    my $self = bless { row_n => $row_n, column_n => $column_n, terminal => $terminal,
                       screen => Hwut::Vterm::_f("vterm_obtain_screen")->($terminal),
                       state  => Hwut::Vterm::_f("vterm_obtain_state")->($terminal) }, $class;
    #  THE ALTERNATE SCREEN IS OFF IN libvterm UNTIL ASKED FOR.
    Hwut::Vterm::_f("vterm_screen_enable_altscreen")->($self->{screen}, 1);
    Hwut::Vterm::_f("vterm_screen_reset")->($self->{screen}, 1);
    return $self;
}

sub row_n    { $_[0]{row_n} }
sub column_n { $_[0]{column_n} }

sub close {
    # RETURN: nothing. The terminal's memory is freed; a second call does
    #         nothing.
    my ($self) = @_;
    return unless defined $self->{terminal};
    Hwut::Vterm::_f("vterm_free")->($self->{terminal});
    @$self{qw(terminal screen state)} = (undef, undef, undef);
}

sub DESTROY {
    # RETURN: nothing. A screen not closed is closed when it goes -- not at
    #         global destruction, where the library may be gone before it.
    my ($self) = @_;
    $self->close unless ${^GLOBAL_PHASE} eq "DESTRUCT";
}

sub feed {
    # RETURN: integer, the number of bytes the terminal took. 'data' is what a
    #         program wrote: bytes, or a character string sent as UTF-8.
    my ($self, $data) = @_;
    utf8::encode($data) if utf8::is_utf8($data);
    my ($pointer, $size) = scalar_to_buffer($data);
    return Hwut::Vterm::_f("vterm_input_write")->($self->{terminal}, $pointer, $size);
}

sub cursor {
    # RETURN: (row, column), the cursor's place, counted from 0.
    my ($self) = @_;
    my $buffer = "\0" x 8;
    my ($pointer) = scalar_to_buffer($buffer);
    Hwut::Vterm::_f("vterm_state_get_cursorpos")->($self->{state}, $pointer);
    return unpack("l l", $buffer);
}

sub _raw {
    # RETURN: string, the library's own cell at that place, its colours
    #         resolved to red, green, blue where the library keeps them
    #         otherwise.
    my ($self, $row, $column) = @_;
    my $buffer = "\0" x $CELL_BYTE_N;
    my ($pointer) = scalar_to_buffer($buffer);
    Hwut::Vterm::_f("vterm_screen_get_cell")->($self->{screen},
                                               Hwut::Vterm::Pos->new(row => $row, col => $column), $pointer);
    if ($LAYOUT && $LAYOUT->{convert_f}) {
        #  THE COLOUR'S STRUCTURE begins one byte before its red.
        Hwut::Vterm::_f("convert")->($self->{screen}, $pointer + $_ - 1)
            for $LAYOUT->{foreground_i}, $LAYOUT->{background_i};
    }
    return $buffer;
}

sub cell {
    # RETURN: Hwut::Vterm::Cell, what stands at that place; dies 'IndexError'
    #         where the place is not on the screen.
    my ($self, $row, $column) = @_;
    Hwut::Vterm::_fail("IndexError", sprintf("(%d, %d) is not on a screen of %d x %d",
                                             $row, $column, $self->{row_n}, $self->{column_n}))
        unless 0 <= $row && $row < $self->{row_n} && 0 <= $column && $column < $self->{column_n};
    my $layout = Hwut::Vterm::_measured();
    my $raw    = $self->_raw($row, $column);
    my $text   = join "", map { chr } grep { $_ != 0 && $_ != 0xFFFFFFFF }
                              unpack("V$CHARS_PER_CELL_N", $raw);
    my $colour = sub {
        my ($i, $default) = @_;
        my @rgb = unpack("C3", substr($raw, $i, 3));
        return "@rgb" eq "@$default" ? undef : \@rgb;
    };
    my %flag = map { my ($offset, $mask) = @{$layout->{mask}{$_->[0]}};
                     ("$_->[0]_f" => (ord(substr($raw, $offset, 1)) & $mask) ? 1 : 0) }
               @ATTRIBUTE_SGR;
    return Hwut::Vterm::Cell->new(
        text       => $text,
        width      => ord(substr($raw, $CHARS_BYTE_N, 1)) || 1,
        foreground => $colour->($layout->{foreground_i}, $layout->{default_fg}),
        background => $colour->($layout->{background_i}, $layout->{default_bg}),
        %flag);
}

sub line {
    # RETURN: string, the row's characters, blanks at its end dropped; a cell
    #         nothing was written to reads as a blank.
    my ($self, $row) = @_;
    my ($text, $column) = ("", 0);
    while ($column < $self->{column_n}) {
        my $cell = $self->cell($row, $column);
        $text   .= $cell->{text} eq "" ? " " : $cell->{text};
        $column += $cell->{width} > 1 ? $cell->{width} : 1;
    }
    $text =~ s/\s+$//;
    return $text;
}

sub line_list {
    # RETURN: list of strings, every row as 'line' gives it, top first.
    my ($self) = @_;
    return map { $self->line($_) } 0 .. $self->{row_n} - 1;
}


#  --------------------------------------------------------------- Terminal
package Hwut::Vterm::Terminal;
our @ISA = ("Hwut::Vterm::Screen");
use FFI::Platypus::Buffer qw(scalar_to_buffer buffer_to_scalar);
use POSIX qw(:sys_wait_h);
use Time::HiRes qw(time);

sub new {
    # RETURN: Hwut::Vterm::Terminal, blank, nothing running in it. 'settle_s'
    #         is how long the application must write nothing before its
    #         screen is taken as drawn.
    my ($class, $row_n, $column_n, %arg) = @_;
    my $self = Hwut::Vterm::Screen::new($class, $row_n, $column_n);
    @$self{qw(settle_s event_f change_f region region_order told answer master pid ended_f status)}
        = ($arg{settle_s} // 0.1, [], [], {}, [], {}, "", undef, undef, 0, undef);
    my $ffi = Hwut::Vterm::library();
    #  THE CLOSURES LIVE AS LONG AS THE TERMINAL: libvterm keeps their
    #  addresses, Perl must keep them.
    $self->{closure} = [
        $ffi->closure(sub { my ($data, $length) = @_; $self->{answer} .= buffer_to_scalar($data, $length) }),
        $ffi->closure(sub { my ($r) = @_;
                            $self->_emit(Hwut::Vterm::Event->new(kind => "damage", row => $r->start_row,
                                column => $r->start_col, row_end => $r->end_row, column_end => $r->end_col)) }),
        $ffi->closure(sub { my ($p, undef, $visible) = @_;
                            $self->_emit(Hwut::Vterm::Event->new(kind => "cursor", row => $p->row,
                                column => $p->col, value => $visible ? 1 : 0)) }),
        $ffi->closure(sub { my ($number, $value) = @_;
                            my ($name, $plain_f) = @{$PROPERTY{$number} // ["property-$number", 0]};
                            my $read = $plain_f ? unpack("l", buffer_to_scalar($value, 4)) : undef;
                            $self->_emit(Hwut::Vterm::Event->new(kind => "property", name => $name,
                                                                 value => $read)) }),
        $ffi->closure(sub { $self->_emit(Hwut::Vterm::Event->new(kind => "bell")) }),
    ];
    my @c = @{$self->{closure}};
    Hwut::Vterm::_f("vterm_output_set_callback")->($self->{terminal}, $c[0], undef);
    #  'VTermScreenCallbacks': damage, moverect (none), movecursor,
    #  settermprop, bell, then nulls -- resize, the scrollback pair, and spare
    #  slots for what later versions append.
    $self->{callback_table} = pack("Q*", $ffi->cast(vterm_damage_f => 'opaque', $c[1]), 0,
                                         $ffi->cast(vterm_cursor_f => 'opaque', $c[2]),
                                         $ffi->cast(vterm_property_f => 'opaque', $c[3]),
                                         $ffi->cast(vterm_bell_f => 'opaque', $c[4]), (0) x 11);
    my ($table) = scalar_to_buffer($self->{callback_table});
    Hwut::Vterm::_f("vterm_screen_set_callbacks")->($self->{screen}, $table, undef);
    Hwut::Vterm::_f("vterm_screen_set_damage_merge")->($self->{screen}, $DAMAGE_MERGE_ROW);
    return $self;
}

#  ------------------------------------------------------------ observation
sub on_event  { my ($self, $f) = @_; push @{$self->{event_f}}, $f }
sub on_change { my ($self, $f) = @_; push @{$self->{change_f}}, $f }

sub region {
    # RETURN: nothing. The rectangle 'name' is observed from now on: 'row_n'
    #         rows from 'row' (negative counts from the bottom), 'column_n'
    #         columns from 'column' (to the right edge where undef).
    my ($self, $name, %arg) = @_;
    my $row = $arg{row} // 0;
    $row += $self->{row_n} if $row < 0;
    my $column   = $arg{column} // 0;
    my $column_n = $arg{column_n} // $self->{column_n} - $column;
    push @{$self->{region_order}}, $name unless exists $self->{region}{$name};
    $self->{region}{$name} = [$row, $arg{row_n} // 1, $column, $column_n];
    #  WHAT STANDS THERE NOW IS KNOWN, not news: only a change is told.
    $self->{told}{$name} = [$self->region_text($name)];
}

sub region_text {
    # RETURN: list of strings, the region's rows as they stand now, blanks at
    #         each row's end dropped; dies 'KeyError' where no such region was
    #         declared.
    my ($self, $name) = @_;
    my $r = $self->{region}{$name}
        or Hwut::Vterm::_fail("KeyError", Hwut::PyText::str_repr($name));
    my ($row, $row_n, $column, $column_n) = @$r;
    my @result;
    for my $each ($row .. $row + $row_n - 1) {
        my ($text, $at) = ("", $column);
        while ($at < $column + $column_n) {
            my $cell = $self->cell($each, $at);
            $text .= $cell->{text} eq "" ? " " : $cell->{text};
            $at   += $cell->{width} > 1 ? $cell->{width} : 1;
        }
        $text =~ s/\s+$//;
        push @result, $text;
    }
    return @result;
}

sub report {
    # RETURN: list of strings, the names of the regions whose text differs
    #         from what was last told -- each told to every 'on_change'
    #         callback, in the order of declaration.
    my ($self) = @_;
    my @changed;
    for my $name (@{$self->{region_order}}) {
        my @line = $self->region_text($name);
        next if join("\n", @line) eq join("\n", @{$self->{told}{$name} // []})
             && @line == @{$self->{told}{$name} // []};
        $self->{told}{$name} = \@line;
        push @changed, $name;
        $_->($name, [@line]) for @{$self->{change_f}};
    }
    return @changed;
}

sub _emit {
    my ($self, $event) = @_;
    $_->($event) for @{$self->{event_f}};
    return 1;
}

#  ------------------------------------------------------ bytes in and out
sub feed {
    # RETURN: integer, the bytes the terminal took. The raw events fire before
    #         this returns; what the terminal answered goes to the application,
    #         where one runs.
    my ($self, $data) = @_;
    my $taken_n = $self->SUPER::feed($data);
    Hwut::Vterm::_f("vterm_screen_flush_damage")->($self->{screen});
    $self->_forward;
    return $taken_n;
}

sub answer {
    # RETURN: string of bytes, what the terminal said since the last call and
    #         no application took.
    my ($self) = @_;
    my $data = $self->{answer};
    $self->{answer} = "";
    return $data;
}

sub _forward {
    my ($self) = @_;
    return if !defined $self->{master} || $self->{answer} eq "";
    $self->{ended_f} = 1 unless defined syswrite($self->{master}, $self->{answer});
    $self->{answer} = "";
}

sub send {
    # RETURN: 1 where the application still runs after it, 0 else. 'text' is
    #         typed character by character, as a keyboard sends it; then the
    #         screen is given 'react_s' to begin answering and read until quiet.
    my ($self, $text, $react_s) = @_;
    Hwut::Vterm::_f("vterm_keyboard_unichar")->($self->{terminal}, ord($_), 0) for split //, $text;
    $self->_forward;
    return $self->pump($react_s // 1.0);
}

sub press {
    # RETURN: 1 where the application still runs after it, 0 else; dies
    #         'KeyError' where 'key' or a modifier has no name here. 'key' is a
    #         name ('enter', 'up', 'f5', ...) or one character; the modifiers
    #         'shift', 'alt', 'ctrl' follow. The last argument may be
    #         { react_s => seconds }.
    my ($self, $key, @modifier) = @_;
    my $react_s = (@modifier && ref $modifier[-1] eq "HASH") ? (pop @modifier)->{react_s} : 1.0;
    my $mod = 0;
    for (@modifier) {
        exists $MODIFIER{$_} or Hwut::Vterm::_fail("KeyError", Hwut::PyText::str_repr($_));
        $mod |= $MODIFIER{$_};
    }
    if (length $key == 1) { Hwut::Vterm::_f("vterm_keyboard_unichar")->($self->{terminal}, ord $key, $mod) }
    else {
        exists $KEY{$key} or Hwut::Vterm::_fail("KeyError", Hwut::PyText::str_repr($key));
        Hwut::Vterm::_f("vterm_keyboard_key")->($self->{terminal}, $KEY{$key}, $mod);
    }
    $self->_forward;
    return $self->pump($react_s);
}

#  -------------------------------------------------------- the application
my $OPENPTY;

sub _openpty {
    # RETURN: (master, slave) file handles of a fresh pseudo-terminal.
    unless ($OPENPTY) {
        my $libc = FFI::Platypus->new(api => 2, lib => [undef]);
        $OPENPTY = $libc->function(openpty => ['int*', 'int*', 'opaque', 'opaque', 'opaque'] => 'int');
    }
    my ($master_fd, $slave_fd) = (0, 0);
    $OPENPTY->(\$master_fd, \$slave_fd, undef, undef, undef) == 0
        or Hwut::Vterm::_fail("RuntimeError", "openpty: $!");
    open(my $master, "+<&=", $master_fd) or Hwut::Vterm::_fail("RuntimeError", "master: $!");
    open(my $slave,  "+<&=", $slave_fd)  or Hwut::Vterm::_fail("RuntimeError", "slave: $!");
    return ($master, $slave);
}

sub run {
    # RETURN: 1 where the application still runs once its first screen stands,
    #         0 else; dies 'RuntimeError' where one already runs here. 'argv'
    #         is started on a pseudo-terminal of this terminal's size: its
    #         three streams are that terminal, it is its controlling one, TERM
    #         is 'xterm-256color', LINES and COLUMNS are taken out of its
    #         environment.
    my ($self, $argv, %arg) = @_;
    Hwut::Vterm::_fail("RuntimeError", "an application already runs in this terminal")
        if defined $self->{pid};
    require "sys/ioctl.ph";
    my ($master, $slave) = _openpty();
    ioctl($slave, TIOCSWINSZ(), pack("S4", $self->{row_n}, $self->{column_n}, 0, 0))
        or Hwut::Vterm::_fail("RuntimeError", "TIOCSWINSZ: $!");
    my %environment = %{$arg{env} // \%ENV};
    $environment{TERM} = "xterm-256color";
    delete @environment{qw(LINES COLUMNS)};
    my $pid = fork;
    Hwut::Vterm::_fail("RuntimeError", "fork: $!") unless defined $pid;
    if ($pid == 0) {
        close $master;
        POSIX::setsid();
        open(STDIN, "<&", $slave); open(STDOUT, ">&", $slave); open(STDERR, ">&", $slave);
        ioctl(STDIN, TIOCSCTTY(), 0);
        close $slave;
        chdir $arg{cwd} if defined $arg{cwd};
        %ENV = %environment;
        { no warnings "exec"; exec { $argv->[0] } @$argv }
        POSIX::_exit(127);
    }
    close $slave;
    @$self{qw(master pid ended_f status)} = ($master, $pid, 0, undef);
    return $self->pump($arg{start_s} // 10.0);
}

sub _running_f {
    # RETURN: 1 where the application has not ended; its status is kept once
    #         it has.
    my ($self) = @_;
    return 0 unless defined $self->{pid};
    return 0 if defined $self->{status};
    my $pid = waitpid($self->{pid}, WNOHANG);
    return 1 if $pid == 0;
    $self->{status} = WIFEXITED($?) ? WEXITSTATUS($?) : -WTERMSIG($?);
    return 0;
}

sub pump {
    # RETURN: 1 where the application still runs, 0 else. READ UNTIL QUIET:
    #         up to 'first_s' for the application to write at all, then on
    #         until it wrote nothing for 'settle_s'; then the changed regions
    #         are reported.
    my ($self, $first_s) = @_;
    my $wait_s = $first_s // 1.0;
    while (defined $self->{master} && !$self->{ended_f}) {
        my $in = "";
        vec($in, fileno($self->{master}), 1) = 1;
        last unless select(my $ready = $in, undef, undef, $wait_s) > 0;
        my $n = sysread($self->{master}, my $data, 65536);
        if (!$n) { $self->{ended_f} = 1; last }       # EIO: the last writer closed
        $self->feed($data);
        $wait_s = $self->{settle_s};
    }
    $self->report;
    return ($self->_running_f && !$self->{ended_f}) ? 1 : 0;
}

sub expect {
    # RETURN: (row, column) where 'text' stands on the screen, once it does;
    #         dies 'TimeoutError', carrying the screen, where it does not within
    #         'timeout_s'.
    my ($self, $text, $timeout_s) = @_;
    my $deadline = time + ($timeout_s // 10.0);
    while (1) {
        my @line = $self->line_list;
        for my $row (0 .. $#line) {
            my $at = index($line[$row], $text);
            return ($row, $at) if $at >= 0;
        }
        Hwut::Vterm::_fail("TimeoutError", "'$text' did not appear; the screen:\n" . join("\n", @line))
            if time >= $deadline || $self->{ended_f} || !defined $self->{master};
        $self->pump($self->{settle_s});
    }
}

sub wait {
    # RETURN: integer, the application's exit status once it has ended and its
    #         last words are on the screen; undef where none was run; dies
    #         'TimeoutError' where it still runs after 'timeout_s' -- killed
    #         first.
    my ($self, $timeout_s) = @_;
    return undef unless defined $self->{pid};
    my $deadline = time + ($timeout_s // 10.0);
    while ($self->pump($self->{settle_s})) {
        if (time >= $deadline) {
            $self->_kill;
            Hwut::Vterm::_fail("TimeoutError", sprintf("the application still ran after %.1f s",
                                                       $timeout_s // 10.0));
        }
    }
    while (!defined $self->{status}) {
        last unless $self->_running_f;
        if (time >= $deadline) {
            $self->_kill;
            Hwut::Vterm::_fail("TimeoutError", "the application closed its terminal and did not end");
        }
        select(undef, undef, undef, 0.01);
    }
    return $self->{status};
}

sub _kill {
    my ($self) = @_;
    return unless defined $self->{pid} && !defined $self->{status};
    kill "KILL", $self->{pid};
    waitpid($self->{pid}, 0);
    $self->{status} = WIFEXITED($?) ? WEXITSTATUS($?) : -WTERMSIG($?);
}

sub close {
    # RETURN: nothing. An application still running is killed, the
    #         pseudo-terminal closed, the terminal's memory freed.
    my ($self) = @_;
    $self->_kill if $self->_running_f;
    if (defined $self->{master}) { CORE::close($self->{master}); $self->{master} = undef }
    $self->SUPER::close;
}


#  ------------------------------------------------------------------ Event
package Hwut::Vterm::Event;
use overload '""' => \&text, fallback => 1;

sub new { my ($c, %a) = @_; bless {%a}, $c }

sub text {
    # RETURN: string, the event on one line, as a test prints it.
    my ($self) = @_;
    my $kind = $self->{kind};
    return sprintf("damage    rows %d..%d  columns %d..%d", @$self{qw(row row_end column column_end)})
        if $kind eq "damage";
    return sprintf("cursor    (%d, %d)%s", $self->{row}, $self->{column}, $self->{value} ? "" : "  hidden")
        if $kind eq "cursor";
    return sprintf("property  %s = %s", $self->{name}, $self->{value} // "None")
        if $kind eq "property";
    return $kind;
}


#  ------------------------------------------------------------- the layout
package Hwut::Vterm;

sub _measured {
    # RETURN: hash ref, where this library's cell keeps each attribute and each
    #         colour -- measured once on a scratch terminal, then remembered.
    return $LAYOUT if $LAYOUT;
    my $cell_after = sub {
        my ($sequence) = @_;
        my $scratch = Hwut::Vterm::Screen->new(2, 4);
        $scratch->feed($sequence ne "" ? "\e[${sequence}m" : "");
        $scratch->feed("X");
        my $raw = $scratch->_raw(0, 0);
        $scratch->close;
        return $raw;
    };
    my $plain = $cell_after->("");
    my $changed = sub {
        my ($raw) = @_;
        my @found;
        for my $i ($CHARS_BYTE_N + 1 .. $CELL_BYTE_N - 1) {
            my ($a, $b) = (ord substr($plain, $i, 1), ord substr($raw, $i, 1));
            push @found, [$i, $a ^ $b] if $a != $b;
        }
        return @found;
    };
    my %mask;
    for my $pair (@ATTRIBUTE_SGR) {
        my ($found) = $changed->($cell_after->($pair->[1]));
        $mask{$pair->[0]} = $found // [$CHARS_BYTE_N + 1, 0];
    }
    #  UNDERLINE IS A NUMBER OF TWO BITS: any of them is 'underlined'.
    for my $found ($changed->($cell_after->("21"))) {
        $mask{underline}[1] |= $found->[1] if $found->[0] == $mask{underline}[0];
    }
    my $colour_at = sub {
        my ($code) = @_;
        return index($cell_after->("$code;2;1;2;3"), "\x01\x02\x03", $CHARS_BYTE_N + 1);
    };
    my %layout = (mask => \%mask, foreground_i => $colour_at->("38"),
                  background_i => $colour_at->("48"), convert_f => $F{convert} ? 1 : 0,
                  default_fg => [], default_bg => []);
    $LAYOUT = \%layout;
    my $scratch = Hwut::Vterm::Screen->new(2, 4);
    $scratch->feed("X");
    my $raw = $scratch->_raw(0, 0);
    $scratch->close;
    $layout{default_fg} = [unpack("C3", substr($raw, $layout{foreground_i}, 3))];
    $layout{default_bg} = [unpack("C3", substr($raw, $layout{background_i}, 3))];
    return $LAYOUT;
}

require Hwut::PyText;

1;
