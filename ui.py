import logging

import gradio as gr

from agent import get_agent
from config import Settings

logger = logging.getLogger(__name__)
APP_TITLE = "Text-to-SQL Chatbot"


def format_message(message: object) -> str:
    content = getattr(message, "content", None)
    if isinstance(content, list):
        return "\n".join(
            item.get("text", str(item)) if isinstance(item, dict) else str(item)
            for item in content
        )
    return str(content) if content else str(message)


def ask_database(
    question: str, history: list[dict[str, str]] | None, settings: Settings
) -> tuple[str, str, str, list[dict[str, str]]]:
    cleaned = question.strip() if question else ""
    history = history or []
    if not cleaned:
        return "Please enter a question.", "", "", history
    if len(cleaned) > settings.max_question_length:
        return (
            f"Please keep questions under {settings.max_question_length} characters.",
            "",
            "",
            history,
        )
    try:
        agent, database = get_agent(settings)
        final_message = None
        for event in agent.stream(
            {"messages": [("user", cleaned)]},
            stream_mode="values",
            config={"recursion_limit": settings.agent_step_limit},
        ):
            final_message = event["messages"][-1]
        if final_message is None:
            raise RuntimeError("The agent returned no response.")
        answer = format_message(final_message)
        tables = database.database.get_usable_table_names()
        metadata = f"Database: {database.database.dialect} | Tables: {', '.join(tables)}"
        sql = database.last_query.sql or "No SQL query was captured."
        result = database.last_query.result or "No result was captured."
        updated_history = history + [
            {"role": "user", "content": cleaned},
            {"role": "assistant", "content": answer},
        ]
        return answer, sql, f"{metadata}\n\n{result}", updated_history
    except Exception as error:
        logger.exception("Database question failed")
        error_text = str(error).lower()
        if "resource_exhausted" in error_text or "quota" in error_text or "429" in error_text:
            return (
                "Gemini API quota is currently exhausted. Wait for the quota to reset "
                "or configure a Google API key/model with available quota.",
                "",
                "The database connection is available, but the language-model request "
                "was rejected by Google.",
                history,
            )
        return (
            "Unable to answer that question. Check the configuration or try a simpler "
            "read-only question.",
            "",
            "The request could not be completed.",
            history,
        )


def build_interface(settings: Settings) -> gr.Blocks:
    with gr.Blocks(title=APP_TITLE) as interface:
        gr.Markdown(f"# {APP_TITLE}\nAsk a question about your database in plain English.")
        question = gr.Textbox(
            label="Question",
            placeholder="How many orders were placed this month?",
            lines=3,
        )
        history = gr.State([])
        with gr.Row():
            ask_button = gr.Button("Ask", variant="primary")
            clear_button = gr.ClearButton([question])
        answer = gr.Markdown(label="Answer")
        sql = gr.Code(label="Generated SQL", language="sql")
        result = gr.Markdown(label="Result")
        chat = gr.Chatbot(label="Session history")

        outputs = [answer, sql, result, history]
        handler = lambda value, state: ask_database(value, state, settings)
        ask_button.click(
            handler, inputs=[question, history], outputs=outputs, show_progress="full"
        )
        question.submit(
            handler, inputs=[question, history], outputs=outputs, show_progress="full"
        )
        history.change(lambda value: value, inputs=history, outputs=chat)
        clear_button.click(lambda: [], outputs=[history, chat])
    return interface


def launch() -> None:
    settings = Settings.from_env()
    interface = build_interface(settings)
    auth = None
    if settings.auth_username and settings.auth_password:
        auth = (settings.auth_username, settings.auth_password)
    interface.launch(auth=auth)
