#! /usr/bin/env perl
#
# @hwut {
#     title   = "Demo: what hwut tolerates, and where it is said"
#     choices {
#         plain       { features = ["demo-perl", "demo-perl+cover-exact-comparison"] }
#         tolerance   { features = ["demo-perl", "demo-perl+cover-equivalence-pattern", "demo-perl+cover-numeric-ratio"]
#                       tolerance {
#                           eq_pattern    = ["(hello|bonjour|hallo|buongiorno|hola|ahoj)"]
#                           numeric_ratio = 0.01
#                       } }
#         constraints { features = ["demo-perl", "demo-perl+cover-constraints"]
#                       tolerance {
#                           constraints = ["load >= 0 and load <= 100",
#                                          "even % 2 == 0",
#                                          "twice == 2 * once"]
#                       } }
#         analogies   { features = ["demo-perl", "demo-perl+cover-analogies"] }
#         race        { features = ["demo-perl", "demo-perl+cover-order-free-block"] }
#         pool        { features = ["demo-perl", "demo-perl+cover-potpourri-subset-duplicates"] }
#         progress    { features = ["demo-perl", "demo-perl+cover-visible-nothing"]
#                       tolerance { nothing = ["[.]+"] } }
#         lisp        { features = ["demo-perl", "demo-perl+cover-analogy-markers"]
#                       tolerance { analogy = ["{", "}"] } }
#         clusters    { features = ["demo-perl", "demo-perl+cover-point-cloud-pair-distance"] }
#     }
# }
#
#______________________________________________________________________________
# A TEST APPLICATION OF HWUT, FOR READING -- the template for every language.
#
#     hwut.run                   runs every choice below, compares with GOOD/
#     hwut.play demo.pl plain    runs one choice and records it in OUT/
#     hwut.accept demo.pl plain  blesses that recording as GOOD; it runs
#                                nothing. Where a GOOD stands, the change
#                                is 'hwut.merge's -- or '--force' (also
#                                '--as-is') replaces it whole.
#     hwut.merge                 shows OUTPUT against GOOD, key by key
#     hwut.config.show demo.pl   prints what hwut READ from the header above
#
# The header above is the whole configuration: a title, and one scope per
# choice. hwut calls 'demo.pl <choice>' and compares what it prints on stdout
# with 'GOOD/demo.pl--<choice>.txt'. '<hwut-end>' closes the stream: a stream
# without it never COMPLETED and is not accepted.
#
# Every run is seeded by the clock, so the output differs from run to run --
# and every choice passes anyway. Each shows WHY:
#
# plain        nothing varies; nothing is tolerated. The output must equal
#              GOOD, line by line.
#
# tolerance    'eq_pattern': a greeting drawn at random; any greeting the
#              pattern names is EQUIVALENT to any other.
#              'numeric_ratio': a value drawn from [19.91, 20.09]. The band
#              belongs to the GOOD's number, |n| x ratio: GOOD 19.91 against
#              20.09 differs by 0.18, inside 19.91 x 0.01 = 0.1991. Every pair
#              from the interval passes; 20.30 would not.
#
# constraints  '((name: value))' BINDS a value; the expressions under
#              'constraints' judge it, not the GOOD's value. 'load' may be
#              anything from 0 to 100; 'even' any even number; 'twice' must be
#              twice 'once', whatever 'once' is. A law over two variables is
#              checked once both are bound. A binding that breaks its law is
#              red.
#
# race         '##! potpourri' ... '####' opens a block whose lines may arrive
#              in ANY order -- three workers print as they finish. The same
#              lines must stand on both sides, each once; the order is free.
#              The program prints the markers, and so does GOOD.
#
# analogies    '((x))' is a placeholder: '((a7f3))' against GOOD's '((91c2))'
#              is equivalent where the mapping holds throughout the stream --
#              the same handle opened, read and closed. A handle that changes
#              in mid-stream is red.
#
# pool         '##! potpourri subset duplicates': four workers share twelve
#              jobs; who takes how many is the scheduler's. 'subset': a
#              worker that got no job is no fault -- every line of the run
#              must stand in GOOD, not every line of GOOD in the run.
#              'duplicates': a worker named twice is one line. The GOOD was
#              recorded from a run in which all four worked.
#
# progress     'nothing': a line made only of what the pattern names counts
#              as no line. A download prints dots while it waits -- none, or
#              a few lines of them -- and the dots are no fact.
#
# lisp         'analogy = ["{", "}"]': the output is Lisp, where '((' is
#              syntax, so the placeholder is marked otherwise. An object is
#              printed with its address, '{10044C1F33}'; the address differs
#              per run, and must be the same object throughout.
#
# clusters     '##! point-cloud limit=0.3 pair dist=Linf': three centroids of
#              a clustering, in whatever order the run finds them. 'pair':
#              each centroid pairs with ONE point of GOOD -- two centroids in
#              one cluster are red. 'dist=Linf': within 0.3 in x AND in y.
#______________________________________________________________________________
use strict;
use warnings;
no warnings "portable";               # the Lisp addresses are 40 bits wide
use threads;
use threads::shared;
use Thread::Queue;
use Time::HiRes qw(sleep time);
use List::Util qw(shuffle min max sum);

$| = 1;
my @GREETING = qw(hello bonjour hallo buongiorno hola ahoj);
my $PI       = 4 * atan2(1, 1);


sub uniform {
    # RETURN: number, drawn uniformly from [low, high].
    my ($low, $high) = @_;
    return $low + rand($high - $low);
}

sub randint {
    # RETURN: integer, drawn uniformly from [low, high], both included.
    my ($low, $high) = @_;
    return $low + int(rand($high - $low + 1));
}

sub gauss {
    # RETURN: number, a draw of the normal distribution (mu, sigma), by the
    #         Box-Muller transform over 'rand'.
    my ($mu, $sigma) = @_;
    my $u1 = 1.0 - rand();                               # in (0, 1]
    return $mu + $sigma * sqrt(-2.0 * log($u1)) * cos(2.0 * $PI * rand());
}

sub sample_two {
    # RETURN: (integer, integer), two different integers drawn from [low, high).
    my ($low, $high) = @_;
    my $first = $low + int(rand($high - $low));
    my $second;
    do { $second = $low + int(rand($high - $low)) } while $second == $first;
    return ($first, $second);
}


sub plain {
    # RETURN: nothing. Prints what never varies.
    print "the first line\n";
    print "the second line: 1 2 3\n";
}

sub tolerance {
    # RETURN: nothing. Prints a greeting and a value, both drawn at random.
    printf "greeting: %s, world\n", $GREETING[int rand @GREETING];
    printf "value:    %.2f\n", uniform(19.91, 20.09);
}

sub constraints {
    # RETURN: nothing. Prints bindings, each drawn at random, each lawful.
    printf "load  ((load: %.1f)) %%\n", uniform(0.0, 100.0);
    printf "even  ((even: %i))\n", 2 * randint(0, 500);
    my $once = randint(1, 50);
    printf "once  ((once: %i))\n", $once;
    printf "twice ((twice: %i))\n", 2 * $once;
}

sub analogies {
    # RETURN: nothing. Prints two handles, each drawn at random, each used
    #         consistently from opening to closing.
    my ($first, $second) = sample_two(0x1000, 0x10000);
    printf "open  ((%04x)) input.txt\n", $first;
    printf "open  ((%04x)) output.txt\n", $second;
    printf "read  ((%04x)) 17 lines\n", $first;
    printf "write ((%04x)) 17 lines\n", $second;
    printf "close ((%04x))\n", $first;
    printf "close ((%04x))\n", $second;
}

sub race {
    # RETURN: nothing. Three workers print as they finish; the order is the
    #         scheduler's, the facts are not. The program frames the
    #         unordered block itself: '##! potpourri' ... '####'.
    #  A THREAD STARTS WITH A COPY OF ITS PARENT'S 'rand': drawn in a thread,
    #  the three delays would be one. So they are drawn here, before.
    my $lock :shared;
    my $work = sub {
        my ($name, $jobs, $delay) = @_;
        sleep $delay;
        lock $lock;
        printf "worker %s done: %i jobs\n", $name, $jobs;
    };
    my @argument = map { [@$_, uniform(0.0, 0.02)] } (["A", 3], ["B", 5], ["C", 2]);
    print "start\n";
    print "##! potpourri\n";
    my @pool = map { threads->create($work, @$_) } @argument;
    $_->join for @pool;
    print "####\n";
    print "all joined\n";
}

sub pool {
    # RETURN: nothing. Four workers take twelve jobs from one queue; each
    #         reports the job it finished. Who takes how many is the
    #         scheduler's.
    my $job_queue = Thread::Queue->new(0 .. 11);
    $job_queue->end;
    my @done :shared;
    my $work = sub {
        my ($name, $seed) = @_;
        srand($seed);                                  # a stream of its own
        while (defined $job_queue->dequeue_nb) {
            sleep uniform(0.0, 0.005);
            lock @done;
            push @done, "job done by worker $name";
        }
    };
    my @pool = map { threads->create($work, $_, int rand 2**31) } qw(A B C D);
    $_->join for @pool;
    print "twelve jobs, four workers:\n";
    print "##! potpourri subset duplicates\n";
    print "$_\n" for @done;
    print "####\n";
    printf "jobs done: %i\n", scalar @done;
}

sub progress {
    # RETURN: nothing. A download that prints dots while it waits; how many
    #         is the network's.
    print "connecting to mirror\n";
    print "." x randint(1, 8), "\n" for 1 .. randint(0, 3);
    print "connected\n";
    print "received 1024 bytes\n";
}

sub lisp {
    # RETURN: nothing. A Lisp session at its prompt: two objects, each
    #         printed with its address '{...}', drawn anew per run, and each
    #         used again.
    my ($table, $thread) = sample_two(0x1000000000, 0x1100000000);
    print "* (defvar *cache* (make-hash-table))\n";
    printf "#<HASH-TABLE :TEST EQL :COUNT 0 {%X}>\n", $table;
    print "* (defvar *worker* (make-thread (lambda () (loop (sleep 1))) :name \"worker\"))\n";
    printf "#<THREAD \"worker\" RUNNING {%X}>\n", $thread;
    print "* (let ((key (list 1 2))) (setf (gethash key *cache*) *worker*))\n";
    printf "#<THREAD \"worker\" RUNNING {%X}>\n", $thread;
    print "* *cache*\n";
    printf "#<HASH-TABLE :TEST EQL :COUNT 1 {%X}>\n", $table;
}

sub clusters {
    # RETURN: nothing. Clusters 90 noisy points around three centres and
    #         prints the centroids in the order the run found them.
    my @centre = ([1.0, 1.0], [5.0, 4.0], [9.0, 1.0]);
    my @point  = shuffle map { my $c = $_; map { [$c->[0] + gauss(0.0, 0.3),
                                                  $c->[1] + gauss(0.0, 0.3)] } 1 .. 30 } @centre;
    my $d2 = sub { ($_[0][0] - $_[1][0]) ** 2 + ($_[0][1] - $_[1][1]) ** 2 };
    #  The start: one point at random, then twice the point farthest from
    #  every start chosen so far -- one start per cluster.
    my @centroid = ($point[int rand @point]);
    while (@centroid < 3) {
        my ($best, $best_d) = (undef, -1);
        for my $p (@point) {
            my $d = min(map { $d2->($p, $_) } @centroid);
            ($best, $best_d) = ($p, $d) if $d > $best_d;
        }
        push @centroid, $best;
    }
    for (1 .. 10) {
        my @member = ([], [], []);
        for my $p (@point) {
            my ($nearest) = sort { $d2->($p, $centroid[$a]) <=> $d2->($p, $centroid[$b]) } 0 .. 2;
            push @{$member[$nearest]}, $p;
        }
        @centroid = map { my $m = $_; [sum(map { $_->[0] } @$m) / @$m,
                                       sum(map { $_->[1] } @$m) / @$m] } @member;
    }
    print "centroids (x y), in the order found:\n";
    print "##! point-cloud limit=0.3 pair dist=Linf\n";
    printf "    %5.2f %5.2f\n", @$_ for @centroid;
    print "####\n";
}


my @CHOICE = ([plain => \&plain], [tolerance => \&tolerance], [constraints => \&constraints],
              [analogies => \&analogies], [race => \&race], [pool => \&pool],
              [progress => \&progress], [lisp => \&lisp], [clusters => \&clusters]);
my %CHOICE = map { @$_ } @CHOICE;

srand(int(time * 1e6) % 2**31);
my $choice = $ARGV[0] // "";
unless ($CHOICE{$choice}) {
    print "choices: ", join(", ", map { $_->[0] } @CHOICE), "\n";
    exit 1;
}
$CHOICE{$choice}->();
print "<hwut-end>\n";
