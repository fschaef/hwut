#! /usr/bin/env perl
#
# @hwut {
#     title     = "Demo: a terminal program's screen, as a person sees it"
#     tolerance { regions    = false
#                 comment    = false
#                 whitespace = false }
#     choices {
#         open   { features = ["demo-perl+cover-terminal-screen", "demo-perl+cover-screen-as-seen"] }
#         scroll { features = ["demo-perl+cover-terminal-screen", "demo-perl+cover-screen-as-seen"] }
#     }
# }
#
#______________________________________________________________________________
# SUBJECT  the screen of 'viewer.pl', a full-screen file viewer, run in a
#          terminal of 9 rows and 40 columns and driven by its keys.
# REQUIREMENT  The viewer shows a title bar in reverse video, the file's lines
#              as they fit, and a status line -- the keys flush left, the lines
#              shown flush right; 'j' and the down key go one line further,
#              'k' one back.
#
# Hwut::Vterm's 'Terminal' runs the viewer on a pseudo-terminal: the viewer
# cannot tell it from a real one. The test PRESSES KEYS and is told what
# CHANGED: three regions are declared -- title, body, status -- and after
# every key, once the viewer has gone quiet, each region whose text changed
# is printed. A redraw that changes nothing is not told: the title is told
# once.
#
# THE SCREEN IS COMPARED AS A PERSON SEES IT -- three tolerances switched
# off, in the header:
#
#     regions = false     the file shown is a GOOD file of hwut, with a
#                         '##! potpourri' ... '####' block. On this screen
#                         those are characters, not a region to open.
#     comment = false     '## ...' lines are characters too, not notes.
#     whitespace = false  the status line's two halves stand flush left and
#                         flush right: every blank between them counts. A
#                         half moved by one column is red. (A line's leading
#                         and trailing blanks are stripped all the same.)
#
# libvterm and FFI::Platypus must be installed ('apt install libvterm0
# libffi-platypus-perl'); where it is not, the
# test prints why and probes nothing -- its output differs from GOOD and the
# reason stands in the difference.
#
# CHOICES  open    the viewer opened, then quit.
#          scroll  down, down, 'j', then 'k': three lines on, one back.
#______________________________________________________________________________
use strict;
use warnings;
use FindBin;
use lib $FindBin::Bin;
use SupportPath;
use File::Path qw(make_path);
use Hwut::Vterm;

my $HERE   = $FindBin::Bin;
my $SAMPLE = <<'TEXT';
## demo.pl race -- three workers
start
##! potpourri
worker B done: 5 jobs
worker A done: 3 jobs
worker C done: 2 jobs
####
all joined
## the order between the markers is
## free; the lines are not.
TEXT

$| = 1;


sub show {
    # RETURN: nothing. Prints one region that changed, its rows as they stand
    #         on the screen, from the first column.
    my ($name, $line_list) = @_;
    print "-- $name\n";
    print "$_\n" for @$line_list;
}


sub view {
    # RETURN: nothing. Runs the viewer on the sample, presses the keys of the
    #         array ref 'key_list', quits, and prints what changed after each
    #         step.
    my ($key_list) = @_;
    my $path = "$HERE/TMP/race.txt";
    make_path("$HERE/TMP");
    open(my $fh, ">", $path) or die "screen.pl: $path: $!\n";
    print $fh $SAMPLE;
    close $fh;
    my $terminal = Hwut::Vterm::Terminal->new(9, 40);
    $terminal->region("title",  row => 0);
    $terminal->region("body",   row => 1, row_n => 7);
    $terminal->region("status", row => -1);
    $terminal->on_change(\&show);
    print "> viewer.pl race.txt\n";
    $terminal->run([$^X, "$HERE/viewer.pl", $path]);
    printf "title bar: %s\n", $terminal->cell(0, 1)->attribute_text || "plain";
    for my $key (@$key_list) {
        print "> $key\n";
        if (length $key == 1) { $terminal->send($key) }
        else                  { $terminal->press($key) }
    }
    $terminal->send("q");
    printf "> q -- exit status %d\n", $terminal->wait;
    $terminal->close;
}


my %CHOICE = (open => [], scroll => ["down", "down", "j", "k"]);

my $choice = $ARGV[0] // "";
unless ($CHOICE{$choice}) {
    print "choices: open, scroll\n";
    exit 1;
}
unless (eval { view($CHOICE{$choice}); 1 }) {
    my $error = $@;
    die $error unless ref $error && $error->isa("Hwut::Vterm::Error") && $error->kind eq "LibraryMissing";
    print "$error\n";
    exit 1;
}
print "<hwut-end>\n";
