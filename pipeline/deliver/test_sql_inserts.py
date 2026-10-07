"""Tests for sql_inserts: run with `python -m pytest pipeline/deliver`.

Real-database tests run only when a connection string is set:
    MIGRATION_TEST_PG_DSN     e.g. postgresql://user:pass@localhost:5432/test   (needs psycopg)
    MIGRATION_TEST_MYSQL_DSN  e.g. mysql://user:pass@localhost:3306/test        (needs pymysql)
    MIGRATION_TEST_MSSQL_DSN  ODBC connection string                            (needs pyodbc)
They load hostile values into a scratch table and read them back.
"""
from __future__ import annotations

import io
import os
import random
import re
from datetime import date, datetime
from decimal import Decimal
from urllib.parse import urlparse

import pytest

from sql_inserts import (
    DIALECTS,
    Column,
    RejectedValue,
    Table,
    UnsafeOutput,
    insert_statement,
    render_row,
    render_value,
    verify_statement,
    write_sql,
)

HOSTILE_TEXT = [
    "'); DROP TABLE Candidate; --",
    "' OR '1'='1",
    "\\'; DROP TABLE Candidate; --",       # MySQL backslash-escape trick
    "\\",
    "\\\\'",
    "\\x27",
    "''''",
    "Robert'); DROP TABLE Students;--",
    "*/ DROP TABLE x; /*",
    "-- comment",
    "line1\nline2\r\nline3\rDROP TABLE x;",
    "\x00'; DROP TABLE x; --",             # NUL truncation trick (MySQL/SQL Server)
    "\u2019 \u02bc \uff07 \u055a \u0060 \u00b4",  # look-alike quotes (Windows best-fit → ')
    "\u00bf'",                             # GBK/Big5 multibyte-quote trick
    "\u202e'; DROP TABLE x; --",           # right-to-left override
    "$$; DROP TABLE x; $$",                # Postgres dollar quoting
    "$tag$ x $tag$",
    "]; DROP TABLE x; --",                 # SQL Server bracket break-out
    "`; DROP TABLE x; --",                 # MySQL backtick break-out
    "\"; DROP TABLE x; --",
    "N'abc'",
    "0x41424344",
    "X'41'",
    "convert_from(decode('41', 'hex'), 'UTF8')",
    "CAST(0x4100 AS NVARCHAR(MAX))",
    "GO\nDROP TABLE x\nGO",                # sqlcmd batch separator
    ":r C:\\secret.sql",                   # sqlcmd command
    "\\! rm -rf /",                        # psql meta-command
    "\\copy x to '/tmp/x'",
    "SET standard_conforming_strings = off;",
    "Amara Okafor 😀 Łódź Ñoño 中文 עברית",
    " ",
    "\t",
    "a" * 100_000,
]

TABLE = Table("Candidate", (Column("external_id", "text"), Column("comments", "text")))


def decode_text_literal(lit: str, dialect: str) -> str:
    """Invert the text encoding, the way the database would."""
    if lit in ("''", "N''"):
        return ""
    if dialect == "postgres":
        m = re.fullmatch(r"convert_from\(decode\('([0-9a-f]+)', 'hex'\), 'UTF8'\)", lit)
        return bytes.fromhex(m.group(1)).decode("utf-8")
    if dialect == "mysql":
        m = re.fullmatch(r"CONVERT\(X'([0-9a-f]+)' USING utf8mb4\)", lit)
        return bytes.fromhex(m.group(1)).decode("utf-8")
    m = re.fullmatch(r"CAST\(0x([0-9a-f]+) AS NVARCHAR\(MAX\)\)", lit)
    return bytes.fromhex(m.group(1)).decode("utf-16-le")


def storable(value: str, dialect: str) -> bool:
    return not (dialect == "postgres" and "\x00" in value)


# ---- text values ----

@pytest.mark.parametrize("dialect", DIALECTS)
@pytest.mark.parametrize("payload", HOSTILE_TEXT, ids=lambda p: repr(p[:30]))
def test_hostile_text_is_inert_and_round_trips(dialect, payload):
    if not storable(payload, dialect):
        with pytest.raises(RejectedValue):
            render_value(payload, "text", dialect)
        return
    lit = render_value(payload, "text", dialect)
    assert lit.isascii()
    assert decode_text_literal(lit, dialect) == payload
    # The full statement passes both the grammar check and SQLGlot
    sql = insert_statement(TABLE, [render_row(TABLE, {"external_id": "C-1", "comments": payload}, dialect)], dialect)
    assert sql.count(";") == 1


@pytest.mark.parametrize("dialect", DIALECTS)
def test_random_unicode_fuzz(dialect):
    rng = random.Random(1234)
    alphabet = "'\"`\\;-/*$[]()\n\r\t\x00 aZ09" + "\u2019\u02bc\uff07\u00bf\u202e😀中"
    for _ in range(3000):
        s = "".join(rng.choice(alphabet) for _ in range(rng.randint(1, 40)))
        if not storable(s, dialect):
            continue
        row = render_row(TABLE, {"external_id": s, "comments": s[::-1]}, dialect)
        insert_statement(TABLE, [row], dialect)  # raises UnsafeOutput if anything is off
        first = re.match(r"\((N?''|convert_from\(decode\('[0-9a-f]+', 'hex'\), 'UTF8'\)|CONVERT\(X'[0-9a-f]+' USING utf8mb4\)|CAST\(0x[0-9a-f]+ AS NVARCHAR\(MAX\)\))", row)
        assert decode_text_literal(first.group(1), dialect) == s


@pytest.mark.parametrize("dialect", DIALECTS)
def test_lone_surrogate_rejected(dialect):
    with pytest.raises(RejectedValue):
        render_value("abc\ud800", "text", dialect)


def test_non_string_text_rejected():
    with pytest.raises(RejectedValue):
        render_value(123, "text", "postgres")


# ---- typed values ----

@pytest.mark.parametrize("bad", ["1; DROP TABLE x", "1 OR 1=1", " 1", "1 ", "0x41", "1e3", "١٢٣", "--1", "", True, 2**63, "99999999999999999999"])
def test_bad_integers_rejected(bad):
    with pytest.raises(RejectedValue):
        render_value(bad, "integer", "postgres")


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-inf", "1e309", "1,000", "£100", "1.5; DROP", float("nan"), float("inf"), 1e300, True])
def test_bad_decimals_rejected(bad):
    with pytest.raises(RejectedValue):
        render_value(bad, "decimal", "mysql")


@pytest.mark.parametrize("value,expected", [(6480, "6480"), ("6480", "6480"), ("-12.50", "-12.50"), (Decimal("1E+5"), "100000"), (0.1, "0.1")])
def test_good_decimals(value, expected):
    assert render_value(value, "decimal", "postgres") == expected


@pytest.mark.parametrize("bad", ["2024-01-01'); DROP TABLE x; --", "01/07/2024", "2024-13-01", "tomorrow", 20240101])
def test_bad_dates_rejected(bad):
    with pytest.raises(RejectedValue):
        render_value(bad, "date", "tsql")


def test_dates_rebuilt_from_parsed_value():
    assert render_value("2024-07-01", "date", "postgres") == "'2024-07-01'"
    assert render_value(date(2024, 7, 1), "date", "postgres") == "'2024-07-01'"
    assert render_value(datetime(2021, 3, 14, 9, 22), "datetime", "mysql") == "'2021-03-14 09:22:00'"
    with pytest.raises(RejectedValue):
        render_value("2021-03-14T09:22:00+01:00", "datetime", "mysql")
    with pytest.raises(RejectedValue):
        render_value("2021-03-14 09:22'; DROP TABLE x", "datetime", "mysql")


@pytest.mark.parametrize("bad", ["true; DROP", "maybe", 2, "TRUE OR 1=1"])
def test_bad_booleans_rejected(bad):
    with pytest.raises(RejectedValue):
        render_value(bad, "boolean", "postgres")


def test_booleans_per_dialect():
    assert render_value("yes", "boolean", "postgres") == "TRUE"
    assert render_value(False, "boolean", "mysql") == "FALSE"
    assert render_value(True, "boolean", "tsql") == "1"


# ---- identifiers and row shape ----

@pytest.mark.parametrize("bad", ['name"; DROP TABLE x; --', "a]", "a`b", "a b", "", "1abc", "a;b", "a'b", "a" * 64, "naïve", "a\nb"])
def test_unsafe_identifiers_rejected(bad):
    with pytest.raises(ValueError):
        Column(bad)
    with pytest.raises(ValueError):
        Table(bad, (Column("a"),))


def test_unknown_row_key_is_refused():
    with pytest.raises(UnsafeOutput):
        render_row(TABLE, {"external_id": "C-1", "comments) VALUES (1); DROP TABLE x; --": "x"}, "postgres")


def test_missing_keys_become_null():
    assert render_row(TABLE, {"external_id": "C-1"}, "postgres").endswith(", NULL)")


# ---- verifier catches tampering ----

@pytest.mark.parametrize("dialect", DIALECTS)
def test_verifier_rejects_tampered_statements(dialect):
    good = insert_statement(TABLE, [render_row(TABLE, {"external_id": "a", "comments": "b"}, dialect)], dialect)
    tampered = [
        good.replace(";\n", "; DROP TABLE Candidate;\n"),
        good.replace("VALUES\n", "VALUES\n('x', 'y'),\n"),
        good.replace("VALUES\n(", "SELECT * FROM users; --\n("),
        good.replace("Candidate", "Other"),
        good + "DELETE FROM Candidate;\n",
        good.replace("(", "(\u2019", 1),
    ]
    for sql in tampered:
        with pytest.raises(UnsafeOutput):
            verify_statement(sql, TABLE, dialect)


# ---- whole file ----

@pytest.mark.parametrize("dialect", DIALECTS)
def test_write_sql_batches_rejects_and_transaction(dialect):
    table = Table("Placement", (Column("external_id"), Column("fee", "decimal"), Column("date_begin", "date"), Column("active", "boolean")))
    rows = [{"external_id": f"P-{i}", "fee": str(1000 + i), "date_begin": "2024-07-01", "active": "1"} for i in range(1203)]
    rows[10]["fee"] = "6480; DROP TABLE Placement"
    rows[20]["date_begin"] = "01/07/2024"
    buf = io.StringIO()
    result = write_sql(table, rows, dialect, buf)
    out = buf.getvalue()
    assert result.written == 1201
    assert [r[0] for r in result.rejected] == [11, 21]
    assert "fee:" in result.rejected[0][1]
    assert out.isascii()
    assert out.count("INSERT INTO") == 3  # 500 + 500 + 201
    assert "DROP" not in out
    first, last = out.splitlines()[0], out.splitlines()[-1]
    assert "COMMIT" in last and ("BEGIN" in out.splitlines()[2] or "TRANSACTION" in out.splitlines()[1])


# ---- optional: load into a real database and read back ----

def _rows_for_db():
    vals = [p for p in HOSTILE_TEXT if "\x00" not in p]
    return [{"id": i, "val": v} for i, v in enumerate(vals)], vals


@pytest.mark.skipif(not os.getenv("MIGRATION_TEST_PG_DSN"), reason="set MIGRATION_TEST_PG_DSN to run")
def test_postgres_round_trip():
    import psycopg

    table = Table("sqli_probe", (Column("id", "integer"), Column("val", "text")))
    rows, vals = _rows_for_db()
    buf = io.StringIO()
    write_sql(table, rows, "postgres", buf)
    with psycopg.connect(os.environ["MIGRATION_TEST_PG_DSN"], autocommit=True) as conn:
        conn.execute('DROP TABLE IF EXISTS "sqli_probe"; CREATE TABLE "sqli_probe" ("id" bigint, "val" text)')
        conn.execute(buf.getvalue())
        got = [r[0] for r in conn.execute('SELECT "val" FROM "sqli_probe" ORDER BY "id"')]
        conn.execute('DROP TABLE "sqli_probe"')
    assert got == vals


@pytest.mark.skipif(not os.getenv("MIGRATION_TEST_MYSQL_DSN"), reason="set MIGRATION_TEST_MYSQL_DSN to run")
def test_mysql_round_trip():
    import pymysql

    u = urlparse(os.environ["MIGRATION_TEST_MYSQL_DSN"])
    table = Table("sqli_probe", (Column("id", "integer"), Column("val", "text")))
    rows, vals = _rows_for_db()
    buf = io.StringIO()
    write_sql(table, rows, "mysql", buf)
    conn = pymysql.connect(host=u.hostname, port=u.port or 3306, user=u.username, password=u.password, database=u.path.lstrip("/"), charset="utf8mb4", autocommit=True, client_flag=pymysql.constants.CLIENT.MULTI_STATEMENTS)
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS `sqli_probe`")
        cur.execute("CREATE TABLE `sqli_probe` (`id` BIGINT, `val` LONGTEXT) CHARACTER SET utf8mb4")
        cur.execute(buf.getvalue())
        while cur.nextset():
            pass
        cur.execute("SELECT `val` FROM `sqli_probe` ORDER BY `id`")
        got = [r[0] for r in cur.fetchall()]
        cur.execute("DROP TABLE `sqli_probe`")
    conn.close()
    assert got == vals


@pytest.mark.skipif(not os.getenv("MIGRATION_TEST_MSSQL_DSN"), reason="set MIGRATION_TEST_MSSQL_DSN to run")
def test_sqlserver_round_trip():
    import pyodbc

    table = Table("sqli_probe", (Column("id", "integer"), Column("val", "text")))
    rows, vals = _rows_for_db()
    buf = io.StringIO()
    write_sql(table, rows, "tsql", buf)
    conn = pyodbc.connect(os.environ["MIGRATION_TEST_MSSQL_DSN"], autocommit=True)
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS [sqli_probe]; CREATE TABLE [sqli_probe] ([id] BIGINT, [val] NVARCHAR(MAX))")
    cur.execute(buf.getvalue())
    got = [r[0] for r in cur.execute("SELECT [val] FROM [sqli_probe] ORDER BY [id]").fetchall()]
    cur.execute("DROP TABLE [sqli_probe]")
    conn.close()
    assert got == vals
