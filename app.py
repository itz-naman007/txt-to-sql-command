import os
from functools import lru_cache
from urllib.parse import quote_plus

import gradio as gr
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langgraph.prebuilt import create_react_agent

try:
    from langchain import hub
except ImportError:  # LangChain 1.x moved the hub package out of the core package.
    hub = None


APP_TITLE = "Text-to-SQL Chatbot"
MODEL_NAME = "gemini-3.6-flash"
TOP_K_RESULTS = 5

load_dotenv()


def _required_setting(name: str) -> str:
    """Return a required environment setting or raise a useful configuration error."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing {name}. Add it to your .env file.")
    return value


def _build_database() -> SQLDatabase:
    """Create the MySQL database connection from environment settings."""
    host = os.getenv("MYSQL_HOST", "localhost")
    port = os.getenv("MYSQL_PORT", "3306")
    username = _required_setting("MYSQL_USER")
    password = _required_setting("MYSQL_PASSWORD")
    database = _required_setting("MYSQL_DATABASE")
    mysql_uri = (
        f"mysql+pymysql://{quote_plus(username)}:{quote_plus(password)}"
        f"@{host}:{port}/{database}"
    )
    return SQLDatabase.from_uri(mysql_uri)


def _build_system_message(database: SQLDatabase) -> str:
    """Load the SQL-agent prompt, with a local fallback for older LangChain versions."""
    if hub is not None:
        prompt_template = hub.pull("langchain-ai/sql-agent-system-prompt")
        return prompt_template.format(dialect=database.dialect, top_k=TOP_K_RESULTS)

    return (
        "You are a helpful SQL agent. Use the provided tools to inspect the database schema "
        "and answer user questions accurately. Keep your answers concise and cite the relevant "
        f"database dialect ({database.dialect}) when needed."
    )


@lru_cache(maxsize=1)
def get_agent():
    """Build and cache the SQL agent until the application process restarts."""
    os.environ["GOOGLE_API_KEY"] = _required_setting("GOOGLE_API_KEY")
    database = _build_database()
    llm = init_chat_model(MODEL_NAME, model_provider="google_genai")
    toolkit = SQLDatabaseToolkit(db=database, llm=llm)
    system_message = _build_system_message(database)
    agent = create_react_agent(llm, toolkit.get_tools(), prompt=system_message)
    return agent, database


def _format_message(message: object) -> str:
    """Convert a LangChain message content value into text for the UI."""
    content = getattr(message, "content", None)
    if isinstance(content, list):
        return "\n".join(
            item.get("text", str(item)) if isinstance(item, dict) else str(item)
            for item in content
        )
    return str(content) if content else str(message)


def ask_database(question: str) -> tuple[str, str]:
    """Answer a natural-language question using the configured SQL agent."""
    cleaned_question = question.strip() if question else ""
    if not cleaned_question:
        return "Please enter a question.", ""

    try:
        agent, database = get_agent()
        final_message = None
        for event in agent.stream(
            {"messages": [("user", cleaned_question)]},
            stream_mode="values",
        ):
            final_message = event["messages"][-1]

        answer = _format_message(final_message)
        tables = ", ".join(database.get_usable_table_names())
        metadata = f"Database: {database.dialect} | Tables: {tables}"
        return answer, metadata
    except Exception as error:
        return (
            f"Unable to answer the question: {error}",
            "Check your .env and database connection.",
        )


def build_interface() -> gr.Blocks:
    """Create the Gradio interface."""
    with gr.Blocks(title=APP_TITLE) as interface:
        gr.Markdown(
            f"# {APP_TITLE}\n"
            "Ask a question about your database in plain English."
        )
        question = gr.Textbox(
            label="Question",
            placeholder="What this data about?",
            lines=3,
        )
        with gr.Row():
            ask_button = gr.Button("Ask", variant="primary")
            gr.ClearButton([question])
        answer = gr.Markdown(label="Answer")
        connection_info = gr.Markdown()

        ask_button.click(ask_database, inputs=question, outputs=[answer, connection_info])
        question.submit(ask_database, inputs=question, outputs=[answer, connection_info])

    return interface


demo = build_interface()


if __name__ == "__main__":
    demo.launch()