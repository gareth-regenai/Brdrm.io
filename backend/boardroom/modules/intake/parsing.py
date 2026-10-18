"""Turns an uploaded file into a table of text cells, in a child process with memory and
time limits (FR-11.7). Nothing here interprets meaning: that is skill 1's job."""

import csv
import io
import json
import resource
import subprocess
import sys
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

from boardroom.config import get_settings


class ParseError(Exception):
    """A file that cannot be read. The message is shown to the person who uploaded it."""


@dataclass
class Table:
    headers: list[str]
    rows: list[list[str]]
    # Lines above the header row, such as a report title or "For the month ended ...".
    preamble: list[str] = field(default_factory=list)
    sheet: str | None = None
    source_format: str = "csv"


@dataclass(frozen=True)
class Limits:
    max_rows: int
    max_columns: int
    max_cell_chars: int
    max_uncompressed_bytes: int
    memory_bytes: int
    seconds: int


def limits() -> Limits:
    s = get_settings()
    return Limits(
        max_rows=s.max_rows,
        max_columns=s.max_columns,
        max_cell_chars=s.max_cell_chars,
        max_uncompressed_bytes=s.max_uncompressed_mb * 1024 * 1024,
        memory_bytes=s.parse_memory_mb * 1024 * 1024,
        seconds=s.parse_seconds,
    )


# Format detection and decoding


def _decode(data: bytes) -> str:
    if data.startswith(b"\xef\xbb\xbf"):
        return data[3:].decode("utf-8")
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        # Excel on Windows still writes CSVs in this code page.
        return data.decode("cp1252", errors="replace")


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat() if value.time() == time(0) else value.isoformat(" ")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else repr(value)
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    return str(value).strip()


def _read_csv(text: str, lim: Limits) -> list[list[str]]:
    if "\x00" in text:
        raise ParseError("This file looks like a binary file, not a spreadsheet.")
    sample = text[:65536]
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        delimiter = ","
    csv.field_size_limit(lim.max_cell_chars)
    rows: list[list[str]] = []
    try:
        for row in csv.reader(io.StringIO(text), delimiter=delimiter):
            if len(rows) >= lim.max_rows + 50:
                raise ParseError(f"This file has more than {lim.max_rows:,} rows.")
            if len(row) > lim.max_columns:
                raise ParseError(f"This file has more than {lim.max_columns} columns.")
            rows.append([c.strip() for c in row])
    except csv.Error as exc:
        raise ParseError("A cell in this file is too long to read.") from exc
    return rows


def _read_xlsx(data: bytes, lim: Limits) -> tuple[list[list[str]], str]:
    import openpyxl  # imported in the child process only

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            total = sum(info.file_size for info in zf.infolist())
    except zipfile.BadZipFile as exc:
        raise ParseError("This Excel file is damaged. Save it again and re-upload.") from exc
    if total > lim.max_uncompressed_bytes:
        raise ParseError("This Excel file expands to more data than we can read.")

    try:
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:  # openpyxl raises many types for malformed workbooks
        raise ParseError(
            "This Excel file could not be opened. Save it again and re-upload."
        ) from exc
    best: tuple[list[list[str]], str] = ([], "")
    for ws in wb.worksheets[:10]:
        rows: list[list[str]] = []
        for values in ws.iter_rows(values_only=True):
            if len(rows) >= lim.max_rows + 50:
                raise ParseError(f"This file has more than {lim.max_rows:,} rows.")
            cells = [_cell(v) for v in values[: lim.max_columns + 1]]
            if len(cells) > lim.max_columns and any(cells[lim.max_columns :]):
                raise ParseError(f"This file has more than {lim.max_columns} columns.")
            if any(len(c) > lim.max_cell_chars for c in cells):
                raise ParseError("A cell in this file is too long to read.")
            rows.append(cells)
        filled = sum(1 for r in rows if any(r))
        if filled > sum(1 for r in best[0] if any(r)):
            best = (rows, ws.title)
    wb.close()
    return best


# Header detection


def _is_number(text: str) -> bool:
    t = text.replace(",", "").replace("£", "").replace("$", "").replace("€", "").strip("()% ")
    try:
        float(t)
        return True
    except ValueError:
        return False


def _header_index(rows: list[list[str]]) -> int:
    """The first row that looks like column names: wide enough and all text."""
    widest = max((sum(1 for c in r if c) for r in rows[:30]), default=0)
    for i, row in enumerate(rows[:30]):
        cells = [c for c in row if c]
        if len(cells) >= max(2, int(widest * 0.6)) and not any(_is_number(c) for c in cells):
            return i
    return 0


def _clean_headers(raw: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    out = []
    for i, name in enumerate(raw):
        name = " ".join(name.split()) or f"Column {i + 1}"
        count = seen.get(name.lower(), 0) + 1
        seen[name.lower()] = count
        out.append(name if count == 1 else f"{name} ({count})")
    return out


def to_table(rows: list[list[str]], lim: Limits, source_format: str, sheet: str | None) -> Table:
    while rows and not any(rows[-1]):
        rows.pop()
    if not rows:
        raise ParseError("This file is empty.")
    h = _header_index(rows)
    preamble = [" ".join(c for c in r if c)[:160] for r in rows[:h] if any(r)][:5]
    width = max(len(r) for r in rows[h:])
    # Drop columns that are empty all the way down, including the header.
    used = [i for i in range(width) if any(i < len(r) and r[i] for r in rows[h:])]
    headers = _clean_headers([rows[h][i] if i < len(rows[h]) else "" for i in used])
    body = [[r[i] if i < len(r) else "" for i in used] for r in rows[h + 1 :]]
    body = [r for r in body if any(r)]
    if len(body) > lim.max_rows:
        raise ParseError(f"This file has more than {lim.max_rows:,} rows.")
    if not body:
        raise ParseError("This file has column names but no rows.")
    return Table(headers, body, preamble, sheet, source_format)


def parse_bytes(data: bytes, lim: Limits) -> Table:
    if data.startswith(b"PK\x03\x04"):
        rows, sheet = _read_xlsx(data, lim)
        return to_table(rows, lim, "xlsx", sheet)
    if data.startswith(b"\xd0\xcf\x11\xe0"):
        raise ParseError(
            "This is an old Excel format (.xls). Save it as .xlsx or .csv and re-upload."
        )
    if data.startswith((b"%PDF", b"MZ", b"\x7fELF")):
        raise ParseError("This file type is not supported yet. Upload a CSV or Excel file.")
    return to_table(_read_csv(_decode(data), lim), lim, "csv", None)


# The sandbox: a separate Python process with memory and CPU limits, fed on stdin.


def _limit(lim: Limits) -> None:
    resource.setrlimit(resource.RLIMIT_AS, (lim.memory_bytes, lim.memory_bytes))
    resource.setrlimit(resource.RLIMIT_CPU, (lim.seconds, lim.seconds + 1))


def _child_main() -> None:
    lim = Limits(**json.loads(sys.argv[1]))
    data = sys.stdin.buffer.read()
    try:
        out: dict[str, Any] = {"ok": asdict(parse_bytes(data, lim))}
    except ParseError as exc:
        out = {"error": str(exc)}
    except MemoryError:
        out = {"error": "This file needs more memory to read than we allow."}
    except Exception:  # anything else in a hostile file is reported, never raised in the worker
        out = {"error": "This file could not be read. Upload a CSV or Excel file."}
    sys.stdout.write(json.dumps(out))


def parse_sandboxed(data: bytes) -> Table:
    lim = limits()
    try:
        proc = subprocess.run(  # noqa: S603
            [
                sys.executable,
                "-I",
                "-m",
                "boardroom.modules.intake.parsing",
                json.dumps(asdict(lim)),
            ],
            input=data,
            capture_output=True,
            timeout=lim.seconds + 5,
            preexec_fn=lambda: _limit(lim),  # noqa: PLW1509
            cwd=_PACKAGE_ROOT,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ParseError("This file took too long to read.") from exc
    try:
        out = json.loads(proc.stdout or b"{}")
    except json.JSONDecodeError:
        out = {}
    if "ok" in out:
        return Table(**out["ok"])
    if "error" in out:
        raise ParseError(out["error"])
    if proc.returncode < 0:
        raise ParseError("This file needs more memory or time to read than we allow.")
    raise ParseError("This file could not be read. Upload a CSV or Excel file.")


_PACKAGE_ROOT = str(Path(__file__).resolve().parents[3])

if __name__ == "__main__":
    _child_main()
