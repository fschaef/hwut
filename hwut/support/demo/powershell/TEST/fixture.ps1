#! /usr/bin/env pwsh
<#
______________________________________________________________________________
THE SHOP'S FIXTURE -- no test, a helper the directory's 'hwut.conf' calls.

    fixture.ps1 open           a fresh 'TMP/shop.db', stocked as below, and
                               an empty 'TMP/frame.log' ('on_entry', and
                               'hwut.execute fixture open')
    fixture.ps1 close          both removed ('on_exit')
    fixture.ps1 check <when> <app> [<choice>]
                               'when' is 'before' or 'after': whether the
                               stock adds up around the test run '<app>
                               <choice>', appended to 'TMP/frame.log'
                               ('on_before_test', 'on_after_test')

'hwut.conf' passes '<app>' and '<choice>' as '$HWUT_TEST $HWUT_CHOICE',
which hwut sets for the run the check stands around; a test without
choices has none. 'check' concerns the shop's tests alone -- and loads the
database only for them: the other runs cost a pwsh start, no compile. The
stock ADDS UP where every item's quantity is its opening quantity plus
every movement of the journal.
______________________________________________________________________________
#>
$ErrorActionPreference = 'Stop'
$HERE     = $PSScriptRoot
$DB_PATH  = Join-Path $HERE 'TMP/shop.db'
$LOG_PATH = Join-Path $HERE 'TMP/frame.log'
$OPENING_DB = [ordered]@{ apple = 10; pear = 5; plum = 5 }
$SHOP_TEST_SET = @('delivery.json', 'shop.ps1')

<# RETURN: nothing. Writes a fresh, stocked database and an empty log. #>
function open_shop {
    [void](New-Item -ItemType Directory -Force -Path (Split-Path $DB_PATH))
    foreach ($path in $DB_PATH, $LOG_PATH) { if (Test-Path $path) { Remove-Item $path } }
    . "$HERE/shop_db.ps1"
    $db = [ShopDb]::new($DB_PATH, 10000, $false)
    [void]$db.Execute('CREATE TABLE opening (item TEXT PRIMARY KEY, qty INTEGER)', @())
    [void]$db.Execute('CREATE TABLE stock   (item TEXT PRIMARY KEY, qty INTEGER)', @())
    [void]$db.Execute('CREATE TABLE journal (item TEXT, delta INTEGER, source TEXT)', @())
    foreach ($item in $OPENING_DB.Keys) {
        [void]$db.Execute('INSERT INTO opening VALUES (?, ?)', @($item, $OPENING_DB[$item]))
        [void]$db.Execute('INSERT INTO stock   VALUES (?, ?)', @($item, $OPENING_DB[$item]))
    }
    $db.Close()
    [System.IO.File]::WriteAllText($LOG_PATH, '')
}

<# RETURN: nothing. Removes the database and the log. #>
function close_shop {
    foreach ($path in $DB_PATH, $LOG_PATH) { if (Test-Path $path) { Remove-Item $path } }
}

<#
RETURN: $true, if every item's stock is its opening quantity plus its
               journal's movements;
        $false, else.
#>
function adds_up {
    . "$HERE/shop_db.ps1"
    $db = [ShopDb]::new($DB_PATH, 10000, $false)
    $row_list = $db.Execute('SELECT o.item, o.qty + COALESCE(SUM(j.delta), 0), s.qty' +
                            '  FROM opening o JOIN stock s ON s.item = o.item' +
                            '  LEFT JOIN journal j ON j.item = o.item GROUP BY o.item', @())
    $db.Close()
    foreach ($row in $row_list) { if ($row[1] -ne $row[2]) { return $false } }
    return $true
}

<# RETURN: nothing. Appends one line to the log for a shop test run. #>
function check([string]$when, [string]$test, [string]$choice = '') {
    if ($SHOP_TEST_SET -cnotcontains $test) { return }
    $run  = "$test $choice".Trim()
    $said = if (adds_up) { 'stock adds up' } else { 'STOCK BROKEN' }
    [System.IO.File]::AppendAllText($LOG_PATH, ('{0,-6} {1,-15} {2}' -f $when, $run, $said) + "`n")
}

$command = if ($args.Count -gt 0) { [string]$args[0] } else { '' }
switch -CaseSensitive ($command) {
    'open'  { open_shop }
    'close' { close_shop }
    'check' { $rest = @($args | Select-Object -Skip 1); check @rest }
    default {
        [Console]::Error.WriteLine('usage: fixture.ps1 open | close | check before|after <app> <choice>')
        exit 2
    }
}
