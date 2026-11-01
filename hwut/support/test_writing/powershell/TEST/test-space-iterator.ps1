# @hwut {
#     title      = "space_iterator: every combination of a parameter basis"
#     choices {
#         edges   { features = ["ps-space"] }
#         product { features = ["ps-space"] }
#     }
#     caps        { file_size_mb = 2097152 }
#     interactive = true
# }
#
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#_____________________________________________________________________________
#
# PURPOSE: The PowerShell port of 'python/TEST/test-space-iterator.py', held
#          against its GOOD files by '.link'.
#_____________________________________________________________________________
using module ../hwut_runner.psm1
using module ../space_iterator.psm1

<# RETURN: nothing. Section heading. #>
function banner([string]$label) { Out-Py ''; Out-Py "--- $label ---" }

<# RETURN: nothing. Every point of 'basis', one per line, then the count. #>
function points([object[]]$basis) {
    $n = 0
    foreach ($point in [SpaceIterator]::Do($basis)) {
        Out-Py "  ($($point -join ', '))"
        $n++
    }
    Out-Py "  $n point(s)"
}

$product = {
    banner '[0, 2, 4] x [otto, heinz] x [1, 2] -- 3 * 2 * 2 points'
    points @(@(0, 2, 4), @('otto', 'heinz'), @(1, 2))
}

$edges = {
    banner 'an EMPTY basis -- one point, the empty one'
    points @()
    banner 'a basis with an EMPTY dimension -- nothing'
    points @(@(1, 2), @(), @(3))
    banner 'ONE dimension -- its values one by one'
    points @(, @('a', 'b', 'c'))
}

[HwutRunner]::new(@{
    argv       = @($PSCommandPath) + $args
    title      = 'space_iterator: every combination of a parameter basis'
    choice_map = @{ product = $product; edges = $edges }
}).Run()
