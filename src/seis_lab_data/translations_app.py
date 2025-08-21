from pathlib import Path

import babel
import typer
from babel.messages.catalog import Catalog
from babel.messages.extract import extract_from_dir
from babel.messages.mofile import write_mo
from babel.messages.pofile import (
    read_po,
    write_po,
)

from .config import SeisLabDataCliContext

app = typer.Typer()


@app.callback()
def translations_app_callback(ctx: typer.Context):
    """Manage SeisLabData translations.

    Simplified translation workflow:

    0 - Initialize a translation catalog by running the `init` subcommand - you very likely won't need to do this more than once

    1 - Scan the source code and extract strings that are marked as translatable by running the `extract` subcommand - you will need to do this everytime you add new translatable strings in the code

    2 - Update the translation catalog with any new strings by running the `update` subcommand. This will produce the updated .po files

    3 - Perform the translations by modifying the .po files for the various supported locales

    4 - Compile the translated strings into the .mo files which are used by the system by running the `compile` command
    """


@app.command(name="init")
def init_translations(ctx: typer.Context):
    """Initialize a translation catalog."""
    context: SeisLabDataCliContext = ctx.obj["main"]
    for locale in (babel.Locale.parse(loc) for loc in context.settings.locales):
        catalog_path = (
            context.settings.translations_dir
            / locale.language
            / "LC_MESSAGES/messages.po"
        )
        if not catalog_path.exists():
            catalog_dir = catalog_path.parent
            catalog_dir.mkdir(parents=True, exist_ok=True)
            with catalog_path.open("wb") as catalog_fh:
                catalog = Catalog(locale=locale)
                context.status_console.print(
                    f"Initializing message catalog at {str(catalog_path)!s}..."
                )
                write_po(catalog_fh, catalog)
        else:
            context.status_console.print(
                f"Catalog {catalog_path} already exists, aborting..."
            )
            raise typer.Abort() from None
    context.status_console.print("Done!")


@app.command(name="extract")
def extract_translations(
    ctx: typer.Context,
    output_path: Path = Path(__file__).parents[2] / "messages.pot",
):
    """Scan the source code and extract translatable strings into a pot file."""
    context: SeisLabDataCliContext = ctx.obj
    method_map = [
        ("**.py", "python"),
        ("**.html", "jinja2"),
    ]
    source_path = Path(__file__).parent
    context.status_console.print(
        f"Scanning source code from {source_path} for translatable strings..."
    )
    messages = extract_from_dir(dirname=source_path, method_map=method_map)
    template_catalog = Catalog(project="arpav-cline")
    for message in messages:
        template_catalog.add(
            id=message[2],
            locations=[message[:2]],
            auto_comments=message[3],
            context=message[4],
        )
    context.status_console.print(f"Writing template catalog at {output_path}...")
    with output_path.open("wb") as fh:
        write_po(fh, catalog=template_catalog)
    context.status_console.print("Done!")


@app.command(name="update")
def update_translations(
    ctx: typer.Context,
    template_catalog_path: Path = (Path(__file__).parents[2] / "messages.pot"),
    translations_dir: Path = (Path(__file__).parent / "translations"),
):
    """Update existing translation catalogues."""
    context: SeisLabDataCliContext = ctx.obj
    if template_catalog_path.is_file():
        with template_catalog_path.open("r") as fh:
            template_catalog = read_po(fh)
            for locale_dir in (
                p for p in context.settings.translations_dir.iterdir() if p.is_dir()
            ):
                context.status_console.print(
                    f"Updating translations for locale {locale_dir.name}..."
                )
                po_path = locale_dir / "LC_MESSAGES/messages.po"
                with po_path.open("r") as po_fh:
                    catalog = read_po(po_fh)
                    catalog.update(template_catalog)
                context.status_console.print(
                    f"Writing template catalog at {str(po_path.resolve())!r}..."
                )
                with po_path.open("wb") as po_fh:
                    write_po(po_fh, catalog)
    else:
        context.status_console.print(f"{template_catalog_path} not found")
        raise typer.Abort() from None
    context.status_console.print("Done!")


@app.command(name="compile")
def compile_translations(ctx: typer.Context):
    """Compile translations from their .po file into the usable .mo file."""
    context: SeisLabDataCliContext = ctx.obj
    for locale_dir in (
        p for p in context.settings.translations_dir.iterdir() if p.is_dir()
    ):
        po_path = locale_dir / "LC_MESSAGES/messages.po"
        mo_path = locale_dir / "LC_MESSAGES/messages.mo"
        context.status_console.print(
            f"Compiling messages for locale {locale_dir.name}..."
        )
        with po_path.open("r") as po_fh, mo_path.open("wb") as mo_fh:
            catalog = read_po(po_fh)
            write_mo(mo_fh, catalog)
        context.status_console.print(f"Wrote file {mo_path}...")
    context.status_console.print("Done!")
