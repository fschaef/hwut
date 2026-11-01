#! /usr/bin/env pwsh
#
# @hwut {
#     title   = "Demo: what hwut tolerates, and where it is said"
#     choices {
#         plain       { features = ["demo-passes-on-every-run", "exact-comparison"] }
#         tolerance   { features = ["demo-passes-on-every-run", "equivalence-pattern", "numeric-ratio"]
#                       tolerance {
#                           eq_pattern    = ["(hello|bonjour|hallo|buongiorno|hola|ahoj)"]
#                           numeric_ratio = 0.01
#                       } }
#         constraints { features = ["demo-passes-on-every-run", "constraints"]
#                       tolerance {
#                           constraints = ["load >= 0 and load <= 100",
#                                          "even % 2 == 0",
#                                          "twice == 2 * once"]
#                       } }
#         analogies   { features = ["demo-passes-on-every-run", "analogies"] }
#         race        { features = ["demo-passes-on-every-run", "order-free-block"] }
#         pool        { features = ["demo-passes-on-every-run", "potpourri-subset-duplicates"] }
#         progress    { features = ["demo-passes-on-every-run", "visible-nothing"]
#                       tolerance { nothing = ["[.]+"] } }
#         lisp        { features = ["demo-passes-on-every-run", "analogy-markers"]
#                       tolerance { analogy = ["{", "}"] } }
#         clusters    { features = ["demo-passes-on-every-run", "point-cloud-pair-distance"] }
#     }
# }
#
<#
______________________________________________________________________________
A TEST APPLICATION OF HWUT, FOR READING -- the template for every language.

    hwut.run                    runs every choice below, compares with GOOD/
    hwut.play demo.ps1 plain    runs one choice and records it in OUT/
    hwut.accept demo.ps1 plain  blesses that recording as GOOD; it runs
                                nothing. Where a GOOD stands, the change
                                is 'hwut.merge's -- or '--force' (also
                                '--as-is') replaces it whole.
    hwut.merge                  shows OUTPUT against GOOD, key by key
    hwut.config.show demo.ps1   prints what hwut READ from the header above

The header above is the whole configuration: a title, and one scope per
choice. hwut calls 'pwsh demo.ps1 <choice>' and compares what it prints on
stdout with 'GOOD/demo.ps1--<choice>.txt' -- a link to the Python demo's
GOOD: the same choice prints the same text. '<hwut-end>' closes the stream:
a stream without it never COMPLETED and is not accepted.

Every run is seeded by the clock, so the output differs from run to run --
and every choice passes anyway. Each shows WHY:

plain        nothing varies; nothing is tolerated. The output must equal
             GOOD, line by line.

tolerance    'eq_pattern': a greeting drawn at random; any greeting the
             pattern names is EQUIVALENT to any other.
             'numeric_ratio': a value drawn from [19.91, 20.09]. The band
             belongs to the GOOD's number, |n| x ratio: GOOD 19.91 against
             20.09 differs by 0.18, inside 19.91 x 0.01 = 0.1991. Every pair
             from the interval passes; 20.30 would not.

constraints  '((name: value))' BINDS a value; the expressions under
             'constraints' judge it, not the GOOD's value. 'load' may be
             anything from 0 to 100; 'even' any even number; 'twice' must be
             twice 'once', whatever 'once' is. A law over two variables is
             checked once both are bound. A binding that breaks its law is
             red.

race         '##! potpourri' ... '####' opens a block whose lines may arrive
             in ANY order -- three workers print as they finish. The same
             lines must stand on both sides, each once; the order is free.
             The program prints the markers, and so does GOOD.

analogies    '((x))' is a placeholder: '((a7f3))' against GOOD's '((91c2))'
             is equivalent where the mapping holds throughout the stream --
             the same handle opened, read and closed. A handle that changes
             in mid-stream is red.

pool         '##! potpourri subset duplicates': four workers share twelve
             jobs; who takes how many is the scheduler's. 'subset': a
             worker that got no job is no fault -- every line of the run
             must stand in GOOD, not every line of GOOD in the run.
             'duplicates': a worker named twice is one line. The GOOD was
             recorded from a run in which all four worked.

progress     'nothing': a line made only of what the pattern names counts
             as no line. A download prints dots while it waits -- none, or
             a few lines of them -- and the dots are no fact.

lisp         'analogy = ["{", "}"]': the output is Lisp, where '((' is
             syntax, so the placeholder is marked otherwise. An object is
             printed with its address, '{10044C1F33}'; the address differs
             per run, and must be the same object throughout.

clusters     '##! point-cloud limit=0.3 pair dist=Linf': three centroids of
             a clustering, in whatever order the run finds them. 'pair':
             each centroid pairs with ONE point of GOOD -- two centroids in
             one cluster are red. 'dist=Linf': within 0.3 in x AND in y.

THREADS are 'ForEach-Object -Parallel': one runspace per worker. They write
through [Console]::Out, which .NET synchronises -- a line is never torn.
______________________________________________________________________________
#>
. "$PSScriptRoot/hwut_support.ps1"

$GREETING_LIST = @('hello', 'bonjour', 'hallo', 'buongiorno', 'hola', 'ahoj')
$script:rng    = [Random]::new([int]([DateTime]::UtcNow.Ticks % [int]::MaxValue))

<# RETURN: double, drawn uniformly from ['low', 'high']. #>
function uniform([double]$low, [double]$high) { $low + ($high - $low) * $script:rng.NextDouble() }

<# RETURN: double, drawn from the normal distribution of 'mu' and 'sigma' (Box-Muller). #>
function gauss([double]$mu, [double]$sigma) {
    $u = 1.0 - $script:rng.NextDouble()
    $mu + $sigma * [Math]::Sqrt(-2.0 * [Math]::Log($u)) * [Math]::Cos(2.0 * [Math]::PI * $script:rng.NextDouble())
}

<# RETURN: nothing. Prints what never varies. #>
function plain {
    Out-Py 'the first line'
    Out-Py 'the second line: 1 2 3'
}

<# RETURN: nothing. Prints a greeting and a value, both drawn at random. #>
function tolerance {
    Out-Py ('greeting: {0}, world' -f $GREETING_LIST[$script:rng.Next($GREETING_LIST.Count)])
    Out-Py ('value:    {0:F2}' -f (uniform 19.91 20.09))
}

<# RETURN: nothing. Prints bindings, each drawn at random, each lawful. #>
function constraints {
    Out-Py ('load  ((load: {0:F1})) %' -f (uniform 0.0 100.0))
    Out-Py ('even  ((even: {0}))' -f (2 * $script:rng.Next(0, 501)))
    $once = $script:rng.Next(1, 51)
    Out-Py ('once  ((once: {0}))' -f $once)
    Out-Py ('twice ((twice: {0}))' -f (2 * $once))
}

<#
RETURN: nothing. Prints two handles, each drawn at random, each used
        consistently from opening to closing.
#>
function analogies {
    $first = $script:rng.Next(0x1000, 0x10000)
    do { $second = $script:rng.Next(0x1000, 0x10000) } while ($second -eq $first)
    Out-Py ('open  (({0:x4})) input.txt'  -f $first)
    Out-Py ('open  (({0:x4})) output.txt' -f $second)
    Out-Py ('read  (({0:x4})) 17 lines'   -f $first)
    Out-Py ('write (({0:x4})) 17 lines'   -f $second)
    Out-Py ('close (({0:x4}))'            -f $first)
    Out-Py ('close (({0:x4}))'            -f $second)
}

<#
RETURN: nothing. Three workers print as they finish; the order is the
        scheduler's, the facts are not. The program frames the unordered
        block itself: '##! potpourri' ... '####'.
#>
function race {
    Out-Py 'start'
    Out-Py '##! potpourri'
    @(@('A', 3), @('B', 5), @('C', 2)) | ForEach-Object -ThrottleLimit 3 -Parallel {
        Start-Sleep -Milliseconds (Get-Random -Minimum 0 -Maximum 20)
        [Console]::Out.WriteLine(('worker {0} done: {1} jobs' -f $_[0], $_[1]))
    }
    Out-Py '####'
    Out-Py 'all joined'
}

<#
RETURN: nothing. Four workers take twelve jobs from one queue; each
        reports the job it finished. Who takes how many is the scheduler's.
#>
function pool {
    $job_queue = [System.Collections.Concurrent.ConcurrentQueue[int]]::new()
    foreach ($job in 0..11) { $job_queue.Enqueue($job) }
    $done_list = [System.Collections.Concurrent.ConcurrentQueue[string]]::new()
    'A', 'B', 'C', 'D' | ForEach-Object -ThrottleLimit 4 -Parallel {
        $job_queue, $done_list = $using:job_queue, $using:done_list
        $job = 0
        while ($job_queue.TryDequeue([ref]$job)) {
            Start-Sleep -Milliseconds (Get-Random -Minimum 0 -Maximum 5)
            $done_list.Enqueue("job done by worker $_")
        }
    }
    Out-Py 'twelve jobs, four workers:'
    Out-Py '##! potpourri subset duplicates'
    foreach ($line in $done_list) { Out-Py $line }
    Out-Py '####'
    Out-Py ('jobs done: {0}' -f $done_list.Count)
}

<# RETURN: nothing. A download that prints dots while it waits; how many is the network's. #>
function progress {
    Out-Py 'connecting to mirror'
    for ($i = $script:rng.Next(0, 4); $i -gt 0; $i--) { Out-Py ('.' * $script:rng.Next(1, 9)) }
    Out-Py 'connected'
    Out-Py 'received 1024 bytes'
}

<#
RETURN: nothing. A Lisp session at its prompt: two objects, each printed
        with its address '{...}', drawn anew per run, and each used again.
#>
function lisp {
    $table  = $script:rng.NextInt64(0x1000000000, 0x1100000000)
    do { $thread = $script:rng.NextInt64(0x1000000000, 0x1100000000) } while ($thread -eq $table)
    Out-Py '* (defvar *cache* (make-hash-table))'
    Out-Py ('#<HASH-TABLE :TEST EQL :COUNT 0 {{{0:X}}}>' -f $table)
    Out-Py '* (defvar *worker* (make-thread (lambda () (loop (sleep 1))) :name "worker"))'
    Out-Py ('#<THREAD "worker" RUNNING {{{0:X}}}>' -f $thread)
    Out-Py '* (let ((key (list 1 2))) (setf (gethash key *cache*) *worker*))'
    Out-Py ('#<THREAD "worker" RUNNING {{{0:X}}}>' -f $thread)
    Out-Py '* *cache*'
    Out-Py ('#<HASH-TABLE :TEST EQL :COUNT 1 {{{0:X}}}>' -f $table)
}

<# RETURN: double, the squared distance between the points 'p' and 'c'. #>
function distance2($p, $c) { ($p[0] - $c[0]) * ($p[0] - $c[0]) + ($p[1] - $c[1]) * ($p[1] - $c[1]) }

<#
RETURN: nothing. Clusters 90 noisy points around three centres and prints
        the centroids in the order the run found them.
#>
function clusters {
    $point_list = [System.Collections.Generic.List[object]]::new()
    foreach ($centre in @(@(1.0, 1.0), @(5.0, 4.0), @(9.0, 1.0))) {
        for ($i = 0; $i -lt 30; $i++) { $point_list.Add(@(($centre[0] + (gauss 0.0 0.3)), ($centre[1] + (gauss 0.0 0.3)))) }
    }
    $point_list = [object[]]($point_list | Sort-Object { $script:rng.Next() })
    #  The start: one point at random, then twice the point farthest from
    #  every start chosen so far -- one start per cluster.
    $centroid_list = [System.Collections.Generic.List[object]]::new()
    $centroid_list.Add($point_list[$script:rng.Next($point_list.Count)])
    while ($centroid_list.Count -lt 3) {
        $best, $best_d = $null, -1.0
        foreach ($p in $point_list) {
            $d = [double]::MaxValue
            foreach ($c in $centroid_list) { $d = [Math]::Min($d, (distance2 $p $c)) }
            if ($d -gt $best_d) { $best, $best_d = $p, $d }
        }
        $centroid_list.Add($best)
    }
    for ($round = 0; $round -lt 10; $round++) {
        $member_db = @(foreach ($i in 0..2) { , [System.Collections.Generic.List[object]]::new() })
        foreach ($p in $point_list) {
            $nearest = 0
            for ($i = 1; $i -lt 3; $i++) { if ((distance2 $p $centroid_list[$i]) -lt (distance2 $p $centroid_list[$nearest])) { $nearest = $i } }
            $member_db[$nearest].Add($p)
        }
        $centroid_list = [System.Collections.Generic.List[object]]::new()
        foreach ($m in $member_db) {
            $sx, $sy = 0.0, 0.0
            foreach ($p in $m) { $sx += $p[0]; $sy += $p[1] }
            $centroid_list.Add(@(($sx / $m.Count), ($sy / $m.Count)))
        }
    }
    Out-Py 'centroids (x y), in the order found:'
    Out-Py '##! point-cloud limit=0.3 pair dist=Linf'
    foreach ($c in $centroid_list) { Out-Py ('    {0,5:F2} {1,5:F2}' -f $c[0], $c[1]) }
    Out-Py '####'
}

$CHOICE_LIST = @('plain', 'tolerance', 'constraints', 'analogies', 'race', 'pool', 'progress', 'lisp', 'clusters')

$choice = if ($args.Count -gt 0) { [string]$args[0] } else { '' }
if ($CHOICE_LIST -cnotcontains $choice) {
    Out-Py ('choices: {0}' -f ($CHOICE_LIST -join ', '))
    exit 1
}
& $choice
Out-Py '<hwut-end>'
