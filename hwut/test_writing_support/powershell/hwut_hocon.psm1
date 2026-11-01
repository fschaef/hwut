# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#_____________________________________________________________________________
#
# PURPOSE: Parse the HOCON subset of the specification language into the
#          ANNOTATED TREE -- the port of 'python/hwut_hocon.py' (read
#          '../python/README-hwut_hocon.txt'): every key, every value and
#          every block carries its file-relative position.
#
#     using module ../hwut_hocon.psm1
#     $lineList = for ($i = 0; ...) { [SourceLine]::new($text, $i + 1, 0) }
#     $document, $faultList = [Hocon]::Parse($lineList, 'f.hocon')
#     $document.Get('a').node.value;  "$($faultList[0])"   # 'f.hocon:3:5: SYNTAX: ...'
#
# THE SUBSET: nested objects, lists, numbers (decimal, 0x, 0b, 0o, roman 0r,
# '_' between digits), booleans (true/false/yes/no), the spellings of nothing
# (null/nil/none/nihil, or an empty value), '#' and '//' comments, '=' or ':'
# before a value, a brace directly after a key. A string value is written in
# double quotes; a text of several lines in triple quotes, laid out as a
# docstring ('inspect.cleandoc'). 'include', '${...}' and '+=' are REFUSED by
# name. The parser accumulates faults and recovers at the next line; it
# never throws.
#
# PYTHON'S TYPES IN .NET: an int is a [long] -- a [System.Numerics.BigInteger]
# where it is beyond (Python's ints have no bound) --, a float a [double], a
# bool a [bool], None $null. A ScalarNode carries 'py_type' ('str', 'int',
# 'float', 'bool', 'NoneType') and 'Repr()' writes the value as Python's '%r'
# does ('-1500.0' for the float, '42' for the int). Columns count code
# points, as Python's string indices do.
#
# THE NAMES are Python's: the classes Position, ParseFault, SourceLine,
# ScalarNode, ListNode, Entry, ObjectNode and the enum E_ParseFault keep
# theirs, fields too ('key_position', 'item_list', 'entry_list');
# 'parse' and 'cleandoc' are '[Hocon]::Parse' and '[Hocon]::Cleandoc',
# 'ObjectNode.get' and '.keys' are 'Get' and 'Keys'.
#_____________________________________________________________________________
using module ./hwut_pytext.psm1
Set-StrictMode -Version 3.0

enum E_ParseFault { SYNTAX; REFUSED }

[NoRunspaceAffinity()]
class Position {
    [int] $line
    [int] $column

    <# RETURN: Position, one place in one file; 1-based, as an editor counts. #>
    Position([int]$line, [int]$column) { $this.line = $line; $this.column = $column }

    <# RETURN: string, 'line:column'. #>
    [string] ToString() { return "$($this.line):$($this.column)" }
}

[NoRunspaceAffinity()]
class ParseFault {
    [E_ParseFault] $kind
    [string]       $file
    [Position]     $position
    [string]       $message

    <# RETURN: ParseFault, one fault of the parse: 'kind', 'file', 'position', 'message'. #>
    ParseFault([E_ParseFault]$kind, [string]$file, [Position]$position, [string]$message) {
        $this.kind = $kind; $this.file = $file; $this.position = $position; $this.message = $message
    }

    <# RETURN: string, 'file:line:column: KIND: message'. #>
    [string] ToString() { return "$($this.file):$($this.position): $($this.kind): $($this.message)" }
}

[NoRunspaceAffinity()]
class SourceLine {
    [string] $text
    [int]    $line
    [int]    $column_offset

    <#
    RETURN: SourceLine, one line as the parser reads it, tied to where it
            stands on disk; 'column_offset' counts what was removed before
            'text' begins.
    #>
    SourceLine([string]$text, [int]$line, [int]$column_offset) {
        $this.text = $text; $this.line = $line; $this.column_offset = $column_offset
    }
}

[NoRunspaceAffinity()]
class ScalarNode {
    [object]   $value
    [Position] $position
    [string]   $py_type

    <#
    RETURN: ScalarNode, one scalar value -- [string], [long] or BigInteger,
            [double], [bool] or $null -- at 'position'; 'py_type' the type
            Python gives it.
    #>
    ScalarNode([object]$value, [Position]$position, [string]$py_type) {
        $this.value = $value; $this.position = $position; $this.py_type = $py_type
    }

    <# RETURN: string, the value as Python's '%r' writes it: "'text'", '42', '-1500.0', 'True', 'None'. #>
    [string] Repr() {
        switch ($this.py_type) {
            'NoneType' { return 'None' }
            'bool'     { return [PyText]::BoolText($this.value) }
            'str'      { return [PyText]::StrRepr($this.value) }
            'float'    { return [PyText]::FloatRepr($this.value) }
        }
        return $this.value.ToString()
    }
}

[NoRunspaceAffinity()]
class ListNode {
    [object[]] $item_list
    [Position] $position

    <# RETURN: ListNode, one list of nodes at 'position'. #>
    ListNode([object[]]$item_list, [Position]$position) { $this.item_list = $item_list; $this.position = $position }
}

[NoRunspaceAffinity()]
class Entry {
    [string]   $key
    [Position] $key_position
    [object]   $node

    <# RETURN: Entry, one key with its value inside an object. #>
    Entry([string]$key, [Position]$key_position, [object]$node) { $this.key = $key; $this.key_position = $key_position; $this.node = $node }
}

[NoRunspaceAffinity()]
class ObjectNode {
    [Position] $position
    [System.Collections.Generic.List[Entry]] $entry_list

    <# RETURN: ObjectNode at 'position', no entries yet. #>
    ObjectNode([Position]$position) { $this.position = $position; $this.entry_list = [System.Collections.Generic.List[Entry]]::new() }

    <# RETURN: Entry, the entry named 'key' (compared by case); $null, no such entry. #>
    [Entry] Get([string]$key) {
        foreach ($entry in $this.entry_list) { if ($entry.key -ceq $key) { return $entry } }
        return $null
    }

    <# RETURN: string[], the keys in written order. #>
    [string[]] Keys() { return [string[]]@(foreach ($entry in $this.entry_list) { $entry.key }) }
}

[NoRunspaceAffinity()]
class HoconCursor {
    [object[]] $line_list
    [int]      $line_n
    [int]      $i_line
    [int]      $i_col
    [string]   $text

    <# RETURN: HoconCursor at the first character of the SourceLine list 'line_list'. #>
    HoconCursor([object[]]$line_list) {
        $this.line_list = $line_list
        $this.line_n    = $line_list.Count
        $this.i_line    = 0
        $this.i_col     = 0
        $this.text      = if ($line_list.Count -gt 0) { $line_list[0].text } else { '' }
    }

    <# RETURN: bool, $true where no character remains. #>
    [bool] AtEnd() { return $this.i_line -ge $this.line_n }

    <# RETURN: string, the character here (a whole code point); "`n" at the line's end; '' beyond the last line. #>
    [string] Peek() { return $this.Peek(0) }

    <#
    RETURN: string, the character 'ahead' code units from here on this line
            (a whole code point); "`n" at this line's end; '' beyond the last
            line.
    #>
    [string] Peek([int]$ahead) {
        if ($this.i_line -ge $this.line_n) { return '' }
        $i = $this.i_col + $ahead
        if ($i -ge $this.text.Length) { return "`n" }
        if ([char]::IsHighSurrogate($this.text[$i]) -and $i + 1 -lt $this.text.Length) { return $this.text.Substring($i, 2) }
        return [string]$this.text[$i]
    }

    <# RETURN: nothing. Steps 'n' code units WITHIN the current line. #>
    [void] Skip([int]$n) { $this.i_col += $n }

    <# RETURN: nothing. Steps to the beginning of the next line. #>
    [void] SkipLine() {
        $this.i_line++
        $this.i_col = 0
        $this.text  = if ($this.i_line -lt $this.line_n) { $this.line_list[$this.i_line].text } else { '' }
    }

    <# RETURN: Position, file-relative, of the character at the cursor -- columns in code points. #>
    [Position] Position() {
        if ($this.i_line -ge $this.line_n) {
            if ($this.line_list.Count -eq 0) { return [Position]::new(1, 1) }
            $last = $this.line_list[$this.line_list.Count - 1]
            return [Position]::new($last.line, $last.column_offset + [Hocon]::CodePointLength($last.text) + 1)
        }
        $line = $this.line_list[$this.i_line]
        return [Position]::new($line.line, $line.column_offset + [Hocon]::CodePointLength($this.text.Substring(0, $this.i_col)) + 1)
    }
}

[NoRunspaceAffinity()]
class Hocon {
    static hidden [regex] $TOKEN_RE        = [regex]::new('\G[^\s\x1c-\x1f{}\[\]=,:"#]*', 'Compiled')
    static hidden [regex] $QUOTED_PLAIN_RE = [regex]::new('\G([^"\\\n]*)"', 'Compiled')
    static hidden [regex] $DECIMAL_RE      = [regex]::new('^[-+]?(?:[0-9](?:_?[0-9])*(?:\.(?:[0-9](?:_?[0-9])*)?)?|\.[0-9](?:_?[0-9])*)(?:[eE][-+]?[0-9](?:_?[0-9])*)?$', 'Compiled')
    static hidden [regex] $ROMAN_RE        = [regex]::new('^M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$', 'Compiled')
    static hidden [object] $NOT_A_TOKEN    = [object]::new()     # a bare token that is none: an unquoted string

    <# RETURN: int, the number of code points of 's'. #>
    static [int] CodePointLength([string]$s) {
        $n = $s.Length
        foreach ($c in $s.ToCharArray()) { if ([char]::IsLowSurrogate($c)) { $n-- } }
        return $n
    }

    <# RETURN: string, the run of token characters in 'text' from index 'i' on (possibly empty). #>
    static hidden [string] TokenAt([string]$text, [int]$i) { return [Hocon]::TOKEN_RE.Match($text, $i).Value }

    <#
    RETURN: object[], @(ObjectNode, ParseFault[]) -- the document, every
            entry of the outermost level (possibly empty), and every fault
            found (empty on a clean parse). 'line_list' are SourceLines;
            'file' names the file for faults. Never throws on any text.
    #>
    static [object[]] Parse([object[]]$line_list, [string]$file) {
        if ($null -eq $line_list) { $line_list = @() }
        $fault_list = [System.Collections.Generic.List[ParseFault]]::new()
        $cursor     = [HoconCursor]::new($line_list)
        $document   = [Hocon]::ParseBody($cursor, $null, $file, $fault_list)
        return @($document, $fault_list.ToArray())
    }

    <# RETURN: nothing; a fault of 'kind' at 'position' appended. #>
    static hidden [void] Fault([System.Collections.Generic.List[ParseFault]]$fault_list, [E_ParseFault]$kind,
                               [string]$file, [Position]$position, [string]$message) {
        $fault_list.Add([ParseFault]::new($kind, $file, $position, $message))
    }

    <# RETURN: ObjectNode, the entries up to 'terminator' ('}', or $null for the end of the text). #>
    static hidden [ObjectNode] ParseBody([HoconCursor]$cursor, [object]$terminator, [string]$file,
                                         [System.Collections.Generic.List[ParseFault]]$fault_list) {
        $result = [ObjectNode]::new($cursor.Position())
        while ($true) {
            [Hocon]::SkipBlank($cursor)
            if ($cursor.AtEnd()) {
                if ($null -ne $terminator) {
                    [Hocon]::Fault($fault_list, 'SYNTAX', $file, $cursor.Position(), "unterminated object: '$terminator' missing")
                }
                return $result
            }
            $c = $cursor.Peek()
            if ($null -ne $terminator -and $c -ceq $terminator) { $cursor.Skip(1); return $result }
            if ($c -ceq '}') {
                [Hocon]::Fault($fault_list, 'SYNTAX', $file, $cursor.Position(), "unmatched '}'")
                $cursor.Skip(1)
            } else {
                [Hocon]::ParseEntry($cursor, $result, $file, $fault_list)
            }
        }
        return $result
    }

    <# RETURN: nothing. Parses one 'key = value' pair into 'object_node'; faults recover at the next line. #>
    static hidden [void] ParseEntry([HoconCursor]$cursor, [ObjectNode]$object_node, [string]$file,
                                    [System.Collections.Generic.List[ParseFault]]$fault_list) {
        $key_position = $cursor.Position()
        $key          = [Hocon]::ParseKey($cursor, $file, $fault_list)
        if ($null -eq $key) { $cursor.SkipLine(); return }

        if ($key -ceq 'include') {
            [Hocon]::Fault($fault_list, 'REFUSED', $file, $key_position,
                           "'include' does not exist here: a specification refers to nothing outside its file")
            $cursor.SkipLine()
            return
        }

        [Hocon]::SkipSpace($cursor)
        $c = $cursor.Peek()
        if ($c -ceq '=' -or $c -ceq ':') {
            $cursor.Skip(1)
            [Hocon]::SkipSpace($cursor)
        } elseif ($c -ceq '{') {
            #  a brace binds without a sign
        } elseif ($c -ceq '+' -and $cursor.Peek(1) -ceq '=') {
            [Hocon]::Fault($fault_list, 'REFUSED', $file, $cursor.Position(), "'+=' does not exist here")
            $cursor.SkipLine()
            return
        } else {
            [Hocon]::Fault($fault_list, 'SYNTAX', $file, $cursor.Position(), "expected '=', ':' or '{' after key '$key'")
            $cursor.SkipLine()
            return
        }

        $node = [Hocon]::ParseValue($cursor, $file, $fault_list, $false)
        if ($null -eq $node) { return }          # the value parser has recovered already

        if ($null -ne $object_node.Get($key)) {
            [Hocon]::Fault($fault_list, 'SYNTAX', $file, $key_position, "duplicate key '$key'; the first stands, this one is refused")
            return
        }
        $object_node.entry_list.Add([Entry]::new($key, $key_position, $node))
    }

    <# RETURN: string, the key; $null, no key stands here (fault recorded). #>
    static hidden [object] ParseKey([HoconCursor]$cursor, [string]$file, [System.Collections.Generic.List[ParseFault]]$fault_list) {
        if ($cursor.Peek() -ceq '"') { return [Hocon]::ParseQuoted($cursor, $file, $fault_list) }
        $t = [Hocon]::TokenAt($cursor.text, $cursor.i_col)
        if (-not $t) {
            [Hocon]::Fault($fault_list, 'SYNTAX', $file, $cursor.Position(), "expected a key, found '$($cursor.Peek().Trim())'")
            return $null
        }
        $cursor.Skip($t.Length)
        return $t
    }

    <#
    RETURN: ScalarNode, ListNode or ObjectNode, the value here; $null,
            nothing usable stands here (fault recorded). 'in_list_f' says an
            empty value is a fault rather than null.
    #>
    static hidden [object] ParseValue([HoconCursor]$cursor, [string]$file,
                                      [System.Collections.Generic.List[ParseFault]]$fault_list, [bool]$in_list_f) {
        [Hocon]::SkipSpace($cursor)
        $position = $cursor.Position()
        $c = $cursor.Peek()
        if ($c -ceq '{') { $cursor.Skip(1); return [Hocon]::ParseBody($cursor, '}', $file, $fault_list) }
        if ($c -ceq '[') { $cursor.Skip(1); return [Hocon]::ParseList($cursor, $position, $file, $fault_list) }
        if ($c -ceq '"' -and $cursor.Peek(1) -ceq '"' -and $cursor.Peek(2) -ceq '"') {
            $value = [Hocon]::ParseTripleQuoted($cursor, $file, $fault_list)
            if ($null -eq $value) { return $null }
            return [ScalarNode]::new($value, $position, 'str')
        }
        if ($c -ceq '"') {
            $value = [Hocon]::ParseQuoted($cursor, $file, $fault_list)
            if ($null -eq $value) { return $null }
            return [ScalarNode]::new($value, $position, 'str')
        }
        if ($c -ceq '$' -and $cursor.Peek(1) -ceq '{') {
            [Hocon]::Fault($fault_list, 'REFUSED', $file, $position,
                           "substitutions '`${...}' do not exist here: a specification refers to nothing outside its file")
            $cursor.SkipLine()
            return $null
        }
        return [Hocon]::ParseBare($cursor, $position, $file, $fault_list, $in_list_f)
    }

    <# RETURN: ListNode, the items up to ']' (a fault where it is missing). #>
    static hidden [ListNode] ParseList([HoconCursor]$cursor, [Position]$position, [string]$file,
                                       [System.Collections.Generic.List[ParseFault]]$fault_list) {
        $item_list = [System.Collections.Generic.List[object]]::new()
        while ($true) {
            [Hocon]::SkipBlank($cursor)
            if ($cursor.AtEnd()) {
                [Hocon]::Fault($fault_list, 'SYNTAX', $file, $cursor.Position(), "unterminated list: ']' missing")
                break
            }
            $c = $cursor.Peek()
            if ($c -ceq ']') { $cursor.Skip(1); break }
            if ($c -ceq ',') { $cursor.Skip(1); continue }
            if ($c -ceq '}') {
                #  A BRACE CLOSES THE OBJECT AROUND THE LIST: the ']' was forgotten.
                [Hocon]::Fault($fault_list, 'SYNTAX', $file, $cursor.Position(), "unterminated list: ']' missing before '}'")
                break
            }
            $beforeLine = $cursor.i_line; $beforeCol = $cursor.i_col
            $item = [Hocon]::ParseValue($cursor, $file, $fault_list, $true)
            if ($null -ne $item) { $item_list.Add($item) }
            #  NO VALUE READ AND NOTHING CONSUMED: step over the refused character.
            if ($null -eq $item -and $cursor.i_line -eq $beforeLine -and $cursor.i_col -eq $beforeCol) {
                $cursor.Skip($cursor.Peek().Length)
            }
        }
        return [ListNode]::new($item_list.ToArray(), $position)
    }

    <#
    RETURN: string, 'text' with every tab expanded to the next multiple of 8
            columns, as Python's 'str.expandtabs()' ("`n" and "`r" restart the
            count).
    #>
    static hidden [string] ExpandTabs([string]$text) {
        $sb = [System.Text.StringBuilder]::new()
        $column = 0
        foreach ($c in $text.ToCharArray()) {
            if ($c -eq "`t") { $n = 8 - ($column % 8); [void]$sb.Append(' ', $n); $column += $n }
            elseif ($c -eq "`n" -or $c -eq "`r") { [void]$sb.Append($c); $column = 0 }
            else { [void]$sb.Append($c); if (-not [char]::IsLowSurrogate($c)) { $column++ } }
        }
        return $sb.ToString()
    }

    <#
    RETURN: string, 'doc' laid out as Python's 'inspect.cleandoc' lays out a
            docstring: tabs expanded, the indentation (in blanks) common to
            the lines after the first removed, the first line's leading
            blanks removed, empty lines at both ends dropped.
    #>
    static [string] Cleandoc([string]$doc) {
        $lines = [System.Collections.Generic.List[string]]::new([string[]][Hocon]::ExpandTabs($doc).Split("`n"))
        $margin = [int]::MaxValue
        for ($i = 1; $i -lt $lines.Count; $i++) {
            $content = $lines[$i].TrimStart(' ').Length
            if ($content -gt 0) { $margin = [Math]::Min($margin, $lines[$i].Length - $content) }
        }
        if ($lines.Count -gt 0) { $lines[0] = $lines[0].TrimStart(' ') }
        if ($margin -lt [int]::MaxValue) {
            for ($i = 1; $i -lt $lines.Count; $i++) {
                $lines[$i] = if ($lines[$i].Length -gt $margin) { $lines[$i].Substring($margin) } else { '' }
            }
        }
        while ($lines.Count -gt 0 -and -not $lines[$lines.Count - 1]) { $lines.RemoveAt($lines.Count - 1) }
        while ($lines.Count -gt 0 -and -not $lines[0]) { $lines.RemoveAt(0) }
        return $lines -join "`n"
    }

    <#
    RETURN: string, the text between three double quotes and the next three,
            over as many lines as it takes, AS WRITTEN (no escape resolved),
            laid out by 'Cleandoc'; $null, no closing three quotes stand
            before the text's end (fault recorded at the opening).
    #>
    static hidden [object] ParseTripleQuoted([HoconCursor]$cursor, [string]$file, [System.Collections.Generic.List[ParseFault]]$fault_list) {
        $begin = $cursor.Position()
        $cursor.Skip(3)
        $piece_list = [System.Collections.Generic.List[string]]::new()
        while (-not $cursor.AtEnd()) {
            $t   = $cursor.text
            $end = $t.IndexOf('"""', $cursor.i_col, [System.StringComparison]::Ordinal)
            if ($end -ge 0) {
                $piece_list.Add($t.Substring($cursor.i_col, $end - $cursor.i_col))
                $cursor.i_col = $end + 3
                return [Hocon]::Cleandoc($piece_list -join "`n")
            }
            $piece_list.Add($t.Substring($cursor.i_col))
            $cursor.SkipLine()
        }
        [Hocon]::Fault($fault_list, 'SYNTAX', $file, $begin, "unterminated triple-quoted string: closing '`"`"`"' missing")
        return $null
    }

    <#
    RETURN: string, the quoted string's content, escapes ('\n', '\t', '\"',
            '\\'; any other escaped character stands for itself) resolved;
            $null, the string is unterminated at its line's end (fault
            recorded).
    #>
    static hidden [object] ParseQuoted([HoconCursor]$cursor, [string]$file, [System.Collections.Generic.List[ParseFault]]$fault_list) {
        $begin = $cursor.Position()
        $t     = $cursor.text
        $i     = $cursor.i_col + 1               # past the opening quote
        $match = [Hocon]::QUOTED_PLAIN_RE.Match($t, $i)
        if ($match.Success) {
            $cursor.i_col = $match.Index + $match.Length
            return $match.Groups[1].Value
        }
        $sb = [System.Text.StringBuilder]::new()
        while ($true) {
            if ($i -ge $t.Length) {
                [Hocon]::Fault($fault_list, 'SYNTAX', $file, $begin, 'unterminated string')
                $cursor.i_col = $i
                return $null
            }
            $c = $t[$i]
            if ($c -ceq '"') { $cursor.i_col = $i + 1; return $sb.ToString() }
            if ($c -ceq '\') {
                $i++
                $escaped = ''
                if ($i -lt $t.Length) {
                    $escaped = if ([char]::IsHighSurrogate($t[$i]) -and $i + 1 -lt $t.Length) { $t.Substring($i, 2) } else { [string]$t[$i] }
                }
                switch -CaseSensitive ($escaped) {
                    'n'     { [void]$sb.Append("`n") }
                    't'     { [void]$sb.Append("`t") }
                    default { [void]$sb.Append($escaped) }
                }
                $i += [Math]::Max($escaped.Length, 1)
            } else {
                [void]$sb.Append($c)
                $i++
            }
        }
        return $null
    }

    <# RETURN: int, the index of the first character at or after 'i' in 'text' that is no blank (' ' or tab). #>
    static hidden [int] BlankEnd([string]$text, [int]$i) {
        while ($i -lt $text.Length -and ($text[$i] -eq ' ' -or $text[$i] -eq "`t")) { $i++ }
        return $i
    }

    <#
    RETURN: ScalarNode, the bare token here: a boolean, a number, or one of
            the spellings of nothing (an empty value outside a list is null);
            $null, the token is none of those (fault recorded) -- a string is
            written in double quotes.
    #>
    static hidden [object] ParseBare([HoconCursor]$cursor, [Position]$position, [string]$file,
                                     [System.Collections.Generic.List[ParseFault]]$fault_list, [bool]$in_list_f) {
        $raw = [Hocon]::TokenAt($cursor.text, $cursor.i_col)

        #  A SIGN STANDING APART from its digits: '- 0.12'.
        if ($raw -ceq '+' -or $raw -ceq '-') {
            $t     = $cursor.text
            $after = [Hocon]::TokenAt($t, [Hocon]::BlankEnd($t, $cursor.i_col + 1))
            #  The two must make ONE number: '- -1.5e3' does not (services E-213).
            if ($after -and $null -ne [Hocon]::Number($after) -and $null -ne [Hocon]::Number($raw + $after)) {
                $cursor.i_col = [Hocon]::BlankEnd($t, $cursor.i_col + 1) + $after.Length
                $n = [Hocon]::Number($raw + $after)
                return [ScalarNode]::new($n[0], $position, $n[1])
            }
        }
        if ($raw.StartsWith('${', [System.StringComparison]::Ordinal)) {
            [Hocon]::Fault($fault_list, 'REFUSED', $file, $cursor.Position(), "substitutions '`${...}' do not exist here")
            $cursor.SkipLine()
            return $null
        }
        $iComment = $raw.IndexOf('//', [System.StringComparison]::Ordinal)
        if ($iComment -ge 0) { $raw = $raw.Substring(0, $iComment) }
        $cursor.Skip($raw.Length)

        if (-not $raw) {
            if ($in_list_f) {
                [Hocon]::Fault($fault_list, 'SYNTAX', $file, $position, "expected a value, found '$($cursor.Peek().Trim())'")
                return $null
            }
            return [ScalarNode]::new($null, $position, 'NoneType')     # an empty value is null
        }
        switch -CaseSensitive ($raw) {
            'null'  { return [ScalarNode]::new($null, $position, 'NoneType') }
            'nil'   { return [ScalarNode]::new($null, $position, 'NoneType') }
            'none'  { return [ScalarNode]::new($null, $position, 'NoneType') }
            'nihil' { return [ScalarNode]::new($null, $position, 'NoneType') }
            'true'  { return [ScalarNode]::new($true, $position, 'bool') }
            'yes'   { return [ScalarNode]::new($true, $position, 'bool') }
            'false' { return [ScalarNode]::new($false, $position, 'bool') }
            'no'    { return [ScalarNode]::new($false, $position, 'bool') }
        }
        $number = [Hocon]::Number($raw)
        if ($null -eq $number) {
            [Hocon]::Fault($fault_list, 'SYNTAX', $file, $position, "a string is written in double quotes: `"$raw`"")
            return $null
        }
        return [ScalarNode]::new($number[0], $position, $number[1])
    }

    <# RETURN: object, the integer 'value' as a [long] where it fits, the BigInteger else. #>
    static hidden [object] IntOf([System.Numerics.BigInteger]$value) {
        if ($value -ge [long]::MinValue -and $value -le [long]::MaxValue) { return [long]$value }
        return $value
    }

    <#
    RETURN: object[], @(value, 'int'|'float') -- the number the text spells,
            in whatever radix it spells it ('_' enters no value); $null, the
            text spells no number.
    #>
    static hidden [object[]] Number([string]$raw) {
        if ($raw.Length -eq 0) { return $null }
        $signF = $raw[0] -eq '+' -or $raw[0] -eq '-'
        $body  = if ($signF) { $raw.Substring(1) } else { $raw }
        $negF  = $raw[0] -eq '-'
        $prefix = if ($body.Length -ge 2) { $body.Substring(0, 2) } else { $body }
        if ($prefix -ceq '0r' -or $prefix -ceq '0R') {
            $value = [Hocon]::Roman($body.Substring(2))
            if ($value -lt 0) { return $null }
            if ($negF) { $value = -$value }
            return @([long]$value, 'int')
        }
        $radix = switch -CaseSensitive ($prefix) { '0x' { 16 } '0X' { 16 } '0b' { 2 } '0B' { 2 } '0o' { 8 } '0O' { 8 } default { 0 } }
        if ($radix -ne 0) {
            $digits = [Hocon]::WithoutHelper($body.Substring(2), $radix)
            if ($null -eq $digits) { return $null }
            $big = [System.Numerics.BigInteger]::Zero
            foreach ($c in $digits.ToCharArray()) {
                $big = $big * $radix + [System.Convert]::ToInt32([string]$c, 16)
            }
            if ($negF) { $big = -$big }
            return @([Hocon]::IntOf($big), 'int')
        }
        if (-not [Hocon]::DECIMAL_RE.IsMatch($raw)) { return $null }
        $text = $raw.Replace('_', '')
        if ($text.IndexOfAny([char[]]'.eE') -ge 0) {
            return @([double]::Parse($text, [System.Globalization.NumberStyles]::Float, [System.Globalization.CultureInfo]::InvariantCulture), 'float')
        }
        $big = [System.Numerics.BigInteger]::Parse($text.TrimStart('+', '-'), [System.Globalization.CultureInfo]::InvariantCulture)
        if ($negF) { $big = -$big }
        return @([Hocon]::IntOf($big), 'int')
    }

    <#
    RETURN: string, 'text' with every '_' removed; $null, the text carries no
            digit, a character that is no digit of 'radix', or an '_' that
            separates nothing.
    #>
    static hidden [object] WithoutHelper([string]$text, [int]$radix) {
        if (-not $text -or $text[0] -eq '_' -or $text[$text.Length - 1] -eq '_') { return $null }
        if ($text.Contains('__')) { return $null }
        $stripped = $text.Replace('_', '')
        if (-not $stripped) { return $null }
        $digitSet = switch ($radix) { 16 { '0123456789abcdefABCDEF' } 2 { '01' } default { '01234567' } }
        foreach ($c in $stripped.ToCharArray()) { if ($digitSet.IndexOf($c) -lt 0) { return $null } }
        return $stripped
    }

    <#
    RETURN: int, the number the roman numeral 'text' spells (the strict
            form); -1, the text is no roman numeral ('IIII', 'VX').
    #>
    static hidden [int] Roman([string]$text) {
        if (-not $text -or -not [Hocon]::ROMAN_RE.IsMatch($text)) { return -1 }
        $total = 0; $previous = 0
        for ($i = $text.Length - 1; $i -ge 0; $i--) {
            $value = switch -CaseSensitive ([string]$text[$i]) { 'I' { 1 } 'V' { 5 } 'X' { 10 } 'L' { 50 } 'C' { 100 } 'D' { 500 } 'M' { 1000 } }
            if ($value -lt $previous) { $total -= $value } else { $total += $value }
            $previous = [Math]::Max($previous, $value)
        }
        return $total
    }

    <# RETURN: nothing. Skips blanks and comments on the current line. #>
    static hidden [void] SkipSpace([HoconCursor]$cursor) {
        $t = $cursor.text
        $n = $t.Length
        $i = $cursor.i_col
        while ($i -lt $n -and ($t[$i] -eq ' ' -or $t[$i] -eq "`t")) { $i++ }
        $cursor.i_col = $i
        if ($i -lt $n -and ($t[$i] -eq '#' -or ($t[$i] -eq '/' -and $i + 1 -lt $n -and $t[$i + 1] -eq '/'))) { $cursor.SkipLine() }
    }

    <# RETURN: nothing. Skips blanks, newlines, commas and comments. #>
    static hidden [void] SkipBlank([HoconCursor]$cursor) {
        while ($cursor.i_line -lt $cursor.line_n) {
            $t = $cursor.text
            $n = $t.Length
            $i = $cursor.i_col
            while ($i -lt $n -and ($t[$i] -eq ' ' -or $t[$i] -eq "`t" -or $t[$i] -eq ',')) { $i++ }
            if ($i -ge $n) { $cursor.SkipLine(); continue }
            $cursor.i_col = $i
            $c = $t[$i]
            if ($c -eq '#' -or ($c -eq '/' -and $i + 1 -lt $n -and $t[$i + 1] -eq '/')) { $cursor.SkipLine(); continue }
            return
        }
    }
}
