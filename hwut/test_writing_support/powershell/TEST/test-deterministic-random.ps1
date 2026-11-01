# @hwut {
#     title      = "DeterministicStream RNG and SelectionMarker spread"
#     choices {
#         gauss      { features = ["ps-random"] }
#         primitives { features = ["ps-random"] }
#         ranges     { features = ["ps-random"] }
#         sample     { features = ["ps-random"] }
#         seed_sweep { features = ["ps-random"] }
#         select     { features = ["ps-random"] }
#         unchosen   { features = ["ps-random"] }
#     }
#     caps        { file_size_mb = 2097152 }
#     interactive = true
# }
#
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#_____________________________________________________________________________
#
# PURPOSE: The PowerShell port of 'python/TEST/test-deterministic-random.py',
#          choice for choice. Its GOOD files are the Python test's, by
#          '.link': the two modules owe the same stream, byte for byte.
#_____________________________________________________________________________
using module ../hwut_runner.psm1
using module ../hwut_pytext.psm1
using module ../deterministic_random.psm1

$SEED = 0x42

#  THE ONE PLACE THE LIBM PATH IS TOLERATED, as in the Python test.
$TOLERANCE_REGION_BEGIN = '##! table numeric={1:1e-12}'
$REGION_END             = '####'

<# RETURN: nothing; a section heading on the pipeline. #>
function banner([string]$label) { ''; "--- $label ---" }

<# RETURN: DeterministicStream, fresh on SEED. #>
function stream { [DeterministicStream]::new($SEED) }

<# RETURN: string[], 'n' results of the script block 'f' (called with the index). #>
function times([int]$n, [scriptblock]$f) { for ($i = 0; $i -lt $n; $i++) { & $f $i } }

$primitives = {
    banner 'next_int(0, 1000000) -- first 20'
    $s = stream
    for ($i = 0; $i -lt 20; $i++) { '[{0:00}] {1}' -f $i, $s.NextInt(0, 1000000) }

    banner 'next_float -- first 10 (full precision)'
    $s = stream
    for ($i = 0; $i -lt 10; $i++) { '[{0:00}] {1}' -f $i, [PyText]::FloatRepr($s.NextFloat()) }

    banner 'coin(0.5) -- 40 draws'
    $s = stream
    (times 40 { if ($s.Coin(0.5)) { 'T' } else { 'F' } }) -join ' '
}

$ranges = {
    banner 'next_int(0, 9) -- 30 draws'
    $s = stream
    (times 30 { $s.NextInt(0, 9) }) -join ' '

    banner 'next_int(5, 5) -- degenerate range returns the bound'
    $s = stream
    (times 5 { $s.NextInt(5, 5) }) -join ' '

    banner 'next_int(-3, 3) -- spanning zero'
    $s = stream
    (times 20 { '{0:+0;-0;+0}' -f $s.NextInt(-3, 3) }) -join ' '
}

$gauss = {
    banner 'gauss(0, 1) -- 10 draws (full precision)'
    $s = stream
    $TOLERANCE_REGION_BEGIN
    for ($i = 0; $i -lt 10; $i++) { '[{0:00}] {1}' -f $i, [PyText]::FloatRepr($s.Gauss(0.0, 1.0)) }
    $REGION_END

    banner 'gauss(0, 1) clamped to [-1, 1]'
    $s = stream
    $TOLERANCE_REGION_BEGIN
    for ($i = 0; $i -lt 10; $i++) { '[{0:00}] {1}' -f $i, [PyText]::FloatRepr($s.Gauss(0.0, 1.0, -1.0, 1.0)) }
    $REGION_END

    banner 'gauss_int(100, 15) -- 20 draws'
    $s = stream
    (times 20 { $s.GaussInt(100.0, 15.0) }) -join ' '
}

$sample = {
    banner 'sample_indices(10, 10) -- full permutation'
    $s = stream
    [PyText]::ListRepr($s.SampleIndices(10, 10))

    banner 'sample_indices(20, 5) -- partial draw'
    $s = stream
    [PyText]::ListRepr($s.SampleIndices(20, 5))

    banner 'choice from a list -- 20 draws'
    $s = stream
    $pool = @('alpha', 'beta', 'gamma', 'delta', 'epsilon')
    (times 20 { $s.Choice($pool) }) -join ' '

    banner 'sample(list, 4) -- unique elements'
    $s = stream
    [PyText]::ListRepr($s.Sample([object[]]'ABCDEFGH'.ToCharArray(), 4), $true)
}

$select = {
    banner 'select over a list -- 20 draws'
    $s = stream
    $pool = [System.Collections.Generic.List[string]]@('a', 'b', 'c', 'd')
    (times 20 { $s.Select($pool) }) -join ' '

    banner 'select over a tuple -- 12 draws'
    $s = stream
    $branches = [string[]]@('p', 'q', 'r')
    (times 12 { $s.Select($branches) }) -join ' '
}

$unchosen = {
    banner 'stable pool -- three full cycles of 4 elements'
    $s = stream
    $pool = @('a', 'b', 'c', 'd')
    $m = [SelectionMarker]::new()
    (times 12 { $s.SelectUnchosen($pool, $m) }) -join ' '

    banner 'FRESH container each call -- identical to the stable pool above'
    $s = stream
    $m = [SelectionMarker]::new()
    (times 12 { $s.SelectUnchosen(@('a', 'b', 'c', 'd'), $m) }) -join ' '

    banner 'sub-pool coherence -- draw from [a,b] then the full [a,b,c,d]'
    $s = stream
    $m = [SelectionMarker]::new()
    $full = @('a', 'b', 'c', 'd')
    $sub  = @('a', 'b')
    $first = $s.SelectUnchosen($sub, $m)
    $rest  = times 3 { $s.SelectUnchosen($full, $m) }
    "first(from sub): $first  then(from full): $($rest -join ' ')"

    banner 'reset() restarts the cycle'
    $s = stream
    $pool = @('a', 'b', 'c', 'd')
    $m = [SelectionMarker]::new()
    $before = times 4 { $s.SelectUnchosen($pool, $m) }
    $m.Reset()
    $after  = times 4 { $s.SelectUnchosen($pool, $m) }
    "before reset: $($before -join ' ')"
    "after  reset: $($after -join ' ')"
}

$seed_sweep = {
    banner 'first next_int(0, 1000000) per seed 0..15'
    for ($seed = 0; $seed -lt 16; $seed++) {
        $s = [DeterministicStream]::new($seed)
        'seed={0,2} -> {1}' -f $seed, $s.NextInt(0, 1000000)
    }
}

[HwutRunner]::new(@{
    argv       = @($PSCommandPath) + $args
    title      = 'DeterministicStream RNG and SelectionMarker spread'
    choice_map = @{
        primitives = $primitives
        ranges     = $ranges
        gauss      = $gauss
        sample     = $sample
        select     = $select
        unchosen   = $unchosen
        seed_sweep = $seed_sweep
    }
}).Run()
