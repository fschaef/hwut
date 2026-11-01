# @hwut {
#     title      = "A terminal's screen read by a test: libvterm through P/Invoke."
#     choices {
#         attributes { features = ["ps-vterm"] }
#         colours    { features = ["ps-vterm"] }
#         events     { features = ["ps-vterm"] }
#         keys       { features = ["ps-vterm"] }
#         missing    { features = ["ps-vterm"] }
#         regions    { features = ["ps-vterm"] }
#         screen     { features = ["ps-vterm"] }
#         text       { features = ["ps-vterm"] }
#         unnoticed  { features = ["ps-vterm"] }
#     }
#     caps        { file_size_mb = 2097152 }
#     interactive = true
# }
#
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#_____________________________________________________________________________
#
# PURPOSE: The PowerShell port of 'python/TEST/test-hwut_vterm.py', choice for
#          choice, held against its GOOD files by '.link'. WANTS 'libvterm';
#          where it is missing every choice but 'missing' says so in one line.
#          The two applications run on the pseudo-terminal are the Python
#          test's own -- the system under test -- run by 'python3 -c'.
#
# IN ONE PROCESS: the interactive session runs every choice in this process,
# so 'missing' puts HWUT_LIBVTERM and the library back as it found them --
# the choices after it ('regions', 'screen', ...) probe the real library.
#_____________________________________________________________________________
using module ../hwut_runner.psm1
using module ../hwut_pytext.psm1
using module ../hwut_vterm.psm1

$ESC    = "`e"
$PYTHON = 'python3'

<# RETURN: string, a colour as Python prints the tuple, or 'None'. #>
function colourText([object]$rgb) { if ($null -eq $rgb) { 'None' } else { [PyText]::TupleRepr($rgb) } }

<# RETURN: nothing; every row that holds something, framed, then the cursor, on the pipeline. #>
function shown([VtermScreen]$screen) {
    $lineList = $screen.LineList()
    for ($row = 0; $row -lt $lineList.Count; $row++) { if ($lineList[$row]) { "    $row |$($lineList[$row])|" } }
    "    cursor $([PyText]::TupleRepr($screen.Cursor()))"
}

<# RETURN: scriptblock, 'f' run on a library that is there; one line where it is not. #>
function probe([scriptblock]$f) {
    return {
        try { & $f } catch [LibraryMissing] { "NOT PROBED: $($_.Exception.Message)" }
    }.GetNewClosure()
}

<# RETURN: byte[], 'text' as UTF-8. #>
function utf8([string]$text) { return ,[System.Text.UTF8Encoding]::new($false).GetBytes($text) }

$text = {
    [VtermScreen]::new(4, 12).Use({ param($screen)
        '-- plain, then carriage return and line feed'
        $null = $screen.Feed((utf8 "hello`r`nworld"))
        shown $screen
    })
    [VtermScreen]::new(4, 12).Use({ param($screen)
        '-- UTF-8: two bytes, one cell; a wide character, two'
        $null = $screen.Feed((utf8 'ä日x'))
        shown $screen
        for ($column = 0; $column -lt 4; $column++) {
            $cell = $screen.Cell(0, $column)
            '    column {0}: {1,-6} width {2}' -f $column, [PyText]::StrRepr($cell.text), $cell.width
        }
    })
    [VtermScreen]::new(3, 5).Use({ param($screen)
        '-- seven characters on five columns: the line wraps'
        $null = $screen.Feed((utf8 'abcdefg'))
        shown $screen
    })
    [VtermScreen]::new(2, 4).Use({ param($screen)
        '-- a str is sent as UTF-8; the bytes taken are counted'
        "    taken: $($screen.Feed('aä'))"
        '-- a place off the screen'
        try { $null = $screen.Cell(2, 0) } catch [IndexError] { "    IndexError: $($_.Exception.Message)" }
    })
}

$screen = {
    [VtermScreen]::new(5, 20).Use({ param($screen)
        "-- three lines, then '<esc>[2;4H' (it counts from 1) and 'X'"
        $null = $screen.Feed((utf8 "first line`r`nsecond line`r`nthird line"))
        $null = $screen.Feed((utf8 ($ESC + '[2;4H' + 'X')))
        shown $screen
        '-- erase to the end of that line'
        $null = $screen.Feed((utf8 ($ESC + '[K')))
        shown $screen
        '-- clear the screen, home, one word'
        $null = $screen.Feed((utf8 ($ESC + '[2J' + $ESC + '[H' + 'clean')))
        shown $screen
    })
}

$attributes = {
    [VtermScreen]::new(3, 20).Use({ param($screen)
        $nameList = [Vterm]::ATTRIBUTE_NAME_LIST
        for ($k = 0; $k -lt $nameList.Count; $k++) {
            $null = $screen.Feed("$ESC[$([Vterm]::ATTRIBUTE_SGR_LIST[$k])m$($nameList[$k][0])$ESC[0m")
        }
        '-- one cell per attribute, set by its own code'
        for ($column = 0; $column -lt $nameList.Count; $column++) {
            $cell = $screen.Cell(0, $column)
            #  'conceal' IS NOT KNOWN TO EVERY LIBRARY: said, not pinned.
            $said = $cell.AttributeText(); if (-not $said) { $said = '(none)' }
            if ($nameList[$column] -ceq 'conceal') { $said = 'conceal, or (none) on libvterm 0.1' }
            "    $([PyText]::StrRepr($cell.text))  $said"
        }
        '-- bold, underline and reverse at once; then reset'
        $null = $screen.Feed("`r`n$ESC[1;4;7mA$ESC[0mB")
        foreach ($column in 0, 1) {
            $cell = $screen.Cell(1, $column)
            $said = $cell.AttributeText(); if (-not $said) { $said = '(none)' }
            "    $([PyText]::StrRepr($cell.text))  $said"
        }
        '-- double underline (SGR 21) is underlined'
        $null = $screen.Feed("$ESC[21mD")
        "    $([PyText]::StrRepr('D'))  $($screen.Cell(1, 2).AttributeText())"
    })
}

$colours = {
    [VtermScreen]::new(2, 20).Use({ param($screen)
        $null = $screen.Feed("d$ESC[31mr$ESC[0m$ESC[38;5;196mp$ESC[0m$ESC[38;2;10;20;30mt$ESC[0m")
        $null = $screen.Feed("$ESC[48;2;1;2;3mb$ESC[0m")
        $column = 0
        foreach ($what in 'default', 'indexed 31', 'palette 196', 'direct 10;20;30', 'background 1;2;3') {
            $cell = $screen.Cell(0, $column)
            #  THE EIGHT NAMED COLOURS ARE THE LIBRARY'S OWN PALETTE: that
            #  one is a colour and mostly red is the claim, not its shade.
            if ($what -ceq 'indexed 31') {
                $red, $green, $blue = $cell.foreground
                $said = "fg mostly red: $([PyText]::BoolText($red -gt 2 * [Math]::Max($green, $blue)))"
            } else {
                $said = "fg $(colourText $cell.foreground)  bg $(colourText $cell.background)"
            }
            '    {0,-18} {1}  {2}' -f $what, [PyText]::StrRepr($cell.text), $said
            $column++
        }
    })
}

#  THE APPLICATION UNDER OBSERVATION -- the Python test's own: it says what
#  it sees, asks the terminal where the cursor is, then names every key
#  until 'q'.
$SEEING_APP = @'

import os, sys, tty, termios
print("streams are terminals: %s %s %s"
      % (sys.stdin.isatty(), sys.stdout.isatty(), sys.stderr.isatty()))
try:    os.close(os.open("/dev/tty", os.O_RDWR)); print("controlling terminal: yes")
except OSError: print("controlling terminal: no")
print("size: %d columns, %d rows" % tuple(os.get_terminal_size()))
print("TERM=%s COLUMNS=%s" % (os.environ.get("TERM"), os.environ.get("COLUMNS")))
old = termios.tcgetattr(0); tty.setraw(0)
sys.stdout.write("\x1b[6;9H\x1b[6n"); sys.stdout.flush()
reply = b""
while not reply.endswith(b"R"): reply += os.read(0, 1)
sys.stdout.write("\r\x1b[7;1Hthe terminal answered: %r" % reply); sys.stdout.flush()
while True:
    key = os.read(0, 32)
    sys.stdout.write("\x1b[9;1H\x1b[Kread: %r" % key); sys.stdout.flush()
    if key == b"q": break
termios.tcsetattr(0, termios.TCSADRAIN, old)
print("\r\nleaving"); sys.exit(3)
'@

#  AN APPLICATION WITH A HEAD, A BODY AND A FOOT -- the Python test's own:
#  'n' counts in the body, 'f' rewrites the foot, 'r' redraws everything
#  unchanged, 'q' leaves.
$DRAWING_APP = @'

import os, sys, tty, termios
old = termios.tcgetattr(0); tty.setraw(0)
count, foot = 0, "q=quit"
def draw():
    out = "\x1b[2J\x1b[1;1H\x1b[7m the head \x1b[0m"
    out += "\x1b[3;1Hcount: %d\x1b[4;1H(press n)" % count
    out += "\x1b[8;1H%s" % foot
    sys.stdout.write(out); sys.stdout.flush()
draw()
while True:
    key = os.read(0, 1)
    if   key == b"n": count += 1
    elif key == b"f": foot = "q=quit  f=pressed"
    elif key == b"q": break
    draw()
termios.tcsetattr(0, termios.TCSADRAIN, old)
'@

$unnoticed = {
    $env:COLUMNS = '300'
    [VtermTerminal]::new(10, 44).Use({ param($terminal)
        "-- still running after its first screen: $([PyText]::BoolText($terminal.Run(@($PYTHON, '-c', $SEEING_APP))))"
        shown $terminal
        $null = $terminal.Send('q')
        "-- after 'q': exit status $([PyText]::NoneOr($terminal.Wait()))"
        shown $terminal
    })
}

$keys = {
    [VtermTerminal]::new(10, 44).Use({ param($terminal)
        $state = @{ pressed = '(start)' }
        $terminal.Region('read', 8)
        $terminal.OnChange({ param($name, $lineList) '    {0,-22} {1}' -f $state.pressed, $lineList[0] }.GetNewClosure())
        $null = $terminal.Run(@($PYTHON, '-c', $SEEING_APP))
        foreach ($press in @(@('up'), @('enter'), @('tab'), @('escape'), @('f5'), @('delete'),
                             @('c', 'ctrl'), @('x', 'alt'), @('up', 'shift'))) {
            $key = $press[0]
            $modifierList = [string[]]@($press | Select-Object -Skip 1)
            $state.pressed = (@($modifierList) + @($key)) -join ' '
            $null = $terminal.Press($key, $modifierList)
        }
        $state.pressed = "send 'ä'"
        $null = $terminal.Send('ä')
        $state.pressed = "send 'q'"
        $null = $terminal.Send('q')
        $null = $terminal.Wait()
    })
}

$regions = {
    #  A LONGER PAUSE THAN THE DEFAULT: three redraws typed at once must be
    #  ONE report on a loaded machine too.
    [VtermTerminal]::new(8, 30, 0.3).Use({ param($terminal)
        $terminal.Region('head', 0)
        $terminal.Region('body', 2, 2)
        $terminal.Region('foot', -1)
        $terminal.OnChange({ param($name, $lineList) '    changed  {0,-5} {1}' -f $name, [PyText]::ListRepr($lineList, $true) })
        foreach ($step in @(@('run',                         { $terminal.Run(@($PYTHON, '-c', $DRAWING_APP)) }),
                            @("'n'",                         { $terminal.Send('n') }),
                            @("'n'",                         { $terminal.Send('n') }),
                            @("'r': a redraw, nothing new",  { $terminal.Send('r') }),
                            @("'f'",                         { $terminal.Send('f') }),
                            @("'nnn', typed at once",        { $terminal.Send('nnn') }),
                            @("'q'",                         { $terminal.Send('q') }))) {
            "-- $($step[0])"
            $null = & $step[1]
        }
        "-- exit status $([PyText]::NoneOr($terminal.Wait())); a region asked by name: $([PyText]::ListRepr($terminal.RegionText('body'), $true))"
        try { $null = $terminal.RegionText('nosuch') } catch [KeyError] { "-- no such region: KeyError $($_.Exception.Message)" }
    })
}

$events = {
    [VtermTerminal]::new(4, 20).Use({ param($terminal)
        $terminal.OnEvent({ param($event) "    $event" })
        foreach ($step in @(@("'ab'",                         'ab'),
                            @("a line feed and 'c'",          "`r`nc"),
                            @('the cursor to row 4, hidden',  ($ESC + '[4;1H' + $ESC + '[?25l')),
                            @('the alternate screen',         ($ESC + '[?1049h')),
                            @('the bell',                     "`a"),
                            @('nothing that draws: a reset of attributes', ($ESC + '[0m')))) {
            "-- fed: $($step[0])"
            $null = $terminal.Feed($step[1])
        }
        '-- asked where the cursor is, nobody running: the answer waits'
        $null = $terminal.Feed($ESC + '[2;5H' + $ESC + '[6n')
        "    answer() = $([PyText]::BytesRepr($terminal.Answer()))"
        '-- a key pressed with nobody running'
        $null = $terminal.Press('f1', @(), 0)
        "    answer() = $([PyText]::BytesRepr($terminal.Answer()))"
    })
}

$missing = {
    $given = [System.Environment]::GetEnvironmentVariable([Vterm]::LIBRARY_VARIABLE)
    [System.Environment]::SetEnvironmentVariable([Vterm]::LIBRARY_VARIABLE, '/nowhere/libvterm.so')
    [Vterm]::ForgetLibrary()
    try {
        $null = [VtermScreen]::new()
        'a Screen stands on a library that is not there'
    } catch [LibraryMissing] {
        #  THE SYSTEM'S OWN WORDS for the failed load are left out; what this
        #  module says -- the line, and the way to install -- stands.
        $lineList = $_.Exception.Message.Split("`n")
        "LibraryMissing: $(($lineList[0] -split ' -- ')[0])"
        $lineList | Select-Object -Skip 1
    } finally {
        #  ONE PROCESS FOR THE SESSION: the next choice finds the library again.
        [System.Environment]::SetEnvironmentVariable([Vterm]::LIBRARY_VARIABLE, $given)
        [Vterm]::ForgetLibrary()
    }
}

[HwutRunner]::new(@{
    argv       = @($PSCommandPath) + $args
    title      = "A terminal's screen read by a test: libvterm through P/Invoke."
    choice_map = @{
        text       = (probe $text)
        screen     = (probe $screen)
        attributes = (probe $attributes)
        colours    = (probe $colours)
        unnoticed  = (probe $unnoticed)
        keys       = (probe $keys)
        regions    = (probe $regions)
        events     = (probe $events)
        missing    = $missing
    }
}).Run()
