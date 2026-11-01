#! /usr/bin/env pwsh
#
# @hwut {
#     title    = "Demo: a garage's space counter -- a space, a stream and races, generated"
#     interactive = true
#     choices {
#         space       { features = ["space-from-hocon", "space-iterator", "hwut-runner"]
#                       tolerance { constraints = ["mismatches == 0"] } }
#         random      { features = ["deterministic-stream", "hwut-runner"]
#                       tolerance { constraints = ["mismatches == 0"] } }
#         race-naive  { features = ["deterministic-timeline", "space-iterator", "hwut-runner"]
#                       tolerance { constraints = ["overbooked > 0"] } }
#         race-atomic { features = ["deterministic-timeline", "space-iterator", "hwut-runner"]
#                       tolerance { constraints = ["overbooked == 0"] } }
#     }
# }
#
<#
______________________________________________________________________________
SUBJECT  the counter of free spaces at a garage's gates: which cars it
         admits, which it refuses, and how many stand inside.
REQUIREMENT  The garage admits a car only while a space is free, lets a car
             out only while one stands inside, and never holds more cars
             than it has spaces -- also when two gates admit at once.

No choice writes its cases out by hand. Each GENERATES them, with one of
hwut's helpers for writing tests (hwut/support/test_writing/powershell):

space        'garage-space.hocon' states the tested space -- capacities,
             cars arriving, cars leaving -- in hwut's HOCON, read by
             'hwut_hocon'. A reviewer edits the space without reading
             PowerShell. '[SpaceIterator]::Do' walks every combination: 3 x
             5 x 4 = 60 cases. Each is printed as one cell of a matrix, and
             checked against the model: admitted = min(arriving,
             capacity), out = min(leaving, admitted).

random       '[DeterministicStream]::new(4711)' draws 1000 cars arriving
             and leaving at a garage of 5. The draw is the same on every
             machine and in every language hwut supports -- the stream is
             a linear congruential generator, not .NET's 'Random' -- so
             the GOOD is exact (the Python demo's), and a failing run can
             be replayed by its seed.

race-naive   two gates, one free space. A gate CHECKS whether a space is
             free, and later ADMITS its car. 'deterministic_timeline'
             runs the two gates on timelines drawn as strings -- '1 1 '
             fires at tick 0 and tick 2 -- so every interleaving is played
             exactly, not hoped for with sleeps. 'SpaceIterator'
             generates all six interleavings of two two-step gates in four
             ticks. Where both gates check before either admits, both
             admit: the garage is overbooked. The law is 'overbooked > 0':
             the GOOD is the accepted violation report.

race-atomic  the same six interleavings, the gate checking and admitting
             in ONE step under the counter's lock. 'overbooked == 0'.

A GATE IS NO 'Trigger' here, as it is in Python: a PowerShell class can
derive only from a class known when the file is PARSED, and the support is
found at run time (hwut_support.ps1, RATIONALE DEMO-POWERSHELL-1). The
dispatcher asks a trigger for what Trigger has -- 'timeline', 'name',
'Fire', 'OnTermination' -- and 'Gate' has them.

THE FRONT END is hwut's HwutRunner: the choice map below is the whole
command line, '--hwut-info' included. The header says
'interactive = true': hwut starts the application ONCE and asks for the
choices one after another in that one process -- an accelerator only: a
choice's output equals what it prints when run alone.
______________________________________________________________________________
#>
. "$PSScriptRoot/hwut_support.ps1" space_iterator hwut_hocon deterministic_random deterministic_timeline hwut_pytext

#  The unit under test: a counter of the spaces a garage has.
class Garage {
    [int] $capacity
    [int] $occupied

    <# RETURN: Garage, empty, of 'capacity' spaces. #>
    Garage([int]$capacity) { $this.capacity = $capacity; $this.occupied = 0 }

    <# RETURN: int, the number of spaces free now -- negative where the garage is overbooked. #>
    [int] Free() { return $this.capacity - $this.occupied }

    <#
    RETURN: $true, a car was admitted, if a space was free;
            $false, else (the car is refused).
    #>
    [bool] Arrive() {
        if ($this.Free() -le 0) { return $false }
        $this.occupied++
        return $true
    }

    <#
    RETURN: $true, a car drove out, if one stood inside;
            $false, else.
    #>
    [bool] Leave() {
        if ($this.occupied -eq 0) { return $false }
        $this.occupied--
        return $true
    }
}

# _____________________________________________________________________________
# space -- the tested space from HOCON, walked by SpaceIterator
#
<#
RETURN: list of @(name, values), the dimensions of the space in 'path', in
        the order written. Every fault the HOCON reader found is printed
        with '!!' first.
#>
function read_space([string]$path) {
    $i = 0
    $line_list = foreach ($text in [System.IO.File]::ReadAllLines($path)) { $i++; [SourceLine]::new($text, $i, 0) }
    $document, $fault_list = [Hocon]::Parse(@($line_list), [System.IO.Path]::GetFileName($path))
    foreach ($fault in $fault_list) { Out-Py "!! $fault" }
    $space = $document.Get('space').node
    return , @(foreach ($e in $space.entry_list) { , @($e.key, @(foreach ($item in $e.node.item_list) { $item.value })) })
}

<# RETURN: nothing. Prints every case of the space as a matrix cell. #>
function space {
    $dimension_list = read_space (Join-Path $PSScriptRoot 'garage-space.hocon')
    $value_list = @(foreach ($d in $dimension_list) { , $d[1] })
    Out-Py ('space: {0}' -f (@(foreach ($d in $dimension_list) { '{0} {1}' -f $d[0], [PyText]::ListRepr($d[1]) }) -join '  x  '))
    Out-Py "cell: cars inside / cars refused at the gate ('!!' differs from the model)"
    $mismatch_n = 0
    $row_db = @{}
    foreach ($point in [SpaceIterator]::Do($value_list)) {
        $capacity, $arriving, $leaving = $point
        $garage  = [Garage]::new($capacity)
        $refused = 0
        for ($k = 0; $k -lt $arriving; $k++) { if (-not $garage.Arrive()) { $refused++ } }
        for ($k = 0; $k -lt $leaving;  $k++) { [void]$garage.Leave() }
        $admitted = [Math]::Min($arriving, $capacity)
        $expected = '{0}/{1}' -f ($admitted - [Math]::Min($leaving, $admitted)), ($arriving - $admitted)
        $got      = '{0}/{1}' -f $garage.occupied, $refused
        $mark     = if ($got -eq $expected) { '  ' } else { $mismatch_n++; '!!' }
        $key = "$capacity,$arriving"
        if (-not $row_db.Contains($key)) { $row_db[$key] = [System.Collections.Generic.List[string]]::new() }
        $row_db[$key].Add("$got$mark")
    }
    foreach ($capacity in $value_list[0]) {
        Out-Py ('capacity {0}   {1}' -f $capacity, (@(foreach ($l in $value_list[2]) { 'leave {0,-3}' -f $l }) -join '  ').TrimEnd())
        foreach ($arriving in $value_list[1]) {
            Out-Py ('  arrive {0}   {1}' -f $arriving, (@(foreach ($c in $row_db["$capacity,$arriving"]) { '{0,-9}' -f $c }) -join '  ')).TrimEnd()
        }
    }
    Out-Py ('cases {0}, differing from the model ((mismatches: {1}))' -f ($row_db.Count * $value_list[2].Count), $mismatch_n)
}

# _____________________________________________________________________________
# random -- a deterministic stream of arrivals and departures
#
<# RETURN: nothing. Prints the summary of 1000 drawn cars, model-checked. #>
function random_stream {
    $stream    = [DeterministicStream]::new(4711)
    $garage    = [Garage]::new(5)
    $model     = 0
    $count_db  = @{ arrive = 0; refused = 0; leave = 0; empty = 0 }
    $histogram = [int[]]::new(6)
    $mismatch_n = 0
    $strip = [System.Text.StringBuilder]::new()
    for ($i = 0; $i -lt 1000; $i++) {
        if ($stream.Coin(0.55)) {
            $count_db.arrive++
            if (-not $garage.Arrive()) { $count_db.refused++ }
            $model = [Math]::Min(5, $model + 1)
            [void]$strip.Append('+')
        } else {
            $count_db.leave++
            if (-not $garage.Leave()) { $count_db.empty++ }
            $model = [Math]::Max(0, $model - 1)
            [void]$strip.Append('-')
        }
        if ($garage.occupied -ne $model) { $mismatch_n++ }
        $histogram[$garage.occupied]++
    }
    Out-Py "seed 4711, garage of 5, 1000 cars drawn: '+' arrives, '-' leaves"
    Out-Py ('first 60: {0}' -f $strip.ToString().Substring(0, 60))
    Out-Py ('arrivals {0}, refused {1}; departures {2}, from an empty garage {3}' -f $count_db.arrive, $count_db.refused, $count_db.leave, $count_db.empty)
    Out-Py 'cars inside after each event:'
    for ($n = 0; $n -lt 6; $n++) { Out-Py ('    {0}  {1,4}  {2}' -f $n, $histogram[$n], ('#' * [Math]::Floor($histogram[$n] / 10))) }
    Out-Py ('steps differing from the model ((mismatches: {0}))' -f $mismatch_n)
}

# _____________________________________________________________________________
# race -- two gates on drawn timelines
#
#  A gate on a timeline: its first tick checks, its second admits.
class Gate {
    [string]   $timeline
    [string]   $name
    [object]   $garage
    [bool]     $atomic
    [System.Collections.Generic.List[string]] $log
    [int]      $step
    [bool]     $saw_free

    <# RETURN: Gate 'name' on 'timeline' at 'garage', its events appended to 'log'. #>
    Gate([string]$name, [string]$timeline, [object]$garage, [bool]$atomic, [System.Collections.Generic.List[string]]$log) {
        $this.timeline, $this.name = $timeline, $name
        $this.garage, $this.atomic, $this.log = $garage, $atomic, $log
        $this.step, $this.saw_free = 0, $false
    }

    <# RETURN: nothing. Performs the gate's next step at 'pseudo_time'. #>
    [void] Fire([int]$pseudo_time) {
        if ($this.step -eq 0 -and $this.atomic) {
            $this.saw_free = $this.garage.Arrive()
            $this.log.Add($(if ($this.saw_free) { "$($this.name) checks+admits" } else { "$($this.name) refuses" }))
        } elseif ($this.step -eq 0) {
            $this.saw_free = $this.garage.Free() -gt 0
            $this.log.Add("$($this.name) sees $($this.garage.Free()) free")
        } elseif ($this.atomic) {
            $this.log.Add($(if ($this.saw_free) { "$($this.name) opens" } else { "$($this.name) stays shut" }))
        } elseif ($this.saw_free) {
            $this.garage.occupied++                         # the naive admit
            $this.log.Add("$($this.name) admits")
        } else {
            $this.log.Add("$($this.name) refuses")
        }
        $this.step++
    }

    <# RETURN: nothing; a gate has nothing to wind down. #>
    [void] OnTermination([int]$end_tick) { }
}

<#
RETURN: list of @(string, string), every pair of timelines in four ticks in
        which each of two gates fires twice, never at the same tick: gate
        A's and gate B's.
#>
function interleaving_list {
    $line = { param($x, $y) -join @(foreach ($t in 0..3) { if ($t -eq $x -or $t -eq $y) { '1' } else { ' ' } }) }
    $result = [System.Collections.Generic.List[object]]::new()
    foreach ($point in [SpaceIterator]::Do(@((0..3), (0..3), (0..3), (0..3)))) {
        $a1, $a2, $b1, $b2 = $point
        if ($a1 -lt $a2 -and $b1 -lt $b2 -and @($a1, $a2, $b1, $b2 | Sort-Object -Unique).Count -eq 4) {
            $result.Add(@((& $line $a1 $a2), (& $line $b1 $b2)))
        }
    }
    return , $result
}

<# RETURN: nothing. Plays every interleaving of two gates at one space. #>
function race([bool]$atomic) {
    Out-Py 'one free space, two gates, one car at each; timelines: a digit fires'
    Out-Py '    gate A  gate B  what happens                                    inside'
    $overbooked_n = 0
    $all = interleaving_list
    foreach ($pair in $all) {
        $garage, $event_list = [Garage]::new(1), [System.Collections.Generic.List[string]]::new()
        $gate_list = @([Gate]::new('A', $pair[0], $garage, $atomic, $event_list),
                       [Gate]::new('B', $pair[1], $garage, $atomic, $event_list))
        [TriggerDispatcher]::new($gate_list).Run()
        $mark = if ($garage.occupied -gt $garage.capacity) { $overbooked_n++; '!!' } else { '  ' }
        Out-Py ('    "{0}"  "{1}"  {2,-46}  {3} {4}' -f $pair[0], $pair[1], ($event_list -join ', '), $garage.occupied, $mark).TrimEnd()
    }
    Out-Py ('interleavings overbooking the garage ((overbooked: {0})) of {1}' -f $overbooked_n, $all.Count)
}

[HwutRunner]::new(@{
    argv       = @($PSCommandPath) + $args
    title      = "Demo: a garage's space counter -- a space, a stream and races, generated;"
    choice_map = @{
        'space'       = { space }
        'random'      = { random_stream }
        'race-naive'  = { race $false }
        'race-atomic' = { race $true }
    }
}).Run()
