import os
from dataclasses import dataclass
from urllib.parse import quote_plus

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    google_api_key: str
    mysql_host: str
    mysql_port: int
    mysql_user: str
    mysql_password: str
    mysql_database: str
    model_name: str = "gemini-3.6-flash"
    max_question_length: int = 1000
    max_rows: int = 100
    query_timeout_seconds: int = 30
    agent_step_limit: int = 12
    auth_username: str | None = None
    auth_password: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        return cls(
            google_api_key=_required("GOOGLE_API_KEY"),
            mysql_host=os.getenv("MYSQL_HOST", "localhost"),
            mysql_port=_int_setting("MYSQL_PORT", 3306, minimum=1, maximum=65535),
            mysql_user=_required("MYSQL_USER"),
            mysql_password=_required("MYSQL_PASSWORD"),
            mysql_database=_required("MYSQL_DATABASE"),
            model_name=os.getenv("LLM_MODEL", cls.model_name),
            max_question_length=_int_setting("MAX_QUESTION_LENGTH", 1000, minimum=1),
            max_rows=_int_setting("MAX_ROWS", 100, minimum=1),
            query_timeout_seconds=_int_setting("QUERY_TIMEOUT_SECONDS", 30, minimum=1),
            agent_step_limit=_int_setting("AGENT_STEP_LIMIT", 12, minimum=1),
            auth_username=os.getenv("APP_USERNAME") or None,
            auth_password=os.getenv("APP_PASSWORD") or None,
        )

    @property
    def mysql_uri(self) -> str:
        return (
            f"mysql+pymysql://{quote_plus(self.mysql_user)}:"
            f"{quote_plus(self.mysql_password)}@{self.mysql_host}:"
            f"{self.mysql_port}/{self.mysql_database}"
        )


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required setting: {name}")
    return value


def _int_setting(name: str, default: int, minimum: int, maximum: int | None = None) -> int:
    raw_value = os.getenv(name, str(default))
    try:
        value = int(raw_value)
    except ValueError as error:
        raise RuntimeError(f"{name} must be an integer") from error
    if value < minimum or (maximum is not None and value > maximum):
        raise RuntimeError(f"{name} must be between {minimum} and {maximum}")
    return value
