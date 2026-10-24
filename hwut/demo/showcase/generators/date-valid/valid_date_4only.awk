# valid_date_4only.awk -- the same with the "every fourth year" leap rule of an older script.
# (valid Gregorian date or not). Used by an import job to reject bad rows.
function leap(y) { return y % 4 == 0 }
function days_in(y, m) {
    if (m == 2) return leap(y) ? 29 : 28
    if (m == 4 || m == 6 || m == 9 || m == 11) return 30
    return 31
}
{
    y = $1; m = $2; d = $3
    ok = (m >= 1 && m <= 12 && d >= 1 && d <= days_in(y, m))
    print y, m, d, ok ? 1 : 0
}
