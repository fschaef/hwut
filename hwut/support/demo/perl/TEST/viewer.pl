#! /usr/bin/env perl
#______________________________________________________________________________
#
# A TERMINAL FILE VIEWER -- the program 'screen.pl' tests; no test itself.
#
#     viewer.pl <file>
#
# Full screen, on the terminal's alternate screen: a title bar (reverse
# video), as many lines of the file as fit, and a status line: the keys
# flush left, the lines shown flush right. Keys: 'j' or down one line
# further, 'k' or up one line back, 'q' quits.
#______________________________________________________________________________
use strict;
use warnings;
use POSIX qw(:termios_h);
use File::Basename qw(basename);


sub terminal_size {
    # RETURN: (column_n, row_n), the size of the terminal on stdout; dies
    #         where stdout is no terminal.
    require "sys/ioctl.ph";
    my $size = "\0" x 8;
    ioctl(STDOUT, TIOCGWINSZ(), $size) or die "viewer.pl: stdout is no terminal: $!\n";
    my ($row_n, $column_n) = unpack("S2", $size);
    return ($column_n, $row_n);
}


sub draw {
    # RETURN: nothing. Draws the whole screen with the file's line 'top'
    #         first.
    my ($name, $line_list, $top, $row_n, $column_n) = @_;
    my $body_n = $row_n - 2;
    my $last   = $top + $body_n - 1 < $#$line_list ? $top + $body_n - 1 : $#$line_list;
    my @shown  = @$line_list[$top .. $last];
    my $out    = "\e[H\e[2J";
    $out .= "\e[7m" . substr(sprintf("%-*s", $column_n, " $name"), 0, $column_n) . "\e[0m\r\n";
    $out .= substr($_, 0, $column_n) . "\r\n" for @shown;
    $out .= "\r\n" x ($body_n - @shown);
    my $where = sprintf("lines %d-%d of %d", $top + 1, $top + @shown, scalar @$line_list);
    my $keys  = "j k q";
    $out .= sprintf("\e[%d;1H%s%*s", $row_n, $keys, $column_n - 1 - length $keys, $where);
    syswrite(STDOUT, $out);
}


sub main {
    # RETURN: integer, 0 once 'q' was pressed.
    my ($path) = @_;
    open(my $fh, "<", $path) or die "viewer.pl: $path: $!\n";
    my @line = map { s/\r?\n$//r } <$fh>;
    close $fh;
    my ($column_n, $row_n) = terminal_size();
    #  RAW, as Python's 'tty.setraw': no echo, no line discipline, no signal
    #  keys, no output processing -- the viewer writes '\r\n' itself.
    my $fd    = fileno(STDIN);
    my $saved = POSIX::Termios->new;  $saved->getattr($fd);
    my $raw   = POSIX::Termios->new;  $raw->getattr($fd);
    $raw->setiflag($raw->getiflag & ~(BRKINT | ICRNL | INPCK | ISTRIP | IXON));
    $raw->setoflag($raw->getoflag & ~OPOST);
    $raw->setcflag(($raw->getcflag & ~(CSIZE | PARENB)) | CS8);
    $raw->setlflag($raw->getlflag & ~(ECHO | ICANON | IEXTEN | ISIG));
    $raw->setcc(VMIN, 1);
    $raw->setcc(VTIME, 0);
    $raw->setattr($fd, TCSAFLUSH);
    syswrite(STDOUT, "\e[?1049h");
    my $top    = 0;
    my $bottom = @line - ($row_n - 2) > 0 ? @line - ($row_n - 2) : 0;
    while (1) {
        draw(basename($path), \@line, $top, $row_n, $column_n);
        my $n = sysread(STDIN, my $key, 8);
        last if !$n || $key eq "q";
        if    ($key eq "j" || $key eq "\e[B") { $top = $top + 1 < $bottom ? $top + 1 : $bottom }
        elsif ($key eq "k" || $key eq "\e[A") { $top = $top > 0 ? $top - 1 : 0 }
    }
    syswrite(STDOUT, "\e[?1049l");
    $saved->setattr($fd, TCSADRAIN);
    return 0;
}


exit main($ARGV[0]);
