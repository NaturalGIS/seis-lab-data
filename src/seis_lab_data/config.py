import logging
from pathlib import Path
from typing import Optional

import jinja2
from pydantic import (
    BaseModel,
    ConfigDict,
)
from pydantic.networks import (
    PostgresDsn,
    RedisDsn,
)
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)
from rich.console import Console
from rich.logging import RichHandler


class SeisLabDataSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SEIS_LAB_DATA__",
        env_nested_delimiter="__",
        secrets_dir="/run/secrets",
    )

    auth_application_slug: str = "seis-lab-data-app"
    auth_client_id: str = "someid"
    auth_client_secret: str = "somesecret"
    csrf_secret: str = "somesecret"
    session_secret_key: str = "somesecretkey"
    auth_external_base_url: str = "http://localhost:9000"
    auth_internal_base_url: str = "http://localhost:9000"
    bind_host: str = "127.0.0.1"
    bind_port: int = 5001
    database_dsn: PostgresDsn = PostgresDsn(
        "postgresql+psycopg://sld:sldpass@localhost/seis_lab_data"
    )
    test_database_dsn: PostgresDsn = PostgresDsn(
        "postgresql+psycopg://sld:sldpass@localhost/seis_lab_data_test"
    )
    debug: bool = False
    log_config_file: Path | None = None
    num_web_worker_processes: int = 8
    public_url: str = "http://localhost:5001"
    static_dir: Optional[Path] = Path(__file__).parent / "webapp/static"
    templates_dir: Optional[Path] = Path(__file__).parent / "webapp/templates"
    message_broker_dsn: Optional[RedisDsn] = RedisDsn("redis://localhost:6379")
    message_broker_channels: list[str] = ["demo-channel"]
    locales: list[str] = ["pt", "en"]
    translations_dir: Optional[Path] = Path(__file__).parent / "translations"
    emit_events: bool = False


class SeisLabDataCliContext(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    jinja_environment: jinja2.Environment = jinja2.Environment()
    status_console: Console
    settings: SeisLabDataSettings


def get_settings() -> SeisLabDataSettings:
    return SeisLabDataSettings()


def get_cli_context() -> SeisLabDataCliContext:
    settings = get_settings()
    return SeisLabDataCliContext(
        jinja_environment=_get_jinja_environment(settings),
        settings=settings,
        status_console=Console(stderr=True),
    )


def configure_logging(rich_console: Console, debug: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.WARNING,
        handlers=[RichHandler(console=rich_console, rich_tracebacks=True)],
    )


def _get_jinja_environment(settings: SeisLabDataSettings) -> jinja2.Environment:
    env = jinja2.Environment()
    return env
