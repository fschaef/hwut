"""sheet.py -- a small model of a spreadsheet's CSV import and export.

A cell is typed at import time. 'smart' imports guess the type the way a
spreadsheet's General format does: a month name followed by a day number is
a date of the current year, a digit string with an 'E' and digits is a number
in scientific notation; everything else is text. 'text' imports keep every
cell as text (the column type 'Text', or pandas' dtype=str).

Export writes each cell as the sheet DISPLAYS it: a date as '2-Sep', a large
number as '2.31E+13' -- the original spelling is gone.
"""
import re

MONTH_DB = {"JAN": 1, "JANUARY": 1, "FEB": 2, "FEBRUARY": 2, "MAR": 3, "MARCH": 3,
            "APR": 4, "APRIL": 4, "MAY": 5, "JUN": 6, "JUNE": 6, "JUL": 7, "JULY": 7,
            "AUG": 8, "AUGUST": 8, "SEP": 9, "SEPT": 9, "SEPTEMBER": 9, "OCT": 10,
            "OCTOBER": 10, "NOV": 11, "NOVEMBER": 11, "DEC": 12, "DECEMBER": 12}
MONTH_NAME = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def import_cell(text, mode):
    """RETURN: (type, value) -- type is 'text', 'date' or 'number'."""
    if mode == "smart":
        m = re.fullmatch(r"([A-Za-z]+)-?(\d{1,2})", text)
        if m and m.group(1).upper() in MONTH_DB and 1 <= int(m.group(2)) <= 31:
            return "date", (MONTH_DB[m.group(1).upper()], int(m.group(2)))
        if re.fullmatch(r"\d+(\.\d+)?[Ee][+-]?\d+", text) or re.fullmatch(r"-?\d+(\.\d+)?", text):
            return "number", float(text)
    return "text", text


def export_cell(cell):
    """RETURN: the cell as the sheet displays it, which is what 'Save as CSV' writes."""
    kind, value = cell
    if kind == "date":
        return "%d-%s" % (value[1], MONTH_NAME[value[0]])
    if kind == "number":
        if abs(value) >= 1e11:
            mantissa, exponent = ("%.2E" % value).split("E")
            return "%sE+%d" % (mantissa, int(exponent))
        return ("%.4f" % value).rstrip("0").rstrip(".") if value != int(value) else "%d" % value
    return value


def save_significant(path, header, sheet_rows, padj_column, cutoff=0.05):
    """Writes 'Save as CSV' of the rows whose p-value cell is below 'cutoff':
    the header line first, then the columns before 'padj_column', as displayed.
    Duplicate rows are dropped through a set -- so the ROW ORDER of the file
    is the set's iteration order, which for strings changes from process to
    process (hash randomisation). RETURN: number of rows written."""
    keep = {tuple(export_cell(c) for c in row[:padj_column])
            for row in sheet_rows if float(export_cell(row[padj_column])) < cutoff}
    with open(path, "w") as f:
        f.write(",".join(header[:padj_column]) + "\n")
        for row in keep:
            f.write(",".join(row) + "\n")
    return len(keep)
