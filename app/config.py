from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    anthropic_api_key: str

    # Postgres — optional. Unset (the default for local dev) means "just use
    # a local rocket.db SQLite file", no database to stand up first. Set
    # DB_HOST (e.g. in production on Render, pointed at a free Supabase/Neon
    # instance) and the app switches to Postgres instead — same env var
    # names as this project's other FastAPI deploys, so the same free
    # Postgres can be wired in the same way.
    db_host: str = ""
    db_port: int = 5432
    db_name: str = ""
    db_user: str = "postgres"
    db_pass: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def database_url(self) -> str:
        if not self.db_host:
            return "sqlite+aiosqlite:///./rocket.db"
        # User/password are percent-encoded — a generated Supabase/Neon
        # password routinely contains "@"/"/" etc., which would otherwise
        # break the URL's own delimiters if inserted raw.
        user = quote_plus(self.db_user)
        password = quote_plus(self.db_pass)
        return f"postgresql+asyncpg://{user}:{password}@{self.db_host}:{self.db_port}/{self.db_name}"


settings = Settings()
