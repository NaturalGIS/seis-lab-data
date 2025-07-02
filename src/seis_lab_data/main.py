import functools
import logging
import os
import sys
from pathlib import Path

import redis
from rich.padding import Padding
from rich.panel import Panel
import typer

from . import config
from .processing.main import message_handler

logger = logging.getLogger(__name__)
app = typer.Typer()


@app.callback()
def base_callback(ctx: typer.Context) -> None:
    context = config.get_context()
    config.configure_logging(
        rich_console=context.status_console, debug=context.settings.debug
    )
    ctx.obj = context


@app.command()
def greet(ctx: typer.Context) -> None:
    context: config.SeisLabDataCliContext = ctx.obj
    context.status_console.print("Hello from seis-lab-data")


@app.command()
def run_processing_worker(ctx: typer.Context) -> None:
    """Start a processing worker."""
    context: config.SeisLabDataCliContext = ctx.obj
    panel = Panel(
        "SeisLabData processing worker",
        title="seis-lab-data",
        expand=False,
        padding=(1, 2),
        style="green",
    )
    context.status_console.print(Padding(panel, 1))
    connection = redis.Redis.from_url(
        context.settings.message_broker_dsn.unicode_string(), decode_responses=True
    )
    pubsub = connection.pubsub()
    handler = functools.partial(message_handler, context=context)
    for channel_pattern in context.settings.message_broker_channels:
        pubsub.subscribe(**{channel_pattern: handler})
    while True:
        message = pubsub.get_message()
        if message is not None:
            context.status_console.print(f"Caught unhandled message: {message}")


@app.command()
def run_web_server(ctx: typer.Context):
    """Run the uvicorn server."""
    # NOTE: we explicitly do not use uvicorn's programmatic running abilities here
    # because they do not work correctly when called outside an
    # `if __name__ == __main__` guard and when using its debug features.
    # For more detail check:
    #
    # https://github.com/encode/uvicorn/issues/1045
    #
    # This solution works well both in development (where we want to use reload)
    # and in production, as using os.execvp is actually similar to just running
    # the standard `uvicorn` cli command (which is what uvicorn docs recommend).
    context: config.SeisLabDataCliContext = ctx.obj
    uvicorn_args = [
        "uvicorn",
        "seis_lab_data.webapp.app:create_app",
        f"--port={context.settings.bind_port}",
        f"--host={context.settings.bind_host}",
        "--factory",
        "--access-log",
    ]
    if context.settings.debug:
        uvicorn_args.extend(
            [
                "--reload",
                f"--reload-dir={str(Path(__file__).parent)}",
                "--log-level=debug",
            ]
        )
    else:
        uvicorn_args.extend(
            [
                f"--workers={context.settings.num_web_worker_processes}",
                "--log-level=info",
            ]
        )
    if (log_config_file := context.settings.log_config_file) is not None:
        uvicorn_args.append(f"--log-config={str(log_config_file)}")
    if context.settings.public_url.startswith("https://"):
        uvicorn_args.extend(
            [
                "--forwarded-allow-ips=*",
                "--proxy-headers",
            ]
        )

    serving_str = (
        f"[dim]Serving at:[/dim] [link]http://{context.settings.bind_host}:"
        f"{context.settings.bind_port}[/link]\n\n"
        f"[dim]Public URL:[/dim] [link]{context.settings.public_url}[/link]\n\n"
    )
    panel = Panel(
        (
            f"{serving_str}\n\n"
            f"[dim]Running in [b]"
            f"{'development' if context.settings.debug else 'production'} mode[/b]"
        ),
        title="seis-lab-data",
        expand=False,
        padding=(1, 2),
        style="green",
    )
    context.status_console.print(Padding(panel, 1))
    sys.stdout.flush()
    sys.stderr.flush()
    os.execvp("uvicorn", uvicorn_args)
