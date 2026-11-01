# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#_____________________________________________________________________________
#
# PURPOSE: A RANDOM STREAM THAT IS THE SAME EVERYWHERE -- the port of
#          'python/deterministic_random.py'. The same seed gives the same
#          numbers as the Python module, draw for draw: the core is Park-Miller
#          MINSTD, 'state = 48271 * state mod (2^31 - 1)', in [long] (the
#          product stays below 2^47).
#
#     using module ../deterministic_random.psm1
#     $s = [DeterministicStream]::new(0x42)
#     $s.NextInt(0, 9);         $s.NextFloat();       $s.Coin(0.5)
#     $s.Select($pool);         $s.Choice($pool);     $s.Gauss(0, 1)
#     $s.SampleIndices(10, 3);  $s.Sample($pool, 3)
#     $m = [SelectionMarker]::new()
#     $s.SelectUnchosen($pool, $m)        # prefers what '$m' has not seen
#
# THE NAMES are Python's in PowerShell's casing: 'next_int' is 'NextInt',
# 'select_unchosen' 'SelectUnchosen', 'sample_indices' 'SampleIndices'.
#
# 'Gauss' is the one path through the platform's libm, as in Python: .NET's
# Math.Log, Math.Cos and Math.Sqrt call the C library's on Linux, so the bits
# are Python's on the same machine (MEASURED, RATIONALE PS-1); a GOOD that
# prints a draw tolerates the last digits all the same.
#
# IDENTITY: Python's marker remembers candidates by 'id(object)'. Here a
# candidate is remembered by .NET's equality -- an object by its identity, a
# string or a number by its value: two equal strings are one candidate, as in
# the Perl and the node port.
#_____________________________________________________________________________
Set-StrictMode -Version 3.0

class SelectionMarker {
    [System.Collections.Generic.HashSet[object]] $chosen

    <# RETURN: SelectionMarker, with nothing chosen yet. #>
    SelectionMarker() { $this.chosen = [System.Collections.Generic.HashSet[object]]::new() }

    <# RETURN: nothing. Forgets every chosen candidate; the next cycle restarts. #>
    [void] Reset() { $this.chosen.Clear() }
}

class DeterministicStream {
    [long] $state

    <# RETURN: DeterministicStream seeded with 0x42. #>
    DeterministicStream() { $this.state = 0x42 }

    <# RETURN: DeterministicStream seeded with 'seed'; the state is 'seed -band 0x7FFFFFFF'. #>
    DeterministicStream([long]$seed) { $this.state = $seed -band 0x7FFFFFFFL }

    <#
    RETURN: long, uniform in [v_min, v_max]. The state steps even where the
            range is a single value.
    #>
    [long] NextInt([long]$v_min, [long]$v_max) {
        $this.state = (48271L * $this.state) % 2147483647L
        if ($v_min -eq $v_max) { return $v_min }
        return $v_min + ($this.state % ($v_max - $v_min + 1))
    }

    <# RETURN: double, in [0, 1): 1000001 values, 'NextInt(0, 1000000) / 1000001'. #>
    [double] NextFloat() { return [double]$this.NextInt(0, 1000000) / 1000001.0 }

    <#
    RETURN: bool, $true with probability 'p', $false else -- resolved in steps
            of 1/1000001.
    #>
    [bool] Coin([double]$p) { return $this.NextFloat() -lt $p }

    <# RETURN: object, one element of the list (or string) 'candidates', uniformly drawn. #>
    [object] Select([object]$candidates) {
        if ($candidates -is [string]) { return [string]$candidates[$this.NextInt(0, $candidates.Length - 1)] }
        return $candidates[$this.NextInt(0, $candidates.Count - 1)]
    }

    <# RETURN: object, one element of the list 'seq', uniformly drawn. #>
    [object] Choice([object]$seq) { return $this.Select($seq) }

    <#
    RETURN: object, one candidate the marker has not seen, uniformly drawn
            among those -- recorded in the marker. Where every candidate was
            seen, the marker is reset and the draw is over all of them.
    #>
    [object] SelectUnchosen([object]$candidates, [SelectionMarker]$marker) {
        $all = if ($candidates -is [string]) { [object[]]$candidates.ToCharArray().ForEach({ [string]$_ }) } else { [object[]]@($candidates) }
        $unchosen = [System.Collections.Generic.List[object]]::new()
        foreach ($c in $all) { if (-not $marker.chosen.Contains($c)) { $unchosen.Add($c) } }
        if ($unchosen.Count -eq 0) {
            $marker.Reset()
            $unchosen.AddRange($all)
        }
        $pick = $unchosen[$this.NextInt(0, $unchosen.Count - 1)]
        [void]$marker.chosen.Add($pick)
        return $pick
    }

    <# RETURN: double, a draw of the normal distribution (mu, sigma), unclipped. #>
    [double] Gauss([double]$mu, [double]$sigma) {
        return $this.Gauss($mu, $sigma, [double]::NegativeInfinity, [double]::PositiveInfinity)
    }

    <#
    RETURN: double, a draw of the normal distribution (mu, sigma) by the
            Box-Muller transform, clipped to [lower, upper].
    #>
    [double] Gauss([double]$mu, [double]$sigma, [double]$lower, [double]$upper) {
        $u1 = $this.NextFloat() + 1e-9
        $u2 = $this.NextFloat()
        $z0 = [Math]::Sqrt(-2.0 * [Math]::Log($u1)) * [Math]::Cos(2.0 * [Math]::PI * $u2)
        $result = $z0 * $sigma + $mu
        if ($result -lt $lower) { return $lower }
        if ($result -gt $upper) { return $upper }
        return $result
    }

    <# RETURN: long, 'Gauss(mu, sigma)' rounded to the nearest -- a half to the even one. #>
    [long] GaussInt([double]$mu, [double]$sigma) {
        return $this.GaussInt($mu, $sigma, [double]::NegativeInfinity, [double]::PositiveInfinity)
    }

    <# RETURN: long, 'Gauss(mu, sigma, lower, upper)' rounded to the nearest -- a half to the even one, as Python's 'round'. #>
    [long] GaussInt([double]$mu, [double]$sigma, [double]$lower, [double]$upper) {
        return [long][Math]::Round($this.Gauss($mu, $sigma, $lower, $upper), [MidpointRounding]::ToEven)
    }

    <#
    RETURN: long[], 'k' distinct indices of 0 .. population_size - 1, drawn
            by Fisher-Yates; throws ArgumentException where k > population_size.
    #>
    [long[]] SampleIndices([long]$population_size, [long]$k) {
        if ($k -gt $population_size) { throw [System.ArgumentException]::new("SampleIndices: $k > $population_size") }
        $index  = [long[]]::new($population_size)
        for ($i = 0; $i -lt $population_size; $i++) { $index[$i] = $i }
        $result = [long[]]::new($k)
        for ($i = 0; $i -lt $k; $i++) {
            $j = $this.NextInt($i, $population_size - 1)
            $t = $index[$i]; $index[$i] = $index[$j]; $index[$j] = $t
            $result[$i] = $index[$i]
        }
        return $result
    }

    <# RETURN: object[], 'n' distinct elements of the list 'population'. #>
    [object[]] Sample([object[]]$population, [long]$n) {
        $pick = $this.SampleIndices($population.Count, $n)
        $result = [object[]]::new($pick.Count)
        for ($i = 0; $i -lt $pick.Count; $i++) { $result[$i] = $population[$pick[$i]] }
        return $result
    }
}
