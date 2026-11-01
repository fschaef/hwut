# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#_____________________________________________________________________________
#
# PURPOSE: A TERMINAL'S SCREEN, READ BY A TEST -- the port of
#          'python/hwut_vterm.py' (read '../python/README-hwut_vterm.txt'):
#          'libvterm' through P/Invoke.
#
#     using module ../hwut_vterm.psm1
#     [VtermScreen]::new(24, 80).Use({ param($screen)
#         [void]$screen.Feed("`e[1mbold`e[0m plain")
#         $screen.Line(0)                 # 'bold plain'
#         $screen.Cell(0, 0).bold_f       # $true
#         $screen.Cursor()                # @(0, 10)
#     })
#
# THE LIBRARY IS FOUND, NOT SHIPPED: 'libvterm.so.0' as the system knows it
#     (Debian: 'libvterm0'), or the file HWUT_LIBVTERM names -- loaded by
#     .NET's NativeLibrary. Where neither stands, '[VtermScreen]::new()'
#     throws LibraryMissing, whose text says how to install it.
#     'Get-VtermDetection' asks the same by hand.
#
# THE NATIVE EDGE is 'hwut_vterm_native.cs', compiled by Add-Type on the
# first Screen of a process (MEASURED: 0.7 s), once: the C functions, the two
# structures passed by value, the callbacks -- which only QUEUE what libvterm
# reports; this module drains the queue after every call into the library,
# so no script runs inside a native callback.
#
# THE CELL'S LAYOUT IS MEASURED, NOT ASSUMED -- as the Python binding does: a
# scratch terminal is fed one attribute at a time and the bit or the bytes
# that changed are where that attribute stands; no header of libvterm is read.
#
# TWO CLASSES:
#     VtermScreen     the grid alone: bytes in, cells out. No process.
#     VtermTerminal   a Screen an APPLICATION RUNS IN, on a pseudo-terminal it
#                     cannot tell from a person's; keys go in as a keyboard
#                     sends them; observation by callback, raw ('OnEvent') or
#                     by named region ('OnChange').
#
# WHERE POWERSHELL DIFFERS FROM PYTHON:
#     names           Python's in PowerShell's casing: 'line_list' is
#                     'LineList', 'region_text' 'RegionText', 'on_change'
#                     'OnChange'; fields keep theirs ('row_n', 'bold_f').
#     no 'with'       '$screen.Use({ param($screen) ... })': the block runs --
#                     what it puts on the pipeline written to [Console]::Out
#                     as it comes -- then 'Close()', whatever way it ends.
#     no fork         the application is started by libc's 'posix_spawnp'
#                     (as 'java/hwut/Posix.java' does): a new session
#                     (POSIX_SPAWN_SETSID), the pseudo-terminal's slave OPENED
#                     as fd 0 -- a session leader opening a terminal makes it
#                     its controlling one, as Python's 'setsid' and TIOCSCTTY
#                     do -- and dup'ed to 1, 2; every signal at its default.
#     keyword args    overloads, positional in Python's order: 'Region(name,
#                     row, row_n, column, column_n)', 'Press(key,
#                     modifier_list, react_s)', 'Run(argv, env, cwd, start_s)'.
#     tuples          arrays: 'Cursor()' is @(row, column), a colour
#                     @(red, green, blue).
#     callbacks       script blocks; what they put on the pipeline is
#                     written to [Console]::Out.
#     exceptions      classes named as Python's: LibraryMissing, IndexError,
#                     KeyError, TimeoutError, RuntimeError -- 'Message' is
#                     Python's text.
#_____________________________________________________________________________
Set-StrictMode -Version 3.0

class LibraryMissing : System.Exception {
    <# RETURN: LibraryMissing: 'libvterm' was not found; 'message' says how to install it. #>
    LibraryMissing([string]$message) : base($message) { }
}
class IndexError : System.Exception {
    <# RETURN: IndexError, as Python's: a place not on the screen. #>
    IndexError([string]$message) : base($message) { }
}
class KeyError : System.Exception {
    <# RETURN: KeyError, as Python's: 'message' is the key's repr ("'nosuch'"). #>
    KeyError([string]$message) : base($message) { }
}
class TimeoutError : System.Exception {
    <# RETURN: TimeoutError, as Python's. #>
    TimeoutError([string]$message) : base($message) { }
}
class RuntimeError : System.Exception {
    <# RETURN: RuntimeError, as Python's. #>
    RuntimeError([string]$message) : base($message) { }
}

class VtermEvent {
    [string] $kind
    [object] $row
    [object] $column
    [object] $row_end
    [object] $column_end
    [object] $name
    [object] $value

    <#
    RETURN: VtermEvent, ONE THING THE TERMINAL DID (the RAW layer), from the
            native record 'r':
        kind 'damage'    rows 'row'..'row_end', columns 'column'..'column_end'
                         changed, ends EXCLUDED
             'cursor'    the cursor stands at (row, column); 'value': visible
             'property'  the property 'name' is now 'value' ($null for a text)
             'bell'      the bell rang
    #>
    VtermEvent([object[]]$r) {
        $this.kind = $r[0]
        switch ($r[0]) {
            'damage'   { $this.row = $r[1]; $this.row_end = $r[2]; $this.column = $r[3]; $this.column_end = $r[4] }
            'cursor'   { $this.row = $r[1]; $this.column = $r[2]; $this.value = $r[3] }
            'property' {
                $known = [Vterm]::PROPERTY_DB[[int]$r[1]]
                $this.name  = if ($null -ne $known) { $known } else { "property-$($r[1])" }
                $this.value = $r[2]
            }
        }
    }

    <# RETURN: string, the event on one line, as the Python test prints it. #>
    [string] ToString() {
        switch ($this.kind) {
            'damage'   { return "damage    rows $($this.row)..$($this.row_end)  columns $($this.column)..$($this.column_end)" }
            'cursor'   { return "cursor    ($($this.row), $($this.column))$(if ($this.value) { '' } else { '  hidden' })" }
            'property' { return "property  $($this.name) = $(if ($null -eq $this.value) { 'None' } else { $this.value })" }
        }
        return $this.kind
    }
}

class VtermCell {
    [string]   $text = ''
    [int]      $width = 1
    [bool]     $bold_f
    [bool]     $italic_f
    [bool]     $underline_f
    [bool]     $blink_f
    [bool]     $reverse_f
    [bool]     $conceal_f
    [bool]     $strike_f
    [object]   $foreground          # @(red, green, blue), or $null: the terminal's default
    [object]   $background

    <#
    RETURN: string, the attributes that are set, by name, in the fixed order
            of [Vterm]::ATTRIBUTE_NAME_LIST, separated by blanks ('bold
            reverse'); '' where none is set.
    #>
    [string] AttributeText() {
        $set = foreach ($name in [Vterm]::ATTRIBUTE_NAME_LIST) { if ($this."${name}_f") { $name } }
        return (@($set) -join ' ')
    }
}

class Vterm {
    #  THE ENVIRONMENT VARIABLE that names the library's file.
    static [string]   $LIBRARY_VARIABLE  = 'HWUT_LIBVTERM'
    #  THE NAMES the system's search is asked for, in this order.
    static [string[]] $LIBRARY_NAME_LIST = @('libvterm.so.0', 'libvterm.so', 'libvterm.dylib', 'libvterm.0.dylib')
    static [int] $CHARS_BYTE_N = 24      # 6 code points of 4 bytes
    static [int] $CELL_BYTE_N  = 128     # room beyond any version's cell
    #  THE ATTRIBUTES A CELL IS ASKED FOR, each with the SGR code that sets it.
    static [string[]] $ATTRIBUTE_NAME_LIST = @('bold', 'italic', 'underline', 'blink', 'reverse', 'conceal', 'strike')
    static [string[]] $ATTRIBUTE_SGR_LIST  = @('1', '3', '4', '5', '7', '8', '9')
    static [string] $INSTALL_HINT = (@(
        'HINT: install the library, or name its file:',
        '    Debian, Ubuntu   apt install libvterm0',
        '    Fedora           dnf install libvterm',
        '    Arch             pacman -S libvterm',
        '    macOS            brew install libvterm',
        '    elsewhere        export HWUT_LIBVTERM=<path>/libvterm.so',
        '    or work inside   hwut.dev.podman.enter   (the image holds it)') -join "`n")
    static [int] $DAMAGE_MERGE_ROW = 1
    static [hashtable] $PROPERTY_DB = @{ 1 = 'cursor-visible'; 2 = 'cursor-blink'; 3 = 'alternate-screen'; 4 = 'title'
                                         5 = 'icon-name'; 6 = 'reverse-video'; 7 = 'cursor-shape'; 8 = 'mouse'; 9 = 'focus-report' }
    static [int[]] $PLAIN_PROPERTY_LIST = @(1, 2, 3, 6, 7, 8, 9)     # a number or a bool; 4, 5 are texts
    static [System.Collections.Generic.Dictionary[string, int]] $KEY_DB = [Vterm]::KeyDb()
    static [System.Collections.Generic.Dictionary[string, int]] $MODIFIER_DB = [Vterm]::ModifierDb()

    static [object] $_library = $null    # @{ name; handle; convert_f } once loaded
    static [object] $_layout  = $null    # the measured layout, once
    static [type]   $L        = $null    # HwutVterm.Lib, once compiled
    static [type]   $P        = $null    # HwutVterm.Posix
    static [type]   $R        = $null    # HwutVterm.Recorder

    <# RETURN: Dictionary, key name -> libvterm's VTermKey number ('enter' 1 ... 'f12' 268). #>
    static hidden [System.Collections.Generic.Dictionary[string, int]] KeyDb() {
        $db = [System.Collections.Generic.Dictionary[string, int]]::new([System.StringComparer]::Ordinal)
        $i = 1
        foreach ($k in @('enter', 'tab', 'backspace', 'escape', 'up', 'down', 'left', 'right',
                         'insert', 'delete', 'home', 'end', 'pageup', 'pagedown')) { $db[$k] = $i; $i++ }
        for ($n = 1; $n -le 12; $n++) { $db["f$n"] = 256 + $n }
        return $db
    }

    <# RETURN: Dictionary, modifier name -> libvterm's VTermModifier bit. #>
    static hidden [System.Collections.Generic.Dictionary[string, int]] ModifierDb() {
        $db = [System.Collections.Generic.Dictionary[string, int]]::new([System.StringComparer]::Ordinal)
        $db['shift'] = 1; $db['alt'] = 2; $db['ctrl'] = 4
        return $db
    }

    <#
    RETURN: hashtable @{ name; handle; convert_f }, 'libvterm' loaded once --
            'name' the file it was loaded as, the native edge compiled and
            bound to it; throws LibraryMissing, if no such library is found
            or it cannot be loaded.
    #>
    static [object] Library() {
        if ($null -ne [Vterm]::_library) { return [Vterm]::_library }
        $given  = [System.Environment]::GetEnvironmentVariable([Vterm]::LIBRARY_VARIABLE)
        $handle = [IntPtr]::Zero
        $name   = $null
        if ($given) {
            try { $handle = [System.Runtime.InteropServices.NativeLibrary]::Load($given); $name = $given }
            catch {
                $x = $_.Exception; while ($null -ne $x.InnerException) { $x = $x.InnerException }
                #  THE SYSTEM'S WORDS ON ONE LINE, as dlerror gives them to Python.
                $words = (@($x.Message -split '\r?\n' | Where-Object { $_.Trim() }) -join ' ')
                throw [LibraryMissing]::new("libvterm cannot be loaded from '$given' -- $words`n$([Vterm]::INSTALL_HINT)")
            }
        } else {
            foreach ($candidate in [Vterm]::LIBRARY_NAME_LIST) {
                $h = [IntPtr]::Zero
                if ([System.Runtime.InteropServices.NativeLibrary]::TryLoad($candidate, [ref]$h)) { $handle = $h; $name = $candidate; break }
            }
            if ($null -eq $name) {
                throw [LibraryMissing]::new("libvterm is not installed, and '$([Vterm]::LIBRARY_VARIABLE)' names no file`n$([Vterm]::INSTALL_HINT)")
            }
        }
        [Vterm]::Compile()
        ([Vterm]::L)::Use($handle)
        #  ONLY 0.2 AND LATER hold an indexed colour that must be resolved.
        [Vterm]::_library = @{ name = $name; handle = $handle; convert_f = ([Vterm]::L)::Has($handle, 'vterm_screen_convert_color_to_rgb') }
        return [Vterm]::_library
    }

    <# RETURN: nothing; the native edge 'hwut_vterm_native.cs' is compiled (once per process) and its types are known. #>
    static hidden [void] Compile() {
        if ($null -ne [Vterm]::L) { return }
        if ($null -eq ('HwutVterm.Lib' -as [type])) {
            Add-Type -Path (Join-Path $PSScriptRoot 'hwut_vterm_native.cs')
        }
        [Vterm]::L = 'HwutVterm.Lib' -as [type]
        [Vterm]::P = 'HwutVterm.Posix' -as [type]
        [Vterm]::R = 'HwutVterm.Recorder' -as [type]
    }

    <#
    RETURN: nothing; the loaded library (and its measured layout) are
            forgotten, so the next Screen looks for it again under
            HWUT_LIBVTERM -- what Python's test does by 'hwut_vterm._library
            = None'.
    #>
    static [void] ForgetLibrary() { [Vterm]::_library = $null; [Vterm]::_layout = $null }

    <#
    RETURN: string, 'libvterm found: <name>', if the library loads; the text
            of LibraryMissing -- what is wrong and how to install it -- else.
    #>
    static [string] DetectionText() {
        try { return "libvterm found: $(([Vterm]::Library()).name)" }
        catch [LibraryMissing] { return $_.Exception.Message }
    }

    <# RETURN: double, a monotonic clock in seconds. #>
    static [double] Monotonic() { return [System.Diagnostics.Stopwatch]::GetTimestamp() / [double][System.Diagnostics.Stopwatch]::Frequency }

    <#
    RETURN: hashtable, where this library's cell keeps each attribute and
            each colour -- @{ mask_db = name -> @(offset, bits); foreground_i;
            background_i; convert_f; default_fg; default_bg } -- measured once
            on scratch terminals, then remembered.
    #>
    static [hashtable] Measured() {
        if ($null -ne [Vterm]::_layout) { return [Vterm]::_layout }
        $plain = [Vterm]::CellAfter('')
        $mask_db = @{}
        for ($k = 0; $k -lt [Vterm]::ATTRIBUTE_NAME_LIST.Count; $k++) {
            $found = [Vterm]::Changed($plain, [Vterm]::CellAfter([Vterm]::ATTRIBUTE_SGR_LIST[$k]))
            #  NOTHING MOVED: this library does not know the attribute.
            $mask_db[[Vterm]::ATTRIBUTE_NAME_LIST[$k]] = if ($found.Count -gt 0) { $found[0] } else { @(([Vterm]::CHARS_BYTE_N + 1), 0) }
        }
        #  UNDERLINE IS A NUMBER OF TWO BITS: any of them is 'underlined'.
        foreach ($pair in [Vterm]::Changed($plain, [Vterm]::CellAfter('21'))) {
            if ($pair[0] -eq $mask_db['underline'][0]) { $mask_db['underline'] = @($pair[0], ($mask_db['underline'][1] -bor $pair[1])) }
        }
        $foreground_i = [Vterm]::IndexOfRgb([Vterm]::CellAfter('38;2;1;2;3'))
        $background_i = [Vterm]::IndexOfRgb([Vterm]::CellAfter('48;2;1;2;3'))
        $convert_f    = ([Vterm]::Library()).convert_f
        #  THE DEFAULT IS WHAT A PLAIN CELL WEARS, read as every cell will be
        #  read from now on.
        [Vterm]::_layout = @{ mask_db = $mask_db; foreground_i = $foreground_i; background_i = $background_i
                              convert_f = $convert_f; default_fg = $null; default_bg = $null }
        $raw = [Vterm]::CellAfter('')
        [Vterm]::_layout.default_fg = [int[]]@($raw[$foreground_i], $raw[$foreground_i + 1], $raw[$foreground_i + 2])
        [Vterm]::_layout.default_bg = [int[]]@($raw[$background_i], $raw[$background_i + 1], $raw[$background_i + 2])
        return [Vterm]::_layout
    }

    <# RETURN: byte[], the raw cell (0, 0) of a scratch screen fed the SGR 'sequence' (none where empty), then 'X'. #>
    static hidden [byte[]] CellAfter([string]$sequence) {
        $scratch = [VtermScreen]::new(2, 4)
        try {
            if ($sequence) { [void]$scratch.Feed("`e[${sequence}m") }
            [void]$scratch.Feed('X')
            return $scratch.Raw(0, 0)
        } finally { $scratch.Close() }
    }

    <# RETURN: object[], @(offset, plain xor raw) for every byte past the characters and width where 'raw' differs from 'plain'. #>
    static hidden [object[]] Changed([byte[]]$plain, [byte[]]$raw) {
        $found = [System.Collections.Generic.List[object]]::new()
        for ($i = [Vterm]::CHARS_BYTE_N + 1; $i -lt [Vterm]::CELL_BYTE_N; $i++) {
            if ($plain[$i] -ne $raw[$i]) { $found.Add(@($i, ($plain[$i] -bxor $raw[$i]))) }
        }
        return $found.ToArray()
    }

    <# RETURN: int, the first offset past the characters and width where the bytes 1, 2, 3 stand in 'raw'; -1 where they do not. #>
    static hidden [int] IndexOfRgb([byte[]]$raw) {
        for ($i = [Vterm]::CHARS_BYTE_N + 1; $i -le [Vterm]::CELL_BYTE_N - 3; $i++) {
            if ($raw[$i] -eq 1 -and $raw[$i + 1] -eq 2 -and $raw[$i + 2] -eq 3) { return $i }
        }
        return -1
    }
}

class VtermScreen {
    [int] $row_n
    [int] $column_n
    hidden [IntPtr] $_terminal = [IntPtr]::Zero
    hidden [IntPtr] $_screen   = [IntPtr]::Zero
    hidden [IntPtr] $_state    = [IntPtr]::Zero

    <# RETURN: VtermScreen of 24 rows and 80 columns (see the two-argument constructor). #>
    VtermScreen() { $this.Open(24, 80) }

    <#
    RETURN: VtermScreen, a terminal of 'row_n' rows and 'column_n' columns,
            blank, the cursor at (0, 0); throws LibraryMissing, if 'libvterm'
            is not found. Call 'Close()' (or 'Use(block)'): the terminal is
            the library's memory, not .NET's.
    #>
    VtermScreen([int]$row_n, [int]$column_n) { $this.Open($row_n, $column_n) }

    <# RETURN: nothing; the constructors' body. #>
    hidden [void] Open([int]$row_n, [int]$column_n) {
        $this.row_n = $row_n; $this.column_n = $column_n
        [void][Vterm]::Library()
        $lib = [Vterm]::L
        $this._terminal = $lib::vterm_new($row_n, $column_n)
        $lib::vterm_set_utf8($this._terminal, 1)
        $this._screen = $lib::vterm_obtain_screen($this._terminal)
        $this._state  = $lib::vterm_obtain_state($this._terminal)
        #  THE ALTERNATE SCREEN IS OFF IN libvterm UNTIL ASKED FOR.
        $lib::vterm_screen_enable_altscreen($this._screen, 1)
        $lib::vterm_screen_reset($this._screen, 1)
    }

    <#
    RETURN: nothing; 'block' ran with this screen as its argument -- what it
            puts on the pipeline written to [Console]::Out as it comes --
            and the screen is closed after it, whatever way it ends:
            Python's 'with'.
    #>
    [void] Use([scriptblock]$block) {
        try     { & $block $this | ForEach-Object { [Console]::Out.WriteLine([string]$_) } }
        finally { $this.Close() }
    }

    <# RETURN: nothing. The terminal's memory is freed; a second call does nothing. #>
    [void] Close() {
        if ($this._terminal -ne [IntPtr]::Zero) {
            ([Vterm]::L)::vterm_free($this._terminal)
            $this._terminal = $this._screen = $this._state = [IntPtr]::Zero
        }
    }

    <#
    RETURN: long, the number of bytes the terminal took -- all of them, where
            it works as documented. 'data' is what a program wrote: a byte[],
            or a string sent as UTF-8.
    #>
    [long] Feed([object]$data) {
        $bytes = if ($data -is [byte[]]) { $data } else { [System.Text.UTF8Encoding]::new($false).GetBytes([string]$data) }
        return ([Vterm]::L)::InputWrite($this._terminal, $bytes)
    }

    <# RETURN: int[], @(row, column) of the cursor, from 0. #>
    [int[]] Cursor() { return ([Vterm]::L)::CursorPos($this._state) }

    <#
    RETURN: byte[] (CELL_BYTE_N), the library's own cell at that place, its
            colours resolved to red, green, blue where the library keeps them
            otherwise (once the layout is measured).
    #>
    [byte[]] Raw([int]$row, [int]$column) {
        $buffer = [byte[]]::new([Vterm]::CELL_BYTE_N)
        [void]([Vterm]::L)::GetCell($this._screen, $row, $column, $buffer)
        $layout = [Vterm]::_layout
        if ($null -ne $layout -and $layout.convert_f) {
            #  THE COLOUR'S STRUCTURE begins one byte before its red.
            ([Vterm]::L)::ConvertColours($this._screen, $buffer, [int[]]@(($layout.foreground_i - 1), ($layout.background_i - 1)))
        }
        return $buffer
    }

    <# RETURN: VtermCell, what stands at that place; throws IndexError, if the place is not on the screen. #>
    [VtermCell] Cell([int]$row, [int]$column) {
        if (-not ($row -ge 0 -and $row -lt $this.row_n -and $column -ge 0 -and $column -lt $this.column_n)) {
            throw [IndexError]::new("($row, $column) is not on a screen of $($this.row_n) x $($this.column_n)")
        }
        $layout = [Vterm]::Measured()
        $raw    = $this.Raw($row, $column)
        $cell   = [VtermCell]::new()
        $sb     = [System.Text.StringBuilder]::new()
        for ($i = 0; $i -lt [Vterm]::CHARS_BYTE_N; $i += 4) {
            $code = [System.BitConverter]::ToUInt32($raw, $i)
            if ($code -ne 0 -and $code -ne [uint32]::MaxValue) { [void]$sb.Append([char]::ConvertFromUtf32([int]$code)) }
        }
        $cell.text  = $sb.ToString()
        $cell.width = if ($raw[[Vterm]::CHARS_BYTE_N] -ne 0) { $raw[[Vterm]::CHARS_BYTE_N] } else { 1 }
        $cell.foreground = [VtermScreen]::Colour($raw, $layout.foreground_i, $layout.default_fg)
        $cell.background = [VtermScreen]::Colour($raw, $layout.background_i, $layout.default_bg)
        foreach ($name in [Vterm]::ATTRIBUTE_NAME_LIST) {
            $at = $layout.mask_db[$name]
            $cell."${name}_f" = ($raw[$at[0]] -band $at[1]) -ne 0
        }
        return $cell
    }

    <# RETURN: int[] @(red, green, blue) at offset 'i' of 'raw'; $null where it is 'default'. #>
    static hidden [object] Colour([byte[]]$raw, [int]$i, [int[]]$default) {
        $rgb = [int[]]@($raw[$i], $raw[$i + 1], $raw[$i + 2])
        if ($null -ne $default -and $default.Count -eq 3 -and $rgb[0] -eq $default[0] -and $rgb[1] -eq $default[1] -and $rgb[2] -eq $default[2]) { return $null }
        return $rgb
    }

    <# RETURN: string, the row's characters, blanks at its end dropped; a cell nothing was written to reads as a blank. #>
    [string] Line([int]$row) { return $this.TextOf($row, 0, $this.column_n) }

    <#
    RETURN: string, the characters of 'row' from 'column' for 'column_n'
            columns -- a wide character's right half skipped, an empty cell
            a blank -- blanks at the end dropped.
    #>
    [string] TextOf([int]$row, [int]$column, [int]$column_n) {
        $sb = [System.Text.StringBuilder]::new()
        $at = $column
        while ($at -lt $column + $column_n) {
            $cell = $this.Cell($row, $at)
            [void]$sb.Append($(if ($cell.text) { $cell.text } else { ' ' }))
            $at += [Math]::Max($cell.width, 1)
        }
        return [regex]::Replace($sb.ToString(), '\s+$', '')
    }

    <# RETURN: string[], every row as 'Line()' gives it, top first. #>
    [string[]] LineList() {
        $out = [string[]]::new($this.row_n)
        for ($row = 0; $row -lt $this.row_n; $row++) { $out[$row] = $this.Line($row) }
        return $out
    }
}

class VtermProcess {
    [int]    $pid
    [object] $returncode = $null

    <#
    RETURN: VtermProcess, the application 'argv' started on the
            pseudo-terminal whose slave is 'slave_path' (see
            HwutVterm.Posix.Spawn); 'environment' its environment as
            'NAME=value' entries; 'cwd' ($null: this one) its directory.
            Throws (InvalidOperationException, errno's number) where it
            cannot be started.
    #>
    VtermProcess([string[]]$argv, [string[]]$environment, [object]$cwd, [string]$slave_path) {
        $this.pid = ([Vterm]::P)::Spawn($argv, $environment, $slave_path, $cwd)
    }

    <#
    RETURN: object, the exit status -- minus the signal's number where a
            signal ended it -- where the application has ended; $null where
            it still runs.
    #>
    [object] Poll() {
        if ($null -ne $this.returncode) { return $this.returncode }
        $this.returncode = ([Vterm]::P)::WaitPid($this.pid, $false)
        return $this.returncode
    }

    <# RETURN: int, the exit status once the application has ended, waited for without bound. #>
    [int] Wait() { return $this.Wait(-1.0) }

    <#
    RETURN: int, the exit status (see 'Poll') once the application has
            ended; throws TimeoutError where it still runs after 'timeout_s'
            seconds (negative: wait for ever).
    #>
    [int] Wait([double]$timeout_s) {
        $deadline = if ($timeout_s -lt 0) { [double]::PositiveInfinity } else { [Vterm]::Monotonic() + $timeout_s }
        while ($null -eq $this.Poll()) {
            if ([Vterm]::Monotonic() -ge $deadline) { throw [TimeoutError]::new('TimeoutExpired') }
            [System.Threading.Thread]::Sleep(5)
        }
        return $this.returncode
    }

    <# RETURN: nothing. SIGKILL is sent, where the application still runs. #>
    [void] Kill() { if ($null -eq $this.Poll()) { ([Vterm]::P)::Kill($this.pid) } }
}

class VtermTerminal : VtermScreen {
    [double] $settle_s
    hidden [System.Collections.Generic.List[scriptblock]] $_event_f_list
    hidden [System.Collections.Generic.List[scriptblock]] $_change_f_list
    hidden [System.Collections.Specialized.OrderedDictionary] $_region_db   # name -> @(row, row_n, column, column_n)
    hidden [hashtable] $_told_db                                           # name -> the lines last told
    hidden [System.Collections.Generic.List[byte]] $_answer                # what the terminal said
    hidden [object] $_recorder
    hidden [object] $_master = $null
    hidden [object] $_process = $null
    hidden [bool]   $_ended_f = $false

    <# RETURN: VtermTerminal of 24 x 80, settling after 0.1 s (see the three-argument constructor). #>
    VtermTerminal() : base(24, 80) { $this.Setup(0.1) }
    <# RETURN: VtermTerminal of 'row_n' x 'column_n', settling after 0.1 s. #>
    VtermTerminal([int]$row_n, [int]$column_n) : base($row_n, $column_n) { $this.Setup(0.1) }

    <#
    RETURN: VtermTerminal, blank, nothing running in it; throws
            LibraryMissing, if 'libvterm' is not found. 'settle_s' is how
            long the application must write nothing before its screen is
            taken as drawn.

    TWO LAYERS OF OBSERVATION:
        OnEvent    RAW: every VtermEvent libvterm reports, as it happens.
        OnChange   REGIONS: a named rectangle's text, told once it has
                   CHANGED and the application has gone QUIET; one call per
                   changed region and pause, in declaration order.
    #>
    VtermTerminal([int]$row_n, [int]$column_n, [double]$settle_s) : base($row_n, $column_n) { $this.Setup($settle_s) }

    <# RETURN: nothing; the constructors' body: the callbacks registered (queued by the native Recorder). #>
    hidden [void] Setup([double]$settle_s) {
        $this.settle_s       = $settle_s
        $this._event_f_list  = [System.Collections.Generic.List[scriptblock]]::new()
        $this._change_f_list = [System.Collections.Generic.List[scriptblock]]::new()
        $this._region_db     = [System.Collections.Specialized.OrderedDictionary]::new([System.StringComparer]::Ordinal)
        $this._told_db       = [hashtable]::new([System.StringComparer]::Ordinal)
        $this._answer        = [System.Collections.Generic.List[byte]]::new()
        $this._recorder      = ([Vterm]::R)::new($this._terminal, $this._screen, [Vterm]::PLAIN_PROPERTY_LIST)
        ([Vterm]::L)::vterm_screen_set_damage_merge($this._screen, [Vterm]::DAMAGE_MERGE_ROW)
    }

    #  ------------------------------------------------------- observation
    <# RETURN: nothing. 'callback' is called with every raw VtermEvent from now on. #>
    [void] OnEvent([scriptblock]$callback) { $this._event_f_list.Add($callback) }

    <# RETURN: nothing. 'callback' is called with (name, line_list) for every region whose text changed, once the screen is quiet. #>
    [void] OnChange([scriptblock]$callback) { $this._change_f_list.Add($callback) }

    <# RETURN: nothing; 'Region(name, row, 1, 0, $null)'. #>
    [void] Region([string]$name, [int]$row) { $this.Region($name, $row, 1, 0, $null) }
    <# RETURN: nothing; 'Region(name, row, row_n, 0, $null)'. #>
    [void] Region([string]$name, [int]$row, [int]$row_n) { $this.Region($name, $row, $row_n, 0, $null) }

    <#
    RETURN: nothing. The rectangle 'name' is observed from now on: 'row_n'
            rows from 'row', 'column_n' columns from 'column' (to the right
            edge where $null). A NEGATIVE 'row' counts from the bottom: -1 is
            the last row. What stands there now is known, not news: only a
            change is told.
    #>
    [void] Region([string]$name, [int]$row, [int]$row_n, [int]$column, [object]$column_n) {
        if ($row -lt 0) { $row += $this.row_n }
        if ($null -eq $column_n) { $column_n = $this.column_n - $column }
        $this._region_db[$name] = [int[]]@($row, $row_n, $column, [int]$column_n)
        $this._told_db[$name]   = $this.RegionText($name)
    }

    <#
    RETURN: string[], the region's rows as they stand now, blanks at each
            row's end dropped; throws KeyError, if no such region was
            declared.
    #>
    [string[]] RegionText([string]$name) {
        if (-not $this._region_db.Contains($name)) { throw [KeyError]::new("'$name'") }
        $r = $this._region_db[$name]
        $result = [System.Collections.Generic.List[string]]::new()
        for ($each = $r[0]; $each -lt $r[0] + $r[1]; $each++) { $result.Add($this.TextOf($each, $r[2], $r[3])) }
        return $result.ToArray()
    }

    <#
    RETURN: string[], the names of the regions whose text differs from what
            was last told -- each told to every 'OnChange' callback, in the
            order of declaration.
    #>
    [string[]] Report() {
        $changed = [System.Collections.Generic.List[string]]::new()
        foreach ($name in @($this._region_db.Keys)) {
            $lineList = $this.RegionText($name)
            $told     = [string[]]$this._told_db[$name]
            if ([VtermText]::Same($told, $lineList)) { continue }
            $this._told_db[$name] = $lineList
            $changed.Add($name)
            foreach ($callback in $this._change_f_list) {
                & $callback $name $lineList | ForEach-Object { [Console]::Out.WriteLine([string]$_) }
            }
        }
        return $changed.ToArray()
    }

    <#
    RETURN: nothing. What libvterm reported since the last call reaches every
            raw callback, in the order reported; what the terminal said is
            kept for the application ('Forward', 'Answer').
    #>
    hidden [void] Drain() {
        foreach ($r in $this._recorder.TakeEvents()) {
            $event = [VtermEvent]::new($r)
            foreach ($callback in $this._event_f_list) {
                & $callback $event | ForEach-Object { [Console]::Out.WriteLine([string]$_) }
            }
        }
        $this._answer.AddRange([byte[]]$this._recorder.TakeAnswer())
    }

    #  --------------------------------------------------- bytes in and out
    <#
    RETURN: long, the number of bytes the terminal took. The raw events of
            what was fed fire before this returns; what the terminal
            answered goes to the application, where one runs.
    #>
    [long] Feed([object]$data) {
        $taken = ([VtermScreen]$this).Feed($data)
        ([Vterm]::L)::vterm_screen_flush_damage($this._screen)
        $this.Drain()
        $this.Forward()
        return $taken
    }

    <# RETURN: byte[], what the terminal said since the last call and no application took. #>
    [byte[]] Answer() {
        $this.Drain()
        $data = $this._answer.ToArray()
        $this._answer.Clear()
        return $data
    }

    <# RETURN: nothing. The terminal's words reach the application, if one runs; they wait in 'Answer()' otherwise. #>
    hidden [void] Forward() {
        $this.Drain()
        if ($null -eq $this._master -or $this._answer.Count -eq 0) { return }
        if (-not ([Vterm]::P)::Write([int]$this._master, $this._answer.ToArray())) { $this._ended_f = $true }
        $this._answer.Clear()
    }

    <# RETURN: bool, 'Send(text, 1.0)'. #>
    [bool] Send([string]$text) { return $this.Send($text, 1.0) }

    <#
    RETURN: bool, $true if the application still runs after it. 'text' is
            typed, character by character, as a keyboard sends it; then the
            screen is given 'react_s' to begin answering and is read until
            quiet.
    #>
    [bool] Send([string]$text, [double]$react_s) {
        for ($i = 0; $i -lt $text.Length; $i++) {
            $code = [char]::ConvertToUtf32($text, $i)
            if ($code -gt 0xFFFF) { $i++ }
            ([Vterm]::L)::vterm_keyboard_unichar($this._terminal, [uint32]$code, 0)
        }
        $this.Forward()
        return $this.Pump($react_s)
    }

    <# RETURN: bool, 'Press(key, @(), 1.0)'. #>
    [bool] Press([string]$key) { return $this.Press($key, @(), 1.0) }
    <# RETURN: bool, 'Press(key, modifier_list, 1.0)'. #>
    [bool] Press([string]$key, [string[]]$modifier_list) { return $this.Press($key, $modifier_list, 1.0) }

    <#
    RETURN: bool, $true if the application still runs after it; throws
            KeyError, if 'key' or a modifier has no name here. 'key' is a
            name of [Vterm]::KEY_DB ('enter', 'up', 'f5', ...) or one
            character; 'modifier_list' holds 'shift', 'alt', 'ctrl' --
            'Press("c", @("ctrl"))' is Ctrl-C.
    #>
    [bool] Press([string]$key, [string[]]$modifier_list, [double]$react_s) {
        $modifier = 0
        foreach ($name in @($modifier_list)) {
            if (-not [Vterm]::MODIFIER_DB.ContainsKey($name)) { throw [KeyError]::new("'$name'") }
            $modifier = $modifier -bor [Vterm]::MODIFIER_DB[$name]
        }
        $one = $key.Length -eq 1 -or ($key.Length -eq 2 -and [char]::IsSurrogatePair($key, 0))
        if ($one) {
            ([Vterm]::L)::vterm_keyboard_unichar($this._terminal, [uint32][char]::ConvertToUtf32($key, 0), $modifier)
        } else {
            if (-not [Vterm]::KEY_DB.ContainsKey($key)) { throw [KeyError]::new("'$key'") }
            ([Vterm]::L)::vterm_keyboard_key($this._terminal, [Vterm]::KEY_DB[$key], $modifier)
        }
        $this.Forward()
        return $this.Pump($react_s)
    }

    #  ------------------------------------------------------ the application
    <# RETURN: bool, 'Run(argv, $null, $null, 10.0)'. #>
    [bool] Run([string[]]$argv) { return $this.Run($argv, $null, $null, 10.0) }

    <#
    RETURN: bool, $true if the application still runs once its first screen
            stands; throws RuntimeError, if one already runs here.

    'argv' is started on a pseudo-terminal of this terminal's size: stdin,
    stdout and stderr are that terminal, and it is the application's
    controlling one. TERM is 'xterm-256color'; LINES and COLUMNS are taken OUT
    of the environment ('env', a dictionary; $null: this process's).
    #>
    [bool] Run([string[]]$argv, [object]$env, [object]$cwd, [double]$start_s) {
        if ($null -ne $this._process) { throw [RuntimeError]::new('an application already runs in this terminal') }
        $pair = try { ([Vterm]::P)::OpenPty($this.row_n, $this.column_n) } catch { throw [RuntimeError]::new($_.Exception.InnerException.Message) }
        $master = [int]$pair[0]
        $environment = [System.Collections.Generic.Dictionary[string, string]]::new([System.StringComparer]::Ordinal)
        $source = if ($null -eq $env) { [System.Environment]::GetEnvironmentVariables() } else { $env }
        foreach ($k in $source.Keys) { $environment[[string]$k] = [string]$source[$k] }
        $environment['TERM'] = 'xterm-256color'
        [void]$environment.Remove('LINES'); [void]$environment.Remove('COLUMNS')
        $envp = [string[]]@(foreach ($k in $environment.Keys) { "$k=$($environment[$k])" })
        $this._master = $master
        try {
            $this._process = [VtermProcess]::new($argv, $envp, $cwd, [string]$pair[1])
        } catch {
            ([Vterm]::P)::Close($master); $this._master = $null
            throw
        }
        $this._ended_f = $false
        return $this.Pump($start_s)
    }

    <# RETURN: bool, 'Pump(1.0)'. #>
    [bool] Pump() { return $this.Pump(1.0) }

    <#
    RETURN: bool, $true if the application still runs. READ UNTIL QUIET:
            wait up to 'first_s' for the application to write at all, then
            go on reading until it has written nothing for 'settle_s'. Then
            the changed regions are reported.
    #>
    [bool] Pump([double]$first_s) {
        $wait_s = $first_s
        $posix  = [Vterm]::P
        while ($null -ne $this._master -and -not $this._ended_f) {
            $ready = $posix::Readable([int]$this._master, [int][Math]::Round($wait_s * 1000))
            if ($ready -le 0) { break }
            $data = $posix::Read([int]$this._master, 65536)
            if ($data.Length -eq 0) { $this._ended_f = $true; break }    # the last writer closed: it ended
            [void]$this.Feed($data)
            $wait_s = $this.settle_s
        }
        [void]$this.Report()
        return $null -ne $this._process -and $null -eq $this._process.Poll() -and -not $this._ended_f
    }

    <# RETURN: int[], 'Expect(text, 10.0)'. #>
    [int[]] Expect([string]$text) { return $this.Expect($text, 10.0) }

    <#
    RETURN: int[], @(row, column) where 'text' stands on the screen, once it
            does; throws TimeoutError, carrying the screen, if it does not
            within 'timeout_s'.
    #>
    [int[]] Expect([string]$text, [double]$timeout_s) {
        $deadline = [Vterm]::Monotonic() + $timeout_s
        while ($true) {
            $lineList = $this.LineList()
            for ($row = 0; $row -lt $lineList.Count; $row++) {
                $at = $lineList[$row].IndexOf($text, [System.StringComparison]::Ordinal)
                if ($at -ge 0) { return [int[]]@($row, [VtermText]::CodePointLength($lineList[$row].Substring(0, $at))) }
            }
            if ([Vterm]::Monotonic() -ge $deadline -or $this._ended_f -or $null -eq $this._master) {
                throw [TimeoutError]::new("'$text' did not appear; the screen:`n$($lineList -join "`n")")
            }
            [void]$this.Pump($this.settle_s)
        }
        return $null
    }

    <# RETURN: object, 'Wait(10.0)'. #>
    [object] Wait() { return $this.Wait(10.0) }

    <#
    RETURN: object, the application's exit status (int), once it has ended
            and its last words are on the screen; $null, if no application
            was run; throws TimeoutError, if it still runs after 'timeout_s'
            -- it is killed first.
    #>
    [object] Wait([double]$timeout_s) {
        if ($null -eq $this._process) { return $null }
        $deadline = [Vterm]::Monotonic() + $timeout_s
        while ($this.Pump($this.settle_s)) {
            if ([Vterm]::Monotonic() -ge $deadline) {
                $this._process.Kill(); [void]$this._process.Wait()
                throw [TimeoutError]::new("the application still ran after $($timeout_s.ToString('0.0', [cultureinfo]::InvariantCulture)) s")
            }
        }
        try {
            return $this._process.Wait([Math]::Max($deadline - [Vterm]::Monotonic(), 0.1))
        } catch [TimeoutError] {
            $this._process.Kill(); [void]$this._process.Wait()
            throw [TimeoutError]::new('the application closed its terminal and did not end')
        }
    }

    <#
    RETURN: nothing. An application still running is killed (and reaped),
            the pseudo-terminal closed, the callbacks released, the
            terminal's memory freed; a second call does nothing.
    #>
    [void] Close() {
        if ($null -ne $this._process -and $null -eq $this._process.Poll()) {
            $this._process.Kill(); [void]$this._process.Wait()
        }
        if ($null -ne $this._master) { ([Vterm]::P)::Close([int]$this._master); $this._master = $null }
        $wasOpen = $this._terminal -ne [IntPtr]::Zero
        ([VtermScreen]$this).Close()
        if ($wasOpen -and $null -ne $this._recorder) { $this._recorder.Dispose(); $this._recorder = $null }
    }
}

class VtermText {
    <# RETURN: int, the number of code points of 's' (a surrogate pair counts one). #>
    static [int] CodePointLength([string]$s) {
        $n = $s.Length
        foreach ($c in $s.ToCharArray()) { if ([char]::IsLowSurrogate($c)) { $n-- } }
        return $n
    }

    <# RETURN: bool, $true where 'a' and 'b' hold the same strings in the same order (by case); $false else, or where 'a' is $null. #>
    static [bool] Same([string[]]$a, [string[]]$b) {
        if ($null -eq $a -or $null -eq $b -or $a.Count -ne $b.Count) { return $false }
        for ($i = 0; $i -lt $a.Count; $i++) { if ($a[$i] -cne $b[$i]) { return $false } }
        return $true
    }
}

<# RETURN: string, 'libvterm found: <name>' where the library loads; what is wrong and how to install it, else. #>
function Get-VtermDetection { [Vterm]::DetectionText() }

Export-ModuleMember -Function Get-VtermDetection
