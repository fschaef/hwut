#! /usr/bin/env perl
#
# @hwut {
#     title     = "Demo: a shop's stock -- what the directory's hwut.conf arranges"
#     tolerance { stderr_ignored = true }
#     choices {
#         sell   { features = ["unordered-table", "stderr-ignored", "collision"] }
#         report { features = ["output-file", "keyed-table-separator", "dependency",
#                              "frame-scripts", "test-scripts", "stderr-ignored"]
#                  output   = ["<stdout>", "stock.csv"] }
#     }
# }
#
#______________________________________________________________________________
#
# SUBJECT  the stock of a small shop, kept in an SQLite database: a delivery
#          comes in, three clerks sell at once, and the stock is reported.
# REQUIREMENT  Every movement of the stock is journalled, so that the stock
#              always ADDS UP: opening quantity plus the journal's movements.
#
# THE DIRECTORY ARRANGES WHAT NO SINGLE TEST CAN -- in 'hwut.conf' beside
# this file, read it first. hwut, when it enters this directory:
#
#     on_entry        'fixture.pl open': a fresh 'TMP/shop.db', stocked
#     on_before_test  'fixture.pl check before $HWUT_TEST $HWUT_CHOICE',
#     on_after_test   'fixture.pl check after ...': around every test run,
#                     whether the stock adds up, into 'TMP/frame.log' --
#                     hwut sets the two variables for the run
#     on_exit         'fixture.pl close'
#     apps            'delivery.json' is a test, though it carries no
#                     header: JSON has no comment to carry one. 'admit'
#                     takes it out of the files hwut ignores by default
#                     ('*.json'); 'execute' says how it is run --
#                     'shop.pl deliver delivery.json'.
#     collision       'delivery.json' and 'shop.pl sell' both write the
#                     database. SQLite lets one writer at a time hold the
#                     file; one that waits too long fails with 'database
#                     is locked'. hwut never runs the two at once.
#     dependency      'shop.pl report' runs after both, whatever their
#                     verdict: it reports what they left.
#
# STDERR  Every SQL statement is logged on stderr, as a server would. A
# word on stderr fails a run ('unexpected stderr') unless the header says
# 'stderr_ignored = true': the words there are on purpose, and no error.
#
# CHOICES
#
# sell     three clerks sell at once, each in a process of its own. The
#          sales are printed as '##! table unordered sep={;}': rows of
#          'item;qty', in any order -- and no column is a key, 'apple;1'
#          stands four times.
#
# report   the stock, as '##! table key=0 sep={;}', and the same rows
#          written to 'stock.csv': 'output' names the file, hwut reads it
#          after the run and compares it with its own GOOD. Then the frame
#          log of the shop's tests: what 'on_before_test' and 'on_after_test'
#          found around the delivery and the sale ('##! potpourri': which
#          ran first is free), and before this report.
#
# deliver  (no choice -- 'execute' of 'delivery.json' calls it) books a
#          delivery note: every line on the stock and into the journal, in
#          one transaction.
#______________________________________________________________________________
use strict;
use warnings;
use FindBin;
use lib $FindBin::Bin;
use JSON::PP;
use POSIX ();
use ShopDb;

my $HERE     = $FindBin::Bin;
my $DB_PATH  = "$HERE/TMP/shop.db";
my $LOG_PATH = "$HERE/TMP/frame.log";

#  What each clerk sells, one item per sale.
my @CLERK = (["anna",  ["apple", "apple", "pear"]],
             ["ben",   ["apple", "plum"]],
             ["chloe", ["apple"]]);


sub connect_db {
    # RETURN: ShopDb, a connection to the shop's database, every statement it
    #         executes logged on stderr.
    # Exits 1 where the database does not stand: 'on_entry' writes it.
    unless (-e $DB_PATH) {
        print STDERR "shop.pl: no $DB_PATH -- 'on_entry' writes it; by hand: "
                   . "'hwut.execute fixture open'\n";
        exit 1;
    }
    return ShopDb->connect($DB_PATH, timeout_s => 10,
                           trace => sub { print STDERR "sql: $_[0]\n" });
}


sub move {
    # RETURN: nothing. Changes the stock of 'item' by 'delta' and journals it,
    #         in one transaction.
    my ($db, $item, $delta, $source) = @_;
    $db->execute("BEGIN IMMEDIATE");
    $db->execute("UPDATE stock SET qty = qty + ? WHERE item = ?", $delta, $item);
    $db->execute("INSERT INTO journal VALUES (?, ?, ?)", $item, $delta, $source);
    $db->execute("COMMIT");
}


sub deliver {
    # RETURN: nothing. Books the delivery note in 'path' and prints it.
    my ($path) = @_;
    open(my $fh, "<", $path) or die "shop.pl: $path: $!\n";
    my $note = decode_json(do { local $/; <$fh> });
    close $fh;
    my $db = connect_db();
    $db->execute("BEGIN IMMEDIATE");
    for my $line (@{$note->{lines}}) {
        $db->execute("UPDATE stock SET qty = qty + ? WHERE item = ?", $line->{qty}, $line->{item});
        $db->execute("INSERT INTO journal VALUES (?, ?, ?)", $line->{item}, $line->{qty}, $note->{note});
    }
    $db->execute("COMMIT");
    print "delivery note $note->{note} from $note->{supplier}:\n";
    printf "    %-6s +%d\n", $_->{item}, $_->{qty} for @{$note->{lines}};
}


sub sell {
    # RETURN: nothing. Three clerks sell at once, each a process of its own;
    #         prints every sale, in the order the clerks booked them.
    #  A CLERK IS A PROCESS: each books on a connection of its own and tells
    #  every sale, once committed, through one pipe -- a line is one write,
    #  so the pipe's order is the order of booking.
    connect_db()->close;
    pipe(my $reader, my $writer) or die "shop.pl: pipe: $!\n";
    my @pid;
    for my $clerk (@CLERK) {
        my ($name, $item_list) = @$clerk;
        my $pid = fork // die "shop.pl: fork: $!\n";
        if ($pid == 0) {
            close $reader;
            my $ok = eval {
                my $db = connect_db();
                for my $item (@$item_list) {
                    move($db, $item, -1, $name);
                    syswrite($writer, "sale $item;1\n");
                }
                $db->close;
                1;
            };
            syswrite($writer, "error $name: " . ($@ =~ s/\s+$//r) . "\n") unless $ok;
            POSIX::_exit(0);
        }
        push @pid, $pid;
    }
    close $writer;
    my (@sale, @error);
    while (my $line = <$reader>) {
        chomp $line;
        if    ($line =~ /^sale (.*)$/)  { push @sale,  $1 }
        elsif ($line =~ /^error (.*)$/) { push @error, $1 }
    }
    waitpid($_, 0) for @pid;
    if (@error) {
        print STDERR "shop.pl: a sale failed -- " . join("; ", @error) . "\n";
        exit 1;
    }
    print "sales, item;qty -- in the order the clerks booked them:\n";
    print "##! table unordered sep={;}\n";
    print "$_\n" for @sale;
    print "####\n";
}


sub report {
    # RETURN: nothing. Prints the stock and the frame log; writes 'stock.csv'.
    my $db  = connect_db();
    my @row = $db->rows("SELECT item, qty FROM stock ORDER BY qty, item");
    open(my $fh, ">", "$HERE/stock.csv") or die "shop.pl: stock.csv: $!\n";
    print $fh "item;qty\n";
    printf $fh "%s;%d\n", @$_ for sort { $a->[0] cmp $b->[0] } @row;
    close $fh;
    print "stock, item;qty (also written to stock.csv):\n";
    print "##! table key=0 sep={;}\n";
    printf "%s;%d\n", @$_ for @row;
    print "####\n";
    open($fh, "<", $LOG_PATH) or die "shop.pl: $LOG_PATH: $!\n";
    my @line = map { s/\s+$//r } <$fh>;
    close $fh;
    print "the frame, around the delivery and the sale:\n";
    print "##! potpourri\n";
    print "$_\n" for grep { index($_, "shop.pl report") < 0 } @line;
    print "####\n";
    print "$_\n" for grep { index($_, "shop.pl report") >= 0 } @line;
}


my $command = $ARGV[0] // "";
if    ($command eq "deliver") { deliver($ARGV[1]) }
elsif ($command eq "sell")    { sell() }
elsif ($command eq "report")  { report() }
else {
    print "choices: sell, report\n";
    exit 1;
}
print "<hwut-end>\n";
