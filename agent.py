import logging
import os
from functools import lru_cache
from typing import Any

from langchain.chat_models import init_chat_model
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import create_react_agent

from config import Settings
from db import ReadOnlyDatabase

logger = logging.getLogger(__name__)
TOP_K_RESULTS = 5


def _system_message(database: SQLDatabase) -> str:
    return (
        "You are a read-only SQL agent. Use the database tools to answer the user's "
        "question. Only generate one SELECT, SHOW, or DESCRIBE statement. Never use "
        "comments, semicolons, or write/schema-changing SQL. Keep answers concise. "
        f"The database dialect is {database.dialect}; prefer at most {TOP_K_RESULTS} "
        "rows unless the user asks for a smaller result."
    )


@lru_cache(maxsize=1)
def get_agent(settings: Settings) -> tuple[Any, ReadOnlyDatabase]:
    os.environ["GOOGLE_API_KEY"] = settings.google_api_key
    database = SQLDatabase.from_uri(
        settings.mysql_uri,
        engine_args={
            "pool_pre_ping": True,
            "connect_args": {"connect_timeout": settings.query_timeout_seconds},
        },
        sample_rows_in_table_info=0,
    )
    readonly_database = ReadOnlyDatabase(
        database, settings.max_rows, settings.query_timeout_seconds
    )
    llm = init_chat_model(settings.model_name, model_provider="google_genai")
    toolkit = SQLDatabaseToolkit(db=database, llm=llm)
    tools = [
        _query_tool(readonly_database) if tool.name == "sql_db_query" else tool
        for tool in toolkit.get_tools()
    ]
    agent = create_react_agent(llm, tools, prompt=_system_message(database))
    return agent, readonly_database


def _query_tool(database: ReadOnlyDatabase) -> StructuredTool:
    return StructuredTool.from_function(
        database.execute,
        name="sql_db_query",
        description=(
            "Execute one validated read-only SQL query. Allowed statements are "
            "SELECT, SHOW, and DESCRIBE."
        ),
    )
