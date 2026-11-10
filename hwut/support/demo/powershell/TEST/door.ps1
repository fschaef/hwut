#! /usr/bin/env pwsh
#
# @hwut {
#     title   = "Demo: a door's state machine, watched by a pype"
#     pype    = "door.pype"
#     choices {
#         kept   { features = ["demo-powershell", "demo-powershell+cover-fsm-law-kept"] }
#         broken { features = ["demo-powershell", "demo-powershell+cover-fsm-law-broken"] }
#     }
# }
#
<#
______________________________________________________________________________
A DOOR CONTROLLER THAT REPORTS WHAT IT DOES -- and a model that says what it
may do.

The application prints its log as it happens: noise, and a line 'door:
<event>' for each thing the door does. It prints no '<hwut-end>': the
header names 'door.pype', which stands between it and the comparison and
closes the stream at '<eof>'.

'door.pype' parses the log and fires every event into a state machine --
the pype's own language is Python, so its machine is Python's 'hwut_fsm'
(support/test_writing/python; 'hwut_fsm.psm1' is the same machine for a
PowerShell test that checks its model itself):

    closed ---( open )---> open ---( close )---> closed
    closed ---( lock )---> locked ---( unlock )---> closed
    open   ---( slam )---> jammed          # forbidden

kept     the door does what the model allows; the report shows which
         transitions were taken and which not, and 'ended in closed'.
broken   the controller locks an open door, slams it into a jam and
         tries to unlock it: each surprise is ONE 'BREACH' line in the
         output, the jam included, and the end outside the final states
         is one more. The GOOD file
         holds them and a run that stops breaching -- or breaches
         differently -- shows up as a difference.

Both choices pass on every run: what they print does not depend on time.
______________________________________________________________________________
#>
. "$PSScriptRoot/hwut_support.ps1"

$STORY_DB = [ordered]@{
    kept   = @('open', 'close', 'lock', 'unlock', 'open', 'close')
    broken = @('open', 'lock', 'slam', 'unlock')
}

<# RETURN: int, 0 -- the log of the door for 'choice', printed. #>
function main([string]$choice) {
    Out-Py 'controller 2.1 up'
    $number = 0
    foreach ($event_name in $STORY_DB[$choice]) {
        $number++
        Out-Py "tick ${number}: sensors read"
        Out-Py "door: $event_name"
    }
    Out-Py 'controller down'
    return 0
}

if ($args.Count -ne 1 -or @($STORY_DB.Keys) -cnotcontains [string]$args[0]) {
    Out-Py ('error: a choice is required: {0}' -f (($STORY_DB.Keys | Sort-Object) -join ', '))
    exit 1
}
exit (main $args[0])
