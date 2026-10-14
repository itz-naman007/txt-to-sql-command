import re
from dataclasses import dataclass
from threading import Lock
from typing import Any

from langchain_community.utilities import SQLDatabase
from sqlalchemy import text


class UnsafeQueryError(ValueError):
    """Raised when generated SQL is outside the read-only query policy."""


_COMMENT_RE = re.compile(r"(--|#|/\*|\*/)")
_STATEMENT_RE = re.compile(r";")
_LIMIT_RE = re.compile(r"\blimit\s+\d+\b", re.IGNORECASE)
_WRITE_RE = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|create|replace|grant|revoke|call|load)\b",
    re.IGNORECASE,
)


def validate_and_limit_sql(query: str, max_rows: int) -> str:
    """Allow one read-only statement and cap SELECT results."""
    cleaned = query.strip()
    if not cleaned:
        raise UnsafeQueryError("The generated query was empty.")
    if _COMMENT_RE.search(cleaned) or _STATEMENT_RE.search(cleaned):
        raise UnsafeQueryError("Comments and multiple SQL statements are not allowed.")
    first_word = cleaned.split(None, 1)[0].lower()
    if first_word not in {"select", "show", "describe"}:
        raise UnsafeQueryError("Only SELECT, SHOW, and DESCRIBE queries are allowed.")
    if _WRITE_RE.search(cleaned):
        raise UnsafeQueryError("Write and schema-changing SQL is not allowed.")
    if first_word == "select":
        limit_match = _LIMIT_RE.search(cleaned)
        if limit_match is None:
            cleaned = f"{cleaned}\nLIMIT {max_rows}"
        elif int(limit_match.group(0).split()[1]) > max_rows:
            cleaned = (
                cleaned[: limit_match.start()]
                + f"LIMIT {max_rows}"
                + cleaned[limit_match.end() :]
            )
    return cleaned


@dataclass
class QueryRecord:
    sql: str = ""
    result: str = ""


class ReadOnlyDatabase:
    """MySQL-backed database adapter with validation and bounded execution."""

    def __init__(self, database: SQLDatabase, max_rows: int, timeout_seconds: int):
        self.database = database
        self.max_rows = max_rows
        self.timeout_seconds = timeout_seconds
        self._last_query = QueryRecord()
        self._query_lock = Lock()

    @property
    def last_query(self) -> QueryRecord:
        with self._query_lock:
            return QueryRecord(self._last_query.sql, self._last_query.result)

    def execute(self, query: str) -> str:
        safe_query = validate_and_limit_sql(query, self.max_rows)
        with self._query_lock:
            self._last_query = QueryRecord(sql=safe_query)
        engine = self.database._engine
        with engine.begin() as connection:
            if engine.dialect.name == "mysql":
                connection.execute(
                    text("SET SESSION MAX_EXECUTION_TIME = :timeout_ms"),
                    {"timeout_ms": self.timeout_seconds * 1000},
                )
            result = connection.execute(text(safe_query))
            rows = result.fetchmany(self.max_rows)
            columns = list(result.keys())
        if not rows:
            rendered = "No rows returned."
        else:
            rendered = _render_rows(columns, rows)
        with self._query_lock:
            self._last_query.result = rendered
        return rendered


def _render_rows(columns: list[str], rows: list[Any]) -> str:
    header = " | ".join(columns)
    separator = " | ".join("---" for _ in columns)
    values = [" | ".join(str(value) for value in row) for row in rows]
    return "\n".join([header, separator, *values])
