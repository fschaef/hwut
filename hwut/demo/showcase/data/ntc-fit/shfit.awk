# shfit.awk -- fit the Steinhart-Hart equation to an NTC calibration table.
#
#     awk -f shfit.awk table.txt        lines: "<degC> <ohm>", '#' comments
#
#     1/T = a + b ln(R) + c ln(R)^3       (T in kelvin)
#
# Least squares over all rows (normal equations, Gaussian elimination).
# Prints the coefficients, then per row: degC, ohm, fitted degC, residual.
/^#/ || NF < 2 { next }
{ n++; t[n] = $1; r[n] = $2 }
END {
    for (i = 1; i <= n; i++) {
        x = log(r[i]); f[1] = 1; f[2] = x; f[3] = x * x * x; y = 1 / (t[i] + 273.15)
        for (j = 1; j <= 3; j++) { v[j] += f[j] * y; for (k = 1; k <= 3; k++) m[j, k] += f[j] * f[k] }
    }
    for (p = 1; p <= 3; p++)                                 # eliminate
        for (j = p + 1; j <= 3; j++) {
            q = m[j, p] / m[p, p]
            for (k = p; k <= 3; k++) m[j, k] -= q * m[p, k]
            v[j] -= q * v[p]
        }
    for (j = 3; j >= 1; j--) {                               # back-substitute
        s = v[j]; for (k = j + 1; k <= 3; k++) s -= m[j, k] * c[k]
        c[j] = s / m[j, j]
    }
    printf "a %.6e\nb %.6e\nc %.6e\n", c[1], c[2], c[3]
    for (i = 1; i <= n; i++) {
        x = log(r[i]); fit = 1 / (c[1] + c[2] * x + c[3] * x * x * x) - 273.15
        printf "%d %d %.3f %+.3f\n", t[i], r[i], fit, fit - t[i]
    }
}
