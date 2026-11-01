#! /usr/bin/env pwsh
#
# @hwut {
#     title   = "Demo: a recursive build, serial and parallel -- one summary, by a pype system"
#     pype    = "build.pypes"
#     same    = true
#     choices = ["serial", "parallel"]
#     features = ["pype-in-header", "pype-system", "same-nominal", "choices-as-list",
#                 "pype-push-pop", "pype-entry-exit", "pype-import", "pype-repeat-group",
#                 "pype-quantity", "pype-anchors-globs-flush"]
#     tolerance { constraints = ["compile < 5 s", "breaches == 0"] }
# }
#
<#
______________________________________________________________________________
SUBJECT  the log of a recursive build -- configure, then the directories
         'lib', 'app' and, inside 'app', 'app/plugins' -- and the summary
         a pype system makes of it.
REQUIREMENT  A parallel build builds what the serial build builds: the same
             sources, the same warnings, the same archives and the same
             program, linked from the same parts.

The application only REPORTS the build as it happens, as 'make -w' would.
The header's 'pype = "build.pypes"' puts a SYSTEM of two pype scripts
between it and the comparison (hwut runs it; the application prints no
'<hwut-end>'):

    build.pypes       --> normalise.pype         stdin to the first
                      normalise.pype --> build.pype
    normalise.pype    a parallel build tags each line with its job,
                      'job2: cc -c ...'; the tag goes, every other line
                      passes unchanged ('flush')
    build.pype        the summary, sorted -- see its own comments: modes
                      pushed on 'Entering directory' and popped on
                      'Leaving' (nested: 'app/plugins' inside 'app'),
                      '<entry>'/'<exit>' around each, a vocabulary
                      imported from 'compiler.pype', a repeat group over
                      the parts of a link, durations read as quantities

'same = true': BOTH CHOICES SHARE ONE GOOD, 'GOOD/build.ps1.txt'. Serial or
parallel, the summary must be the same -- that is the requirement, and
the header says it once. 'choices' is a list: no choice states anything
of its own.

The laws: the compile times sum to under 5 s ('((compile: ...))', in
s, whatever unit the log used), and nothing in the log broke the build's
grammar ('((breaches: 0))').

A HEADER'S PYPE READS THE OUTPUT AFTER THE RUN: the whole stream at once.
Time as the pype sees it -- 'pype.time()', 'tick:' -- is no time of the
build here; a pype that judges time is fed live ('protocol.sh slow').

THE TWO JOBS of 'parallel' are runspaces of 'ForEach-Object -Parallel'. A
runspace knows none of this script's functions: each is handed their text
('$BLOCK_FUNCTION_DB') and defines them anew.
______________________________________________________________________________
#>
. "$PSScriptRoot/hwut_support.ps1"

#  What each directory does: its sources, warnings and products.
$DIRECTORY_DB = @{
    'lib' = @{ source_list = @('lib/str.c', 'lib/num.c', 'lib/map.c')
               warning_db  = @{ 'lib/num.c' = "lib/num.c:14:9: warning: unused variable 'n'" }
               product     = 'ar rcs lib/libcore.a lib/str.o lib/num.o lib/map.o' }
    'app/plugins' =
             @{ source_list = @('app/plugins/png.c', 'app/plugins/svg.c')
               warning_db  = @{ 'app/plugins/svg.c' = "app/plugins/svg.c:3:1: warning: implicit declaration of 'xml_open'" }
               product     = 'ar rcs app/plugins/libplug.a app/plugins/png.o app/plugins/svg.o' }
    'app' = @{ source_list = @('app/main.c', 'app/cli.c')
               warning_db  = @{}
               product     = 'ld -o app/demo app/main.o app/cli.o lib/libcore.a app/plugins/libplug.a' }
}

<#
RETURN: string[], what building directory 'name' prints, its sources
        compiled in the time each takes.
#>
function compile_lines([string]$name) {
    $spec = $DIRECTORY_DB[$name]
    foreach ($source in $spec.source_list) {
        $took = 0.04 + 0.08 * (Get-Random -Minimum 0.0 -Maximum 1.0)
        Start-Sleep -Milliseconds ([int]($took * 1000))
        $spent = if ($took -lt 0.1) { '{0} ms' -f [Math]::Floor($took * 1000) } else { '{0:F2} s' -f $took }
        'cc -c {0} -o {1} (took {2})' -f $source, ($source.Substring(0, $source.Length - 2) + '.o'), $spent
        if ($spec.warning_db.Contains($source)) { $spec.warning_db[$source] }
    }
}

<#
RETURN: string[], the block 'make -w' prints for 'name' at 'level', the
        block of 'inner' nested before the product.
#>
function directory_block([string]$name, [int]$level, [string]$inner = '') {
    "make[$level]: Entering directory '$name'"
    compile_lines $name
    if ($inner) { directory_block $inner ($level + 1) }
    $DIRECTORY_DB[$name].product
    "make[$level]: Leaving directory '$name'"
}

$BLOCK_FUNCTION_DB = @{ compile_lines   = ${function:compile_lines}.ToString()
                        directory_block = ${function:directory_block}.ToString() }

<# RETURN: nothing. Prints what 'configure' prints, and that make enters the top directory. #>
function configure {
    Out-Py 'configure: checking for cc... cc'
    Out-Py 'configure: checking for ar... ar'
    Out-Py "make: Entering directory 'demo'"
}

<# RETURN: nothing. Builds one directory after the other. #>
function serial {
    configure
    foreach ($line in @(directory_block 'lib' 1) + @(directory_block 'app' 1 'app/plugins')) { Out-Py $line }
    Out-Py "make: Leaving directory 'demo'"
}

<#
RETURN: nothing. Builds 'lib' and 'app' at once. Each job prints its block
        whole when done ('make -O'), every line tagged with the job; which
        job finishes first is the scheduler's.
#>
function parallel {
    configure
    @(@(1, 'lib', ''), @(2, 'app', 'app/plugins')) | ForEach-Object -ThrottleLimit 2 -Parallel {
        [System.Globalization.CultureInfo]::CurrentCulture = [System.Globalization.CultureInfo]::InvariantCulture
        $DIRECTORY_DB = $using:DIRECTORY_DB
        foreach ($entry in ($using:BLOCK_FUNCTION_DB).GetEnumerator()) {
            Set-Item -Path "function:$($entry.Key)" -Value ([scriptblock]::Create($entry.Value))
        }
        $slot, $name, $inner = $_
        $block = @(directory_block $name 1 $inner)
        #  One write of the whole block: the synchronised writer keeps it whole.
        [Console]::Out.WriteLine((@(foreach ($line in $block) { "job${slot}: $line" }) -join "`n"))
    }
    Out-Py "make: Leaving directory 'demo'"
}

$CHOICE_LIST = @('serial', 'parallel')

$choice = if ($args.Count -gt 0) { [string]$args[0] } else { '' }
if ($CHOICE_LIST -cnotcontains $choice) {
    Out-Py ('choices: {0}' -f ($CHOICE_LIST -join ', '))
    exit 1
}
& $choice
