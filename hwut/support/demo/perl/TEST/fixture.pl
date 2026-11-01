#! /usr/bin/env perl
#______________________________________________________________________________
#
# THE SHOP'S FIXTURE -- no test, a helper the directory's 'hwut.conf' calls.
#
#     fixture.pl open            a fresh 'TMP/shop.db', stocked as below, and
#                                an empty 'TMP/frame.log' ('on_entry', and
#                                'hwut.execute fixture open')
#     fixture.pl close           both removed ('on_exit')
#     fixture.pl check <when> <app> [<choice>]
#                                'when' is 'before' or 'after': whether the
#                                stock adds up around the test run '<app>
#                                <choice>', appended to 'TMP/frame.log'
#                                ('on_before_test', 'on_after_test')
#
# 'hwut.conf' passes '<app>' and '<choice>' as '$HWUT_TEST $HWUT_CHOICE',
# which hwut sets for the run the check stands around; a test without
# choices has none. 'check' concerns the shop's tests alone. The stock
# ADDS UP where every item's quantity is its opening quantity plus every
# movement of the journal.
#______________________________________________________________________________
use strict;
use warnings;
use FindBin;
use lib $FindBin::Bin;
use File::Path qw(make_path);
use ShopDb;

my $HERE     = $FindBin::Bin;
my $DB_PATH  = "$HERE/TMP/shop.db";
my $LOG_PATH = "$HERE/TMP/frame.log";
my @OPENING  = (["apple", 10], ["pear", 5], ["plum", 5]);
my %SHOP_TEST = map { $_ => 1 } ("delivery.json", "shop.pl");


sub open_shop {
    # RETURN: nothing. Writes a fresh, stocked database and an empty log.
    make_path("$HERE/TMP");
    -e $_ and unlink $_ for $DB_PATH, $LOG_PATH;
    my $db = ShopDb->connect($DB_PATH);
    $db->execute("CREATE TABLE opening (item TEXT PRIMARY KEY, qty INTEGER)");
    $db->execute("CREATE TABLE stock   (item TEXT PRIMARY KEY, qty INTEGER)");
    $db->execute("CREATE TABLE journal (item TEXT, delta INTEGER, source TEXT)");
    for my $pair (@OPENING) {
        $db->execute("INSERT INTO opening VALUES (?, ?)", @$pair);
        $db->execute("INSERT INTO stock   VALUES (?, ?)", @$pair);
    }
    $db->close;
    open(my $fh, ">", $LOG_PATH) or die "fixture.pl: $LOG_PATH: $!\n";
    close $fh;
}


sub close_shop {
    # RETURN: nothing. Removes the database and the log.
    -e $_ and unlink $_ for $DB_PATH, $LOG_PATH;
}


sub adds_up {
    # RETURN: 1, if every item's stock is its opening quantity plus its
    #            journal's movements;
    #         0, else.
    my $db = ShopDb->connect($DB_PATH, timeout_s => 10);
    my @row = $db->rows(
        "SELECT o.item, o.qty + COALESCE(SUM(j.delta), 0), s.qty"
      . "  FROM opening o JOIN stock s ON s.item = o.item"
      . "  LEFT JOIN journal j ON j.item = o.item GROUP BY o.item");
    $db->close;
    return (grep { $_->[1] != $_->[2] } @row) ? 0 : 1;
}


sub check {
    # RETURN: nothing. Appends one line to the log for a shop test run.
    my ($when, $test, $choice) = @_;
    return unless defined $test && $SHOP_TEST{$test};
    (my $run = "$test " . ($choice // "")) =~ s/\s+$//;
    open(my $fh, ">>", $LOG_PATH) or die "fixture.pl: $LOG_PATH: $!\n";
    printf $fh "%-6s %-15s %s\n", $when, $run, adds_up() ? "stock adds up" : "STOCK BROKEN";
    close $fh;
}


my $command = $ARGV[0] // "";
if    ($command eq "open")  { open_shop() }
elsif ($command eq "close") { close_shop() }
elsif ($command eq "check") { check(@ARGV[1 .. 3]) }
else {
    print STDERR "usage: fixture.pl open | close | check before|after <app> <choice>\n";
    exit 2;
}
