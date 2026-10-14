import pytest
from langchain_community.utilities import SQLDatabase

from db import ReadOnlyDatabase, UnsafeQueryError, validate_and_limit_sql


@pytest.mark.parametrize(
    "query",
    ["INSERT INTO users VALUES (1)", "UPDATE users SET name='x'", "DROP TABLE users"],
)
def test_write_queries_are_rejected(query):
    with pytest.raises(UnsafeQueryError):
        validate_and_limit_sql(query, 10)


@pytest.mark.parametrize("query", ["SELECT 1; SELECT 2", "SELECT 1 -- comment"])
def test_multiple_statements_and_comments_are_rejected(query):
    with pytest.raises(UnsafeQueryError):
        validate_and_limit_sql(query, 10)


def test_select_limit_is_added_and_capped():
    assert validate_and_limit_sql("SELECT * FROM users", 10).endswith("LIMIT 10")
    assert validate_and_limit_sql("SELECT * FROM users LIMIT 50", 10).endswith(
        "LIMIT 10"
    )
    assert validate_and_limit_sql("SELECT * FROM users LIMIT 5", 10).endswith(
        "LIMIT 5"
    )


def test_show_and_describe_are_allowed():
    assert validate_and_limit_sql("SHOW TABLES", 10) == "SHOW TABLES"
    assert validate_and_limit_sql("DESCRIBE users", 10) == "DESCRIBE users"


def test_sqlite_read_only_database_renders_rows():
    database = SQLDatabase.from_uri("sqlite://")
    database._engine.connect().exec_driver_sql("CREATE TABLE users (id INTEGER, name TEXT)")
    with database._engine.begin() as connection:
        connection.exec_driver_sql("INSERT INTO users VALUES (1, 'Ada')")
    readonly = ReadOnlyDatabase(database, max_rows=10, timeout_seconds=5)

    result = readonly.execute("SELECT id, name FROM users")

    assert "id | name" in result
    assert "1 | Ada" in result
    assert readonly.last_query.sql.endswith("LIMIT 10")
