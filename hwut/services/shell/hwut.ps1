# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
# TAB COMPLETION OF THE HWUT FACES, PowerShell (services E-151).
#     . <this file>               in '$PROFILE'
# The line up to the cursor goes to the completer whole; it answers one
# 'candidate<TAB>description' per line. A face is every 'hwut' and
# 'hwut.*' command on PATH when this file is read.
$hwutFaceList = @(Get-Command -CommandType Application -Name 'hwut', 'hwut.*' `
                      -ErrorAction SilentlyContinue |
                  ForEach-Object { $_.Name } | Sort-Object -Unique)
if ($hwutFaceList.Count -gt 0) {
    Register-ArgumentCompleter -Native -CommandName $hwutFaceList -ScriptBlock {
        param($wordToComplete, $commandAst, $cursorPosition)
        $line = $commandAst.Extent.Text
        $upTo = $cursorPosition - $commandAst.Extent.StartOffset
        #  The extent ends at the last word: a cursor beyond it stands
        #  after a blank, and a new word begins.
        if ($upTo -lt $line.Length) { $line = $line.Substring(0, $upTo) }
        elseif ($upTo -gt $line.Length) { $line += ' ' }
        hwut --command-line-complete powershell $line 2>$null | ForEach-Object {
            $candidate, $description = $_ -split "`t", 2
            [System.Management.Automation.CompletionResult]::new(
                $candidate, $candidate, 'ParameterValue', $description)
        }
    }
}
Remove-Variable hwutFaceList
