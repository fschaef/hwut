# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#_____________________________________________________________________________
#
# WHERE THE POWERSHELL TEST SUPPORT STANDS -- no test, a helper every test
# application of this directory dot-sources, naming the modules it uses:
#
#     . "$PSScriptRoot/hwut_support.ps1" hwut_runner deterministic_timeline
#
# THE ONE LINE THAT NAMES THE PORT'S PLACE is the marked line
# below: HWUT_SUPPORT_POWERSHELL where it is set, else the port as it stands
# in hwut's own tree, relative to this file.
#
# WHY NOT 'using module' (RATIONALE DEMO-POWERSHELL-1): its path is read
# when the file is PARSED, a literal -- no variable can say where it points.
# So the modules are imported at run time, and their classes are made known
# by name as type accelerators: '[HwutRunner]::new(...)' then works in the
# test as after 'using module'. What cannot work so is a class of the test
# that DERIVES from a class of the support: a base class must be known when
# the file is parsed (garage.ps1's 'Gate' therefore is no 'Trigger').
#
# The console is set up as the support's runner sets it up
# ('Initialize-HwutConsole'): UTF-8, the invariant culture, no colour, an
# error stops the script.
#_____________________________________________________________________________
$HwutSupportDir = if ($env:HWUT_SUPPORT_POWERSHELL) { $env:HWUT_SUPPORT_POWERSHELL } else { [System.IO.Path]::Combine($PSScriptRoot, '../../../test_writing/powershell') }  # HWUT-SUPPORT-PATH

<#
RETURN: nothing, once every module named in 'name_list' (the stem of a
        '.psm1' of the support; 'hwut_runner' always) is imported and each
        class and enum it defines is known by its name; throws where a
        module does not stand in $HwutSupportDir.
#>
function Import-HwutSupport([string[]]$name_list) {
    $accelerator = [psobject].Assembly.GetType('System.Management.Automation.TypeAccelerators')
    foreach ($name in @('hwut_runner') + $name_list) {
        $path = Join-Path $HwutSupportDir "$name.psm1"
        if (-not (Test-Path -LiteralPath $path)) {
            throw "hwut_support.ps1: no '$path' -- set HWUT_SUPPORT_POWERSHELL to the directory of the PowerShell test support"
        }
        $module = Import-Module $path -PassThru -Global -DisableNameChecking
        foreach ($type_name in $module.GetExportedTypeDefinitions().Keys) {
            $type = & $module { param($n) $n -as [type] } $type_name
            [void]$accelerator::Remove($type_name)
            $accelerator::Add($type_name, $type)
        }
    }
    Initialize-HwutConsole
}

Import-HwutSupport $args
