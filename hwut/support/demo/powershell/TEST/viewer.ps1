#! /usr/bin/env pwsh
<#
______________________________________________________________________________
A TERMINAL FILE VIEWER -- the program 'screen.ps1' tests; no test itself.

    pwsh viewer.ps1 <file>

Full screen, on the terminal's alternate screen: a title bar (reverse
video), as many lines of the file as fit, and a status line: the keys
flush left, the lines shown flush right. Keys: 'j' or down one line
further, 'k' or up one line back, 'q' quits.

The keys are read by [Console]::ReadKey, which puts the terminal into raw
mode while it waits and gives the arrow keys as ConsoleKey, whichever of
the two encodings the terminal sends ('ESC [ B' or 'ESC O B'). The screen
is written as one string per draw: the terminal sees one burst.
______________________________________________________________________________
#>
$ErrorActionPreference = 'Stop'

<# RETURN: string, the whole screen with the file's line 'top' first, as escape sequences. #>
function draw([string]$name, [string[]]$line_list, [int]$top, [int]$row_n, [int]$column_n) {
    $body_n = $row_n - 2
    $shown  = @($line_list | Select-Object -Skip $top -First $body_n)
    $out = [System.Text.StringBuilder]::new()
    [void]$out.Append("`e[H`e[2J")
    $title = (' ' + $name).PadRight($column_n).Substring(0, $column_n)
    [void]$out.Append("`e[7m$title`e[0m`r`n")
    foreach ($line in $shown) { [void]$out.Append($line.Substring(0, [Math]::Min($line.Length, $column_n)) + "`r`n") }
    [void]$out.Append("`r`n" * ($body_n - $shown.Count))
    $where = 'lines {0}-{1} of {2}' -f ($top + 1), ($top + $shown.Count), $line_list.Count
    $keys  = 'j k q'
    [void]$out.Append(("`e[{0};1H{1}{2}" -f $row_n, $keys, $where.PadLeft($column_n - 1 - $keys.Length)))
    return $out.ToString()
}

<# RETURN: int, 0 once 'q' was pressed. #>
function main([string]$path) {
    $line_list = [string[]]@(([System.IO.File]::ReadAllText($path) -split "`n") | Select-Object -SkipLast 1)
    $column_n, $row_n = [Console]::WindowWidth, [Console]::WindowHeight
    $name = [System.IO.Path]::GetFileName($path)
    $stdout = [Console]::OpenStandardOutput()
    $write  = { param($text) $b = [System.Text.Encoding]::UTF8.GetBytes($text); $stdout.Write($b, 0, $b.Length); $stdout.Flush() }
    #  The terminal is taken over (raw, no echo) BEFORE the first screen is
    #  drawn: a key that comes while pwsh still compiles is not echoed.
    [Console]::TreatControlCAsInput = $true
    [void][Console]::KeyAvailable
    $top   = 0
    $enter = "`e[?1049h"                 # the alternate screen, in the first burst
    try {
        while ($true) {
            & $write ($enter + (draw $name $line_list $top $row_n $column_n))
            $enter = ''
            $key = [Console]::ReadKey($true)
            if     ($key.KeyChar -ceq 'q')                                     { break }
            elseif ($key.KeyChar -ceq 'j' -or $key.Key -eq 'DownArrow')        { $top = [Math]::Min($top + 1, [Math]::Max(0, $line_list.Count - ($row_n - 2))) }
            elseif ($key.KeyChar -ceq 'k' -or $key.Key -eq 'UpArrow')          { $top = [Math]::Max($top - 1, 0) }
        }
    } finally {
        & $write "`e[?1049l"
    }
    return 0
}

exit (main $args[0])
