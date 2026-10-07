"""Write target rows as SQL INSERT statements that cannot be hijacked by the data.

Source data is untrusted: a candidate's name, a note or an old CRM field can
contain anything. The rules below make injection impossible by construction,
then check every statement before it is written.

1. No character from the data is ever written as SQL text.
   - Text values are hex-encoded. The only data-derived characters in the
     file are 0-9 and a-f, which cannot close a quote or start a statement,
     whatever the server's settings (backslash escapes, character set,
     standard_conforming_strings, code page).
   - Numbers, booleans, dates and datetimes are parsed into Python values
     first and re-rendered from those values, never copied from the input.
   - A value that doesn't parse as its column's type rejects the row; it is
     never written.
2. Table and column names come from the target spec, never from the data,
   and must match a strict pattern. Rows with unexpected keys are refused.
3. The file is pure ASCII, so no client can re-decode it into something
   else (e.g. Windows "best fit" turning U+02BC into a quote).
4. Every statement is checked twice before writing: against the exact
   grammar this module emits, and by SQLGlot, which must see exactly one
   INSERT into the expected table. Any mismatch raises UnsafeOutput.
5. The whole file runs in one transaction, so a failed load leaves nothing
   half-written.

Usage:
    table = Table("Candidate", (Column("external_id", "text"), Column("fee", "decimal")))
    with open("Candidate.sql", "w", encoding="ascii", newline="\\n") as f:
        result = write_sql(table, rows, "postgres", f)
    result.rejected  # [(row_number, reason), ...] → goes to the rejects file
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Literal, Mapping, TextIO

Dialect = Literal["postgres", "mysql", "tsql"]
ColumnType = Literal["text", "integer", "decimal", "boolean", "date", "datetime"]

DIALECTS: tuple[Dialect, ...] = ("postgres", "mysql", "tsql")
COLUMN_TYPES: tuple[ColumnType, ...] = ("text", "integer", "decimal", "boolean", "date", "datetime")

# Letters, digits, underscore and dot (target schemas use names like "address.city").
# No quotes, brackets, backticks, spaces or control characters can get through.
# 63 is Postgres's limit; longer names would be silently truncated there.
IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_.]{0,62}")
INT_RE = re.compile(r"-?[0-9]{1,19}")
DECIMAL_RE = re.compile(r"-?[0-9]{1,38}(\.[0-9]{1,38})?")
MAX_TEXT_BYTES = 10 * 1024 * 1024  # 10 MB per value; bigger values are rejected
MAX_BATCH = 500  # SQL Server allows at most 1000 rows per VALUES list

TRUE_WORDS = {"true", "t", "yes", "y", "1"}
FALSE_WORDS = {"false", "f", "no", "n", "0"}

HEADER = {
    "postgres": "SET client_encoding = 'UTF8';\nSET standard_conforming_strings = on;\nBEGIN;\n",
    "mysql": "SET NAMES utf8mb4;\nSTART TRANSACTION;\n",
    "tsql": "SET XACT_ABORT ON;\nBEGIN TRANSACTION;\n",
}
FOOTER = {"postgres": "COMMIT;\n", "mysql": "COMMIT;\n", "tsql": "COMMIT TRANSACTION;\n"}
SQLGLOT_DIALECT = {"postgres": "postgres", "mysql": "mysql", "tsql": "tsql"}


class UnsafeOutput(Exception):
    """The writer produced something outside its own grammar. Never written."""


class RejectedValue(ValueError):
    """A value doesn't fit its column type. The row goes to the rejects file."""


@dataclass(frozen=True)
class Column:
    name: str
    type: ColumnType = "text"

    def __post_init__(self) -> None:
        check_identifier(self.name)
        if self.type not in COLUMN_TYPES:
            raise ValueError(f"Unknown column type {self.type!r}")


@dataclass(frozen=True)
class Table:
    name: str
    columns: tuple[Column, ...]
    schema: str | None = None

    def __post_init__(self) -> None:
        check_identifier(self.name)
        if self.schema is not None:
            check_identifier(self.schema)
        if not self.columns:
            raise ValueError("A table needs at least one column")
        names = [c.name for c in self.columns]
        if len(set(names)) != len(names):
            raise ValueError(f"Duplicate column names in {self.name}")


@dataclass
class WriteResult:
    written: int = 0
    rejected: list[tuple[int, str]] = field(default_factory=list)


# ---- identifiers ----

def check_identifier(name: str) -> str:
    if not isinstance(name, str) or not IDENT_RE.fullmatch(name):
        raise ValueError(f"Unsafe identifier {name!r}: use letters, digits, _ and . only (max 63)")
    return name


def quote_identifier(name: str, dialect: Dialect) -> str:
    check_identifier(name)  # the pattern allows no quote characters, so no escaping is needed
    if dialect == "postgres":
        return f'"{name}"'
    if dialect == "mysql":
        return f"`{name}`"
    if dialect == "tsql":
        return f"[{name}]"
    raise ValueError(f"Unknown dialect {dialect!r}")


def table_ref(table: Table, dialect: Dialect) -> str:
    ref = quote_identifier(table.name, dialect)
    return f"{quote_identifier(table.schema, dialect)}.{ref}" if table.schema else ref


# ---- values ----

def render_value(value: Any, col_type: ColumnType, dialect: Dialect) -> str:
    """Render one value as a SQL literal, or raise RejectedValue."""
    if value is None:
        return "NULL"
    if col_type == "text":
        return _text(value, dialect)
    if col_type == "integer":
        return _integer(value)
    if col_type == "decimal":
        return _decimal(value)
    if col_type == "boolean":
        return _boolean(value, dialect)
    if col_type == "date":
        return _date(value)
    if col_type == "datetime":
        return _datetime(value)
    raise ValueError(f"Unknown column type {col_type!r}")


def _text(value: Any, dialect: Dialect) -> str:
    if not isinstance(value, str):
        raise RejectedValue(f"expected text, got {type(value).__name__}")
    if value == "":
        return "N''" if dialect == "tsql" else "''"
    if dialect == "postgres" and "\x00" in value:
        raise RejectedValue("text contains a NUL character, which Postgres cannot store")
    try:
        utf8 = value.encode("utf-8")  # fails on lone surrogates from bad decoding
    except UnicodeEncodeError:
        raise RejectedValue("text is not valid Unicode") from None
    if len(utf8) > MAX_TEXT_BYTES:
        raise RejectedValue("text is larger than 10 MB")
    if dialect == "postgres":
        return f"convert_from(decode('{utf8.hex()}', 'hex'), 'UTF8')"
    if dialect == "mysql":
        return f"CONVERT(X'{utf8.hex()}' USING utf8mb4)"
    # NVARCHAR is UTF-16LE; supplementary characters become surrogate pairs, as SQL Server expects
    return f"CAST(0x{value.encode('utf-16-le').hex()} AS NVARCHAR(MAX))"


def _integer(value: Any) -> str:
    if isinstance(value, bool):
        raise RejectedValue("expected an integer, got a boolean")
    if isinstance(value, int):
        n = value
    elif isinstance(value, str) and INT_RE.fullmatch(value):
        n = int(value)
    else:
        raise RejectedValue(f"not an integer: {_preview(value)}")
    if not -(2**63) <= n < 2**63:
        raise RejectedValue("integer out of 64-bit range")
    return str(n)


def _decimal(value: Any) -> str:
    if isinstance(value, bool):
        raise RejectedValue("expected a number, got a boolean")
    if isinstance(value, (int, Decimal)):
        d = Decimal(value)
    elif isinstance(value, float):
        d = Decimal(repr(value))
    elif isinstance(value, str) and DECIMAL_RE.fullmatch(value):
        d = Decimal(value)
    else:
        raise RejectedValue(f"not a number: {_preview(value)}")
    try:
        if not d.is_finite():
            raise RejectedValue("number is NaN or infinite")
        text = format(d, "f")
    except InvalidOperation:
        raise RejectedValue(f"not a number: {_preview(value)}") from None
    if not DECIMAL_RE.fullmatch(text):
        raise RejectedValue("number has too many digits")
    return text


def _boolean(value: Any, dialect: Dialect) -> str:
    if isinstance(value, bool):
        b = value
    elif isinstance(value, int) and value in (0, 1):
        b = bool(value)
    elif isinstance(value, str) and value.strip().lower() in TRUE_WORDS | FALSE_WORDS:
        b = value.strip().lower() in TRUE_WORDS
    else:
        raise RejectedValue(f"not a yes/no value: {_preview(value)}")
    if dialect == "tsql":
        return "1" if b else "0"
    return "TRUE" if b else "FALSE"


def _date(value: Any) -> str:
    if isinstance(value, datetime):
        raise RejectedValue("expected a date, got a date and time")
    if isinstance(value, date):
        d = value
    elif isinstance(value, str):
        try:
            d = date.fromisoformat(value)
        except ValueError:
            raise RejectedValue(f"not a YYYY-MM-DD date: {_preview(value)}") from None
    else:
        raise RejectedValue(f"not a date: {_preview(value)}")
    return f"'{d.isoformat()}'"  # rebuilt from the parsed date: digits and dashes only


def _datetime(value: Any) -> str:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value)
        except ValueError:
            raise RejectedValue(f"not an ISO date and time: {_preview(value)}") from None
    else:
        raise RejectedValue(f"not a date and time: {_preview(value)}")
    if dt.tzinfo is not None:
        raise RejectedValue("date and time has a timezone; convert to UTC and drop it first")
    return f"'{dt.isoformat(sep=' ', timespec='seconds' if not dt.microsecond else 'microseconds')}'"


def _preview(value: Any) -> str:
    """Short, printable description of a bad value for the rejects file."""
    s = repr(value)
    return s if len(s) <= 40 else s[:37] + "..."


# ---- statements ----

def render_row(table: Table, row: Mapping[str, Any], dialect: Dialect) -> str:
    """Render one row as '(v1, v2, ...)'. Raises RejectedValue for bad data."""
    expected = {c.name for c in table.columns}
    extra = set(row) - expected
    if extra:
        # Column names never come from data; an unexpected key is a bug upstream
        raise UnsafeOutput(f"Row has columns not in the {table.name} spec: {sorted(map(repr, extra))[:5]}")
    parts = []
    for c in table.columns:
        try:
            parts.append(render_value(row.get(c.name), c.type, dialect))
        except RejectedValue as e:
            raise RejectedValue(f"{c.name}: {e}") from None
    return "(" + ", ".join(parts) + ")"


def insert_statement(table: Table, rendered_rows: list[str], dialect: Dialect) -> str:
    cols = ", ".join(quote_identifier(c.name, dialect) for c in table.columns)
    sql = f"INSERT INTO {table_ref(table, dialect)} ({cols}) VALUES\n" + ",\n".join(rendered_rows) + ";\n"
    verify_statement(sql, table, dialect)
    return sql


def write_sql(table: Table, rows: Iterable[Mapping[str, Any]], dialect: Dialect, out: TextIO, batch_size: int = MAX_BATCH) -> WriteResult:
    """Write all rows as verified INSERT statements inside one transaction."""
    if dialect not in DIALECTS:
        raise ValueError(f"Unknown dialect {dialect!r}")
    if not 1 <= batch_size <= MAX_BATCH:
        raise ValueError(f"batch_size must be 1–{MAX_BATCH}")
    result = WriteResult()
    batch: list[str] = []
    out.write(HEADER[dialect])
    for i, row in enumerate(rows, start=1):
        try:
            batch.append(render_row(table, row, dialect))
        except RejectedValue as e:
            result.rejected.append((i, str(e)))
            continue
        if len(batch) == batch_size:
            out.write(insert_statement(table, batch, dialect))
            result.written += len(batch)
            batch = []
    if batch:
        out.write(insert_statement(table, batch, dialect))
        result.written += len(batch)
    out.write(FOOTER[dialect])
    return result


# ---- verification ----

_DATE = r"'[0-9]{4}-[0-9]{2}-[0-9]{2}'"
_DATETIME = r"'[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{6})?'"
_NUMBER = r"-?[0-9]{1,38}(\.[0-9]{1,38})?"
_TEXT = {
    "postgres": r"''|convert_from\(decode\('(?:[0-9a-f]{2})+', 'hex'\), 'UTF8'\)",
    "mysql": r"''|CONVERT\(X'(?:[0-9a-f]{2})+' USING utf8mb4\)",
    "tsql": r"N''|CAST\(0x(?:[0-9a-f]{4})+ AS NVARCHAR\(MAX\)\)",
}
_BOOL = {"postgres": "TRUE|FALSE", "mysql": "TRUE|FALSE", "tsql": "1|0"}
_IDENT = {"postgres": r'"[A-Za-z0-9_.]+"', "mysql": r"`[A-Za-z0-9_.]+`", "tsql": r"\[[A-Za-z0-9_.]+\]"}


def _statement_re(dialect: Dialect) -> re.Pattern[str]:
    lit = f"(?:NULL|{_TEXT[dialect]}|{_DATETIME}|{_DATE}|{_NUMBER}|{_BOOL[dialect]})"
    tup = rf"\({lit}(?:, {lit})*\)"
    ident = _IDENT[dialect]
    return re.compile(rf"INSERT INTO {ident}(?:\.{ident})? \({ident}(?:, {ident})*\) VALUES\n{tup}(?:,\n{tup})*;\n")


_STATEMENT_RE = {d: _statement_re(d) for d in DIALECTS}


def verify_statement(sql: str, table: Table, dialect: Dialect) -> None:
    """Raise UnsafeOutput unless sql is exactly one INSERT this module could have produced."""
    if not sql.isascii():
        raise UnsafeOutput("Statement contains non-ASCII characters")
    if not _STATEMENT_RE[dialect].fullmatch(sql):
        raise UnsafeOutput("Statement doesn't match the safe INSERT grammar")

    # Second, independent check: a real SQL parser must agree.
    import sqlglot
    from sqlglot import exp

    try:
        parsed = [p for p in sqlglot.parse(sql, read=SQLGLOT_DIALECT[dialect]) if p is not None]
    except sqlglot.errors.ParseError as e:
        raise UnsafeOutput(f"Statement doesn't parse: {e}") from None
    if len(parsed) != 1 or not isinstance(parsed[0], exp.Insert):
        raise UnsafeOutput(f"Expected one INSERT, parsed {[type(p).__name__ for p in parsed]}")
    target = parsed[0].find(exp.Table)
    if target is None or target.name != table.name:
        raise UnsafeOutput("INSERT targets the wrong table")
    for node in parsed[0].walk():
        if isinstance(node, (exp.Select, exp.Subquery, exp.Command, exp.Drop, exp.Delete, exp.Update, exp.Semicolon)):
            raise UnsafeOutput(f"Unexpected {type(node).__name__} inside INSERT")
