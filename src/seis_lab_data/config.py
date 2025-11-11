import logging
import logging.config
import warnings
from pathlib import Path
from typing import Optional

import jinja2
import yaml
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

warnings.filterwarnings(
    "ignore", r".*directory.*does not exist.*", UserWarning, module="pydantic_settings"
)


class SeisLabDataSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SEIS_LAB_DATA__",
        env_nested_delimiter="__",
        secrets_dir="/run/secrets",
    )

    auth_application_slug: str = "seis-lab-data-app"
    auth_client_id: str = "someid"
    auth_client_secret: str = "somesecret"
    auth_admin_token: str = "sometoken"
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
    pagination_page_size: int = 20
    webmap_base_tile_layer_url: str = (
        "https://localhost:8888/tiles/world-bathymetry/{z}/{x}/{y}.png"
    )
    webmap_default_center_lon: float = 0.0
    webmap_default_center_lat: float = 0.0
    webmap_default_zoom_level: int = 3
    webmap_default_polygon_fill_color: str = "#c27d0e"
    webmap_default_polygon_fill_opacity: float = 0.3
    webmap_default_polygon_outline_color: str = "#c27d0e"
    webmap_default_polygon_outline_opacity: float = 1.0
    webmap_default_polygon_outline_width: int = 4
    # the below WKT Polygon corresponds to the bbox of Portugal's Exclusive Economic Zone, as gotten
    # by postprocessing the dataset of the world EEZs, available
    # for download at https://www.marineregions.org/downloads.php#eez
    webmap_default_bbox_wkt: str = (
        "Polygon (("
        "-35.58558 29.24784, "
        "-7.25694 29.24784, "
        "-7.25694 43.06482, "
        "-35.58558 43.06482, "
        "-35.58558 29.24784"
        "))"
    )
    default_temporal_extent_begin: str = ""
    default_temporal_extent_end: str = ""


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


def configure_logging(
    cli_context: SeisLabDataCliContext,
) -> None:
    if cli_context.settings.log_config_file:
        logging_dict_conf = (
            yaml.safe_load(cli_context.settings.log_config_file.read_text())
            if cli_context.settings.log_config_file
            else {}
        )
        logging.config.dictConfig(logging_dict_conf)
    else:
        logging.basicConfig(
            level=logging.DEBUG if cli_context.settings.debug else logging.WARNING,
            handlers=[
                RichHandler(console=cli_context.status_console, rich_tracebacks=True)
            ],
        )


def _get_jinja_environment(settings: SeisLabDataSettings) -> jinja2.Environment:
    env = jinja2.Environment()
    return env
