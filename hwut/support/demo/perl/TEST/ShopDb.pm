# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# PURPOSE: THE SHOP'S DATABASE, for 'shop.pl' and 'fixture.pl' -- no test, a
#          helper. SQLite through FFI::Platypus straight to 'libsqlite3':
#          Perl's core has no SQLite, as Python's has 'sqlite3', and DBI with
#          DBD::SQLite is not given where FFI::Platypus is (the Perl support's
#          'Hwut::Vterm' wants it already).
#
#     my $db = ShopDb->connect($path, timeout_s => 10, trace => sub { ... });
#     $db->execute("UPDATE stock SET qty = qty + ? WHERE item = ?", 1, "pear");
#     my @row = $db->rows("SELECT item, qty FROM stock");   # array refs
#     $db->close;
#
# Statements run in autocommit, as Python's 'isolation_level=None': a
# transaction is the caller's 'BEGIN IMMEDIATE' ... 'COMMIT'. A fault dies
# with SQLite's own message ('database is locked', ...).
#______________________________________________________________________________
package ShopDb;
use strict;
use warnings;
use FFI::Platypus 2.00;

my $SQLITE_ROW  = 100;
my $SQLITE_DONE = 101;
my %F;

sub _library {
    # RETURN: nothing, once the functions of 'libsqlite3' are bound; dies
    #         naming the library where it is not found.
    return if %F;
    my $ffi = FFI::Platypus->new(api => 2);
    $ffi->lib("libsqlite3.so.0");
    my %signature = (
        sqlite3_open          => [['string', 'opaque*'] => 'int'],
        sqlite3_close         => [['opaque'] => 'int'],
        sqlite3_busy_timeout  => [['opaque', 'int'] => 'int'],
        sqlite3_errmsg        => [['opaque'] => 'string'],
        sqlite3_prepare_v2    => [['opaque', 'string', 'int', 'opaque*', 'opaque'] => 'int'],
        sqlite3_bind_text     => [['opaque', 'int', 'string', 'int', 'opaque'] => 'int'],
        sqlite3_bind_int64    => [['opaque', 'int', 'sint64'] => 'int'],
        sqlite3_step          => [['opaque'] => 'int'],
        sqlite3_column_count  => [['opaque'] => 'int'],
        sqlite3_column_text   => [['opaque', 'int'] => 'string'],
        sqlite3_expanded_sql  => [['opaque'] => 'opaque'],
        sqlite3_free          => [['opaque'] => 'void'],
        sqlite3_finalize      => [['opaque'] => 'int'],
    );
    for my $name (keys %signature) {
        my $f = eval { $ffi->function($name => @{$signature{$name}}) };
        die "ShopDb: libsqlite3 is not found ('apt install libsqlite3-0'): $@" unless $f;
        $F{$name} = $f;
    }
    $F{_ffi} = $ffi;
}

sub connect {
    # RETURN: ShopDb, a connection to the database at 'path', waiting up to
    #         'timeout_s' for a lock; every statement it executes, its
    #         parameters filled in, is given to the code ref 'trace' first.
    #         Dies with SQLite's message where the file cannot be opened.
    my ($class, $path, %arg) = @_;
    _library();
    my $handle;
    my $code = $F{sqlite3_open}->($path, \$handle);
    die "ShopDb: $path: " . ($handle ? $F{sqlite3_errmsg}->($handle) : "out of memory") . "\n"
        if $code != 0;
    $F{sqlite3_busy_timeout}->($handle, int(1000 * ($arg{timeout_s} // 5)));
    return bless { handle => $handle, trace => $arg{trace} }, $class;
}

sub _run {
    # RETURN: list of array refs, every row the statement 'sql' with the
    #         parameters 'value' returned; dies with SQLite's message.
    my ($self, $sql, @value) = @_;
    my $statement;
    my $code = $F{sqlite3_prepare_v2}->($self->{handle}, $sql, -1, \$statement, undef);
    die "ShopDb: " . $F{sqlite3_errmsg}->($self->{handle}) . "\n" if $code != 0;
    for my $i (0 .. $#value) {
        #  SQLITE_TRANSIENT (-1): SQLite copies the text before the call returns.
        if ($value[$i] =~ /^-?[0-9]+$/) { $F{sqlite3_bind_int64}->($statement, $i + 1, $value[$i]) }
        else { $F{sqlite3_bind_text}->($statement, $i + 1, $value[$i], -1,
                                        $F{_ffi}->cast('sint64' => 'opaque', -1)) }
    }
    if ($self->{trace}) {
        my $expanded = $F{sqlite3_expanded_sql}->($statement);
        $self->{trace}->($F{_ffi}->cast('opaque' => 'string', $expanded));
        $F{sqlite3_free}->($expanded);
    }
    my @row;
    while (1) {
        $code = $F{sqlite3_step}->($statement);
        last if $code == $SQLITE_DONE;
        if ($code != $SQLITE_ROW) {
            my $message = $F{sqlite3_errmsg}->($self->{handle});
            $F{sqlite3_finalize}->($statement);
            die "$message\n";
        }
        push @row, [map { $F{sqlite3_column_text}->($statement, $_) }
                        0 .. $F{sqlite3_column_count}->($statement) - 1];
    }
    $F{sqlite3_finalize}->($statement);
    return @row;
}

sub execute {
    # RETURN: nothing, once the statement 'sql' with the parameters 'value'
    #         has run; dies with SQLite's message.
    my ($self, $sql, @value) = @_;
    $self->_run($sql, @value);
    return;
}

sub rows {
    # RETURN: list of array refs, one per row the query 'sql' returned, each
    #         holding the row's columns as text; dies with SQLite's message.
    my ($self, $sql, @value) = @_;
    return $self->_run($sql, @value);
}

sub close {
    # RETURN: nothing. The connection is closed.
    my ($self) = @_;
    $F{sqlite3_close}->($self->{handle}) if $self->{handle};
    $self->{handle} = undef;
}

1;
