# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#_____________________________________________________________________________
#
# PURPOSE: EVERY COMBINATION OF A PARAMETER BASIS -- the port of
#          'python/space_iterator.py'. The cartesian product of a basis (a
#          list of lists), the RIGHTMOST dimension changing fastest:
#
#     using module ../space_iterator.psm1
#     foreach ($point in [SpaceIterator]::Do(@(@(0, 2), @('otto'), @(1, 2)))) {
#         $x, $name, $number = $point
#     }
#
#     $it = [SpaceIterator]::new($basis)          # lazily, one point a call
#     while ($it.Next()) { ... $it.point ... }
#
# An empty basis yields exactly one point, the empty array; a basis with an
# empty dimension yields nothing.
#_____________________________________________________________________________
Set-StrictMode -Version 3.0

class SpaceIterator {
    [object[]] $point                       # the current point, after 'Next()'
    hidden [object[]] $pool
    hidden [int[]]    $index
    hidden [bool]     $startedF
    hidden [bool]     $doneF

    <#
    RETURN: SpaceIterator over 'basis' -- each element one dimension (an
            enumerable; a scalar is a dimension of one value) -- before its
            first point.
    #>
    SpaceIterator([object[]]$basis) {
        if ($null -eq $basis) { $basis = @() }
        $this.pool  = [object[]]::new($basis.Count)
        for ($d = 0; $d -lt $basis.Count; $d++) { $this.pool[$d] = [object[]]@($basis[$d]) }
        $this.index = [int[]]::new($basis.Count)
        $this.doneF = $false
        foreach ($dim in $this.pool) { if ($dim.Count -eq 0) { $this.doneF = $true } }
        $this.startedF = $false
        $this.point    = $null
    }

    <#
    RETURN: bool, $true where 'point' now holds the next point of the
            product (one value of every dimension, in basis order); $false
            where the product is exhausted ('point' $null).
    #>
    [bool] Next() {
        if ($this.doneF) { $this.point = $null; return $false }
        if ($this.startedF) {
            $d = $this.pool.Count - 1
            while ($d -ge 0) {
                $this.index[$d]++
                if ($this.index[$d] -lt $this.pool[$d].Count) { break }
                $this.index[$d] = 0
                $d--
            }
            if ($d -lt 0) { $this.doneF = $true; $this.point = $null; return $false }
        }
        $this.startedF = $true
        $p = [object[]]::new($this.pool.Count)
        for ($d = 0; $d -lt $this.pool.Count; $d++) { $p[$d] = $this.pool[$d][$this.index[$d]] }
        $this.point = $p
        return $true
    }

    <#
    RETURN: System.Collections.Generic.List[object], every point of 'basis'
            (each an object[]), the rightmost dimension fastest -- Python's
            'space_iterator.do(basis)'; one empty point for an empty basis;
            none where a dimension is empty.
    #>
    static [System.Collections.Generic.List[object]] Do([object[]]$basis) {
        $result = [System.Collections.Generic.List[object]]::new()
        $it = [SpaceIterator]::new($basis)
        while ($it.Next()) { $result.Add($it.point) }
        return $result
    }
}
