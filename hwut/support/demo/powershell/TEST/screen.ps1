#! /usr/bin/env pwsh
#
# @hwut {
#     title     = "Demo: a terminal program's screen, as a person sees it"
#     tolerance { regions    = false
#                 comment    = false
#                 whitespace = false }
#     choices {
#         open   { features = ["terminal-screen", "screen-as-seen"] }
#         scroll { features = ["terminal-screen", "screen-as-seen"] }
#     }
# }
#
<#
______________________________________________________________________________
SUBJECT  the screen of 'viewer.ps1', a full-screen file viewer, run in a
         terminal of 9 rows and 40 columns and driven by its keys.
REQUIREMENT  The viewer shows a title bar in reverse video, the file's lines
             as they fit, and a status line -- the keys flush left, the lines
             shown flush right; 'j' and the down key go one line further,
             'k' one back.

hwut_vterm's 'VtermTerminal' runs the viewer on a pseudo-terminal: the
viewer cannot tell it from a real one. The test PRESSES KEYS and is told
what CHANGED: three regions are declared -- title, body, status -- and
after every key, once the viewer has gone quiet, each region whose text
changed is printed. A redraw that changes nothing is not told: the title
is told once.

THE SCREEN IS COMPARED AS A PERSON SEES IT -- three tolerances switched
off, in the header:

    regions = false     the file shown is a GOOD file of hwut, with a
                        '##! potpourri' ... '####' block. On this screen
                        those are characters, not a region to open.
    comment = false     '## ...' lines are characters too, not notes.
    whitespace = false  the status line's two halves stand flush left and
                        flush right: every blank between them counts. A
                        half moved by one column is red. (A line's leading
                        and trailing blanks are stripped all the same.)

libvterm must be installed ('apt install libvterm0'); where it is not, the
test prints why and probes nothing -- its output differs from GOOD and the
reason stands in the difference.

The viewer is a pwsh of its own, started by 'pwsh -NoProfile -File'. It is
told 'DOTNET_EnableWriteXorExecute=0' (RATIONALE DEMO-POWERSHELL-3): the
pseudo-terminal's process inherits this test's file cap.

CHOICES  open    the viewer opened, then quit.
         scroll  down, down, 'j', then 'k': three lines on, one back.
______________________________________________________________________________
#>
. "$PSScriptRoot/hwut_support.ps1" hwut_vterm

$SAMPLE = @'
## demo.py race -- three workers
start
##! potpourri
worker B done: 5 jobs
worker A done: 3 jobs
worker C done: 2 jobs
####
all joined
## the order between the markers is
## free; the lines are not.

'@ -replace "`r", ''

<# RETURN: nothing. Prints one region that changed, its rows as they stand on the screen, from the first column. #>
$show = {
    param($name, $line_list)
    Out-Py "-- $name"
    foreach ($line in $line_list) { Out-Py $line }
}

<# RETURN: nothing. Runs the viewer on the sample, presses 'key_list', quits, and prints what changed after each step. #>
function view([string[]]$key_list) {
    $path = Join-Path $PSScriptRoot 'TMP/race.txt'
    [void](New-Item -ItemType Directory -Force -Path (Split-Path $path))
    [System.IO.File]::WriteAllText($path, $SAMPLE)
    $environment = @{ DOTNET_EnableWriteXorExecute = '0'; POWERSHELL_TELEMETRY_OPTOUT = '1' }
    foreach ($entry in [Environment]::GetEnvironmentVariables().GetEnumerator()) {
        if (-not $environment.Contains($entry.Key)) { $environment[$entry.Key] = $entry.Value }
    }
    [VtermTerminal]::new(9, 40).Use({ param($terminal)
        $terminal.Region('title',  0)
        $terminal.Region('body',   1, 7)
        $terminal.Region('status', -1)
        $terminal.OnChange($show)
        Out-Py '> viewer.ps1 race.txt'
        $pwsh = (Get-Process -Id $PID).Path
        [void]$terminal.Run(@($pwsh, '-NoProfile', '-NonInteractive', '-File', (Join-Path $PSScriptRoot 'viewer.ps1'), $path), $environment, $null, 10.0)
        #  .NET writes the keypad mode ('ESC [?1h ESC =') as pwsh starts, long
        #  before the viewer's first screen: 'Run' hears that, and the quiet
        #  after it. The screen is waited for -- by what it must show.
        [void]$terminal.Expect('lines 1-', 10.0)
        $said = $terminal.Cell(0, 1).AttributeText()
        Out-Py ('title bar: {0}' -f $(if ($said) { $said } else { 'plain' }))
        foreach ($key in $key_list) {
            Out-Py "> $key"
            if ($key.Length -eq 1) { [void]$terminal.Send($key) }
            else                   { [void]$terminal.Press($key) }
        }
        [void]$terminal.Send('q')
        Out-Py ('> q -- exit status {0}' -f $terminal.Wait())
    })
}

$CHOICE_DB = [ordered]@{ open = @(); scroll = @('down', 'down', 'j', 'k') }

$choice = if ($args.Count -gt 0) { [string]$args[0] } else { '' }
if (@($CHOICE_DB.Keys) -cnotcontains $choice) {
    Out-Py ('choices: {0}' -f (@($CHOICE_DB.Keys) -join ', '))
    exit 1
}
try {
    view $CHOICE_DB[$choice]
} catch [LibraryMissing] {
    Out-Py $_.Exception.Message
    exit 1
}
Out-Py '<hwut-end>'
