# Text-to-SQL Chatbot

This project lets a user ask questions about a MySQL database in plain English. A
Gemini model generates and runs the SQL through a LangGraph agent, and the result
is shown in a small Gradio web interface.

## Architecture

1. Gradio collects a question from the user.
2. `app.py` creates a cached LangGraph ReAct agent.
3. LangChain's SQL toolkit inspects the schema and executes read queries.
4. The Gemini model turns the question and database context into an answer.
5. The answer and database metadata are returned to the interface.

The database connection is configured through environment variables, so database
credentials are not stored in the source code.

## Running locally

Install the dependencies and create a `.env` file containing:

```text
GOOGLE_API_KEY=your_google_api_key
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=your_mysql_user
MYSQL_PASSWORD=your_mysql_password
MYSQL_DATABASE=your_database
```

Then start the app:

```bash
pip install -r requirements.txt
python app.py
```

Open the local Gradio URL printed in the terminal.

## Pros

- Natural-language access to existing MySQL data.
- The database agent and connection are cached instead of rebuilt for every question.
- Configuration is kept outside the application code.
- The interface is simple to run and use.

## Cons

- Answers depend on the Gemini model and may need user verification.
- A live MySQL database and Google API key are required.
- There is currently no authentication, query history, or role-based access.
- Large or complex schemas can make generated queries slower or less reliable.

## Future work

- Add authentication, permissions, and query safety limits.
- Show the generated SQL and provide clearer error messages.
- Add tests with a local database fixture and measure query accuracy.
- Support additional database engines and configurable language models.
