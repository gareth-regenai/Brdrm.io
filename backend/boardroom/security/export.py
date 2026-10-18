"""Formula injection is neutralised on export (FR-11.7). A cell starting with one of these
characters would run as a formula when the CSV or spreadsheet is opened."""

FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r")


def safe_cell(value: str) -> str:
    if value.startswith(FORMULA_STARTS):
        # A negative number is a number, not a formula.
        if value[0] == "-" and value[1:].replace(".", "", 1).replace(",", "").isdigit():
            return value
        return "'" + value
    return value
