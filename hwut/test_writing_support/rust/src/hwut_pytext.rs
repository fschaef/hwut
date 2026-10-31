// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
//______________________________________________________________________________
//
// PURPOSE: TEXT AS PYTHON PRINTS IT -- so a Rust test and a Python test of the
//          same module print the same bytes and share one GOOD file by a
//          '.link' (bookkeeper B-32). The Rust twin of 'c/hwut_pytext.c' and
//          'perl/Hwut/PyText.pm'.
//
//     float_repr(0.1)            "0.1"        the shortest text that reads
//     float_repr(1e-05)          "1e-05"      back; exponential below 1e-4
//     float_repr(1e16)           "1e+16"      and from 1e16 on
//     str_repr("it's")           "\"it's\""   Python's choice of quotes
//     bytes_repr(b"\x1b[A")      "b'\\x1b[A'"
//     bool_text(true)            "True"
//
//     use hwut::hwut_pytext::PyRepr;
//     vec!["a", "b"].py_repr()           "['a', 'b']"
//     Some(("x",)).py_repr()             "('x',)"
//     None::<i64>.py_repr()              "None"
//     PyTuple(&["a", "b"]).py_repr()     "('a', 'b')"
//
// RUST'S '{}' FOR f64 is the shortest text that reads back, as Python's repr
// is, but lays it out otherwise ('1e-6', '6.02e23') and breaks an exact tie
// of the last digit upward where Python rounds to even: the digits are the
// first correctly rounded '{:.Ne}' that reads back, laid out as Python lays
// them out.
//______________________________________________________________________________

/// What Python's 'repr()' writes of a value.
pub trait PyRepr {
    /// RETURN: String, the value as Python's 'repr()' writes it.
    fn py_repr(&self) -> String;
}

/// RETURN: String, 'x' as Python's 'repr(float)' writes it -- the shortest
///         decimal that reads back to the same double, fixed notation where
///         the decimal point falls in (-4, 16], exponential else ('1e-05',
///         '1e+16'); 'nan', 'inf', '-inf', '-0.0' as Python names them.
pub fn float_repr(x: f64) -> String {
    if x.is_nan() { return "nan".to_string(); }
    if x.is_infinite() { return if x < 0.0 { "-inf" } else { "inf" }.to_string(); }
    if x == 0.0 { return if x.is_sign_negative() { "-0.0" } else { "0.0" }.to_string(); }
    //  THE SHORTEST CORRECTLY ROUNDED DIGITS THAT READ BACK -- Python's
    //  choice. '{:e}' alone is shortest too, but breaks an exact tie upward
    //  (160141142283143.125 -> '...13'), where Python rounds to even.
    let text = (0..17).map(|p| format!("{:.*e}", p, x))
                      .find(|t| t.parse::<f64>() == Ok(x)).unwrap_or_else(|| format!("{:e}", x));
    let (mantissa, exponent) = text.split_once('e').unwrap();
    let exponent: i32 = exponent.parse().unwrap();
    let (sign, mantissa) = match mantissa.strip_prefix('-') {
        Some(rest) => ("-", rest),
        None       => ("", mantissa),
    };
    let mut digits: String = mantissa.chars().filter(|c| *c != '.').collect();
    while digits.len() > 1 && digits.ends_with('0') { digits.pop(); }
    let n     = digits.len() as i32;
    let point = exponent + 1;                    // value = 0.<digits> * 10^point
    let body = if point > -4 && point <= 16 {
        if point <= 0 {
            format!("0.{}{}", "0".repeat((-point) as usize), digits)
        } else if point >= n {
            format!("{}{}.0", digits, "0".repeat((point - n) as usize))
        } else {
            format!("{}.{}", &digits[..point as usize], &digits[point as usize..])
        }
    } else {
        let e    = point - 1;
        let sign = if e < 0 { '-' } else { '+' };
        if n > 1 { format!("{}.{}e{}{:02}", &digits[..1], &digits[1..], sign, e.abs()) }
        else     { format!("{}e{}{:02}", digits, sign, e.abs()) }
    };
    format!("{}{}", sign, body)
}

/// RETURN: String, 'data' in the quotes Python's repr chooses -- single, or
///         double where it holds a single quote and no double one -- with the
///         backslash, that quote and what does not print escaped. Where
///         'bytes_f', a 'b' leads and every byte from 0x7f on is escaped; a
///         str keeps its UTF-8 from 0x80 on as it stands.
fn quoted(data: &[u8], bytes_f: bool) -> String {
    let single_f = data.contains(&b'\'');
    let double_f = data.contains(&b'"');
    let quote    = if single_f && !double_f { b'"' } else { b'\'' };
    let mut out: Vec<u8> = Vec::with_capacity(data.len() + 3);
    if bytes_f { out.push(b'b'); }
    out.push(quote);
    for &c in data {
        match c {
            b'\\'                => out.extend_from_slice(b"\\\\"),
            _ if c == quote      => { out.push(b'\\'); out.push(quote); }
            b'\n'                => out.extend_from_slice(b"\\n"),
            b'\t'                => out.extend_from_slice(b"\\t"),
            b'\r'                => out.extend_from_slice(b"\\r"),
            _ if c < 0x20 || c == 0x7f || (bytes_f && c >= 0x80)
                                 => out.extend_from_slice(format!("\\x{:02x}", c).as_bytes()),
            _                    => out.push(c),
        }
    }
    out.push(quote);
    String::from_utf8_lossy(&out).into_owned()
}

/// RETURN: String, 'text' as Python's 'repr(str)' writes it.
pub fn str_repr(text: &str) -> String { quoted(text.as_bytes(), false) }

/// RETURN: String, 'data' as Python's 'repr(bytes)' writes it: b'...'.
pub fn bytes_repr(data: &[u8]) -> String { quoted(data, true) }

/// RETURN: &str, "True" where 'value', "False" else.
pub fn bool_text(value: bool) -> &'static str { if value { "True" } else { "False" } }

/// A byte string, printed as Python prints 'bytes'.
pub struct PyBytes<'a>(pub &'a [u8]);

/// A sequence printed as Python prints a TUPLE: '()', '(x,)', '(x, y)'.
pub struct PyTuple<'a, T: PyRepr>(pub &'a [T]);

impl PyRepr for f64  { fn py_repr(&self) -> String { float_repr(*self) } }
impl PyRepr for bool { fn py_repr(&self) -> String { bool_text(*self).to_string() } }
impl PyRepr for str  { fn py_repr(&self) -> String { str_repr(self) } }
impl PyRepr for String { fn py_repr(&self) -> String { str_repr(self) } }
impl PyRepr for PyBytes<'_> { fn py_repr(&self) -> String { bytes_repr(self.0) } }

macro_rules! integer_repr {
    ($($t:ty),*) => { $( impl PyRepr for $t { fn py_repr(&self) -> String { self.to_string() } } )* };
}
integer_repr!(i8, i16, i32, i64, i128, isize, u8, u16, u32, u64, u128, usize);

impl<T: PyRepr + ?Sized> PyRepr for &T { fn py_repr(&self) -> String { (**self).py_repr() } }

impl<T: PyRepr> PyRepr for Option<T> {
    fn py_repr(&self) -> String {
        match self { Some(value) => value.py_repr(), None => "None".to_string() }
    }
}

impl<T: PyRepr> PyRepr for [T] {
    fn py_repr(&self) -> String {
        format!("[{}]", self.iter().map(|x| x.py_repr()).collect::<Vec<_>>().join(", "))
    }
}

impl<T: PyRepr> PyRepr for Vec<T> { fn py_repr(&self) -> String { self.as_slice().py_repr() } }

impl<T: PyRepr> PyRepr for PyTuple<'_, T> {
    fn py_repr(&self) -> String {
        let item: Vec<String> = self.0.iter().map(|x| x.py_repr()).collect();
        if item.len() == 1 { format!("({},)", item[0]) } else { format!("({})", item.join(", ")) }
    }
}

impl<A: PyRepr> PyRepr for (A,) {
    fn py_repr(&self) -> String { format!("({},)", self.0.py_repr()) }
}
impl<A: PyRepr, B: PyRepr> PyRepr for (A, B) {
    fn py_repr(&self) -> String { format!("({}, {})", self.0.py_repr(), self.1.py_repr()) }
}
impl<A: PyRepr, B: PyRepr, C: PyRepr> PyRepr for (A, B, C) {
    fn py_repr(&self) -> String {
        format!("({}, {}, {})", self.0.py_repr(), self.1.py_repr(), self.2.py_repr())
    }
}
