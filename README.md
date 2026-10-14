# Text-to-SQL Chatbot

This project provides a Gradio interface for asking read-only questions about a
MySQL database. Gemini generates SQL through a LangGraph agent; the application
validates the generated statement, applies a row limit, executes it, and shows
the SQL and bounded result.

## Architecture

- `config.py` loads and validates environment settings.
- `db.py` provides the database adapter, SQL safety policy, row limit, and result rendering.
- `agent.py` creates the LangGraph agent and replaces the toolkit query tool with the safe adapter.
- `ui.py` provides Gradio authentication, per-session history, and user-facing errors.
- `app.py` is the compatible entry point.

## Setup

Use Python 3.11 or newer, create a virtual environment, and install the pinned
dependencies:

```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set `GOOGLE_API_KEY` and the MySQL values.
`LLM_MODEL` and the limit settings are optional.

```bash
python app.py
```

The app listens on the local Gradio address printed in the terminal.

## Security

The application permits exactly one statement beginning with `SELECT`, `SHOW`,
or `DESCRIBE`. SQL comments, semicolons, and write/schema-changing keywords are
rejected. `SELECT` queries are capped by `MAX_ROWS` (100 by default), and MySQL
sessions use `QUERY_TIMEOUT_SECONDS` (30 by default).

Create a dedicated read-only MySQL account and grant it only the required
database permissions. Do not use an administrative account:

```sql
CREATE USER 'readonly_user'@'%' IDENTIFIED BY 'use-a-strong-password';
GRANT SELECT, SHOW VIEW ON your_database.* TO 'readonly_user'@'%';
FLUSH PRIVILEGES;
```

For any deployment beyond localhost, set both `APP_USERNAME` and
`APP_PASSWORD` to enable Gradio basic authentication. Use HTTPS and a strong,
unique password in production. Never commit `.env`.

## Limits and behavior

- Questions must be non-empty and no longer than `MAX_QUESTION_LENGTH`.
- The agent has an `AGENT_STEP_LIMIT` recursion limit.
- Results are rendered as bounded text tables; empty results are reported explicitly.
- Session history is kept in the Gradio session, not in the process-wide agent cache.
- MySQL is the current production backend. The adapter boundary in `db.py` is
  intended to support SQLite and PostgreSQL in later work.
- The model may still misunderstand ambiguous questions. Verify important results.
- Gemini requests require available API quota. A quota-exhaustion response is
  reported separately from database/configuration errors; configure billing or
  another model/key, or wait for the provider quota to reset.

## Tests and evaluation

Run the deterministic safety and SQLite adapter tests with:

```bash
pytest
```

The current test set covers destructive SQL rejection, comment and multi-statement
rejection, `LIMIT` enforcement, and bounded result rendering. A future evaluation
set should add question-to-expected-SQL/result cases against a controlled fixture;
never run evaluation cases against a production database.
