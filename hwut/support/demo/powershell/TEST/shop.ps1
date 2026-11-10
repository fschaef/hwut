#! /usr/bin/env pwsh
#
# @hwut {
#     title     = "Demo: a shop's stock -- what the directory's hwut.conf arranges"
#     tolerance { stderr_ignored = true }
#     choices {
#         sell   { features = ["demo-powershell+cover-unordered-table", "demo-powershell+cover-stderr-ignored", "demo-powershell+cover-collision"] }
#         report { features = ["demo-powershell+cover-output-file", "demo-powershell+cover-keyed-table-separator", "demo-powershell+cover-dependency",
#                              "demo-powershell+cover-frame-scripts", "demo-powershell+cover-test-scripts", "demo-powershell+cover-stderr-ignored"]
#                  output   = ["<stdout>", "stock.csv"] }
#     }
# }
#
<#
______________________________________________________________________________
SUBJECT  the stock of a small shop, kept in an SQLite database: a delivery
         comes in, three clerks sell at once, and the stock is reported.
REQUIREMENT  Every movement of the stock is journalled, so that the stock
             always ADDS UP: opening quantity plus the journal's movements.

THE DIRECTORY ARRANGES WHAT NO SINGLE TEST CAN -- in 'hwut.conf' beside
this file, read it first. hwut, when it enters this directory:

    on_entry        'fixture.ps1 open': a fresh 'TMP/shop.db', stocked
    on_before_test  'fixture.ps1 check before $HWUT_TEST $HWUT_CHOICE',
    on_after_test   'fixture.ps1 check after ...': around every test run,
                    whether the stock adds up, into 'TMP/frame.log' --
                    hwut sets the two variables for the run
    on_exit         'fixture.ps1 close'
    apps            'delivery.json' is a test, though it carries no
                    header: JSON has no comment to carry one. 'admit'
                    takes it out of the files hwut ignores by default
                    ('*.json'); 'execute' says how it is run --
                    'shop.ps1 deliver delivery.json'.
    collision       'delivery.json' and 'shop.ps1 sell' both write the
                    database. SQLite lets one writer at a time hold the
                    file; one that waits too long fails with 'database
                    is locked'. hwut never runs the two at once.
    dependency      'shop.ps1 report' runs after both, whatever their
                    verdict: it reports what they left.

STDERR  Every SQL statement is logged on stderr, as a server would. A
word on stderr fails a run ('unexpected stderr') unless the header says
'stderr_ignored = true': the words there are on purpose, and no error.

CHOICES

sell     three clerks sell at once, each in a runspace of its own. The
         sales are printed as '##! table unordered sep={;}': rows of
         'item;qty', in any order -- and no column is a key, 'apple;1'
         stands four times.

report   the stock, as '##! table key=0 sep={;}', and the same rows
         written to 'stock.csv': 'output' names the file, hwut reads it
         after the run and compares it with its own GOOD. Then the frame
         log of the shop's tests: what 'on_before_test' and 'on_after_test'
         found around the delivery and the sale ('##! potpourri': which
         ran first is free), and before this report.

deliver  (no choice -- 'execute' of 'delivery.json' calls it) books a
         delivery note: every line on the stock and into the journal, in
         one transaction.

SQLite is reached through 'shop_db.ps1' (P/Invoke to libsqlite3): .NET has
no SQLite of its own.
______________________________________________________________________________
#>
. "$PSScriptRoot/hwut_support.ps1"
. "$PSScriptRoot/shop_db.ps1"

$HERE     = $PSScriptRoot
$DB_PATH  = Join-Path $HERE 'TMP/shop.db'
$LOG_PATH = Join-Path $HERE 'TMP/frame.log'

#  What each clerk sells, one item per sale.
$CLERK_DB = [ordered]@{ anna  = @('apple', 'apple', 'pear')
                        ben   = @('apple', 'plum')
                        chloe = @('apple') }

<#
RETURN: ShopDb, a connection to the shop's database, every statement it
        executes logged on stderr. Exits 1 where the database does not
        stand: 'on_entry' writes it.
#>
function connect {
    if (-not (Test-Path -LiteralPath $DB_PATH)) {
        [Console]::Error.WriteLine("shop.ps1: no $DB_PATH -- 'on_entry' writes it; by hand: 'hwut.execute fixture open'")
        exit 1
    }
    return [ShopDb]::new($DB_PATH, 10000, $true)
}

<# RETURN: nothing. Books the delivery note in 'path' and prints it. #>
function deliver([string]$path) {
    $note = Get-Content -Raw -LiteralPath $path | ConvertFrom-Json
    $db = connect
    [void]$db.Execute('BEGIN IMMEDIATE', @())
    foreach ($line in $note.lines) {
        [void]$db.Execute('UPDATE stock SET qty = qty + ? WHERE item = ?', @([long]$line.qty, $line.item))
        [void]$db.Execute('INSERT INTO journal VALUES (?, ?, ?)', @($line.item, [long]$line.qty, $note.note))
    }
    [void]$db.Execute('COMMIT', @())
    Out-Py ('delivery note {0} from {1}:' -f $note.note, $note.supplier)
    foreach ($line in $note.lines) { Out-Py ('    {0,-6} +{1}' -f $line.item, $line.qty) }
}

<# RETURN: nothing. Three clerks sell at once; prints every sale. #>
function sell {
    (connect).Close()
    $sale_list  = [System.Collections.Concurrent.ConcurrentQueue[string]]::new()
    $error_list = [System.Collections.Concurrent.ConcurrentQueue[string]]::new()
    $CLERK_DB.GetEnumerator() | ForEach-Object -ThrottleLimit 3 -Parallel {
        $name, $item_list, $path = $_.Key, $_.Value, $using:DB_PATH
        try {
            $db = [ShopDb]::new($path, 10000, $true)
            foreach ($item in $item_list) {
                #  One movement, journalled, in one transaction.
                [void]$db.Execute('BEGIN IMMEDIATE', @())
                [void]$db.Execute('UPDATE stock SET qty = qty + ? WHERE item = ?', @(-1, $item))
                [void]$db.Execute('INSERT INTO journal VALUES (?, ?, ?)', @($item, -1, $name))
                [void]$db.Execute('COMMIT', @())
                ($using:sale_list).Enqueue("$item;1")
            }
            $db.Close()
        } catch {
            ($using:error_list).Enqueue("${name}: $($_.Exception.Message)")
        }
    }
    if ($error_list.Count -gt 0) {
        [Console]::Error.WriteLine("shop.ps1: a sale failed -- $(@($error_list) -join '; ')")
        exit 1
    }
    Out-Py 'sales, item;qty -- in the order the clerks booked them:'
    Out-Py '##! table unordered sep={;}'
    foreach ($row in $sale_list) { Out-Py $row }
    Out-Py '####'
}

<# RETURN: nothing. Prints the stock and the frame log; writes 'stock.csv'. #>
function report {
    $db = connect
    $row_list = $db.Execute('SELECT item, qty FROM stock ORDER BY qty, item', @())
    $csv = [System.Text.StringBuilder]::new("item;qty`n")
    foreach ($row in ($row_list | Sort-Object -Culture '' { $_[0] })) { [void]$csv.Append("$($row[0]);$($row[1])`n") }
    [System.IO.File]::WriteAllText((Join-Path $HERE 'stock.csv'), $csv.ToString())
    Out-Py 'stock, item;qty (also written to stock.csv):'
    Out-Py '##! table key=0 sep={;}'
    foreach ($row in $row_list) { Out-Py "$($row[0]);$($row[1])" }
    Out-Py '####'
    $line_list = @(foreach ($line in [System.IO.File]::ReadAllLines($LOG_PATH)) { $line.TrimEnd() })
    Out-Py 'the frame, around the delivery and the sale:'
    Out-Py '##! potpourri'
    foreach ($line in $line_list) { if (-not $line.Contains('shop.ps1 report')) { Out-Py $line } }
    Out-Py '####'
    foreach ($line in $line_list) { if ($line.Contains('shop.ps1 report')) { Out-Py $line } }
}

$command = if ($args.Count -gt 0) { [string]$args[0] } else { '' }
switch -CaseSensitive ($command) {
    'deliver' { deliver $args[1] }
    'sell'    { sell }
    'report'  { report }
    default   { Out-Py 'choices: sell, report'; exit 1 }
}
Out-Py '<hwut-end>'
