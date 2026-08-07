"""Entrypoint for the docs service

This script exists because we need to specify the mkdocs site URL at runtime, but since mkdocs is a static
generator, doesn't support that. Instead, we bake a placeholder into the static build and substitute it at runtime.
"""

import functools
import http.server
import os
from pathlib import Path


def main() -> None:
    docs_site = Path(__file__).parents[2] / "docs-site"
    if not docs_site.is_dir():
        raise RuntimeError(f"Docs site directory {docs_site} does not exist")
    substitute_site_url(
        placeholder="https://__SITE_URL_PLACEHOLDER__",
        site_url=os.environ.get("MKDOCS_SITE_URL", "http://localhost/"),
        docs_site=docs_site,
    )
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(docs_site)
    )
    with http.server.ThreadingHTTPServer(("0.0.0.0", 8000), handler) as httpd:
        httpd.serve_forever()


def substitute_site_url(*, placeholder: str, site_url: str, docs_site: Path) -> None:
    # Extensions worth scanning for the placeholder. mkdocs' output is
    # HTML/CSS/JS/XML/JSON text; anything else (images, fonts) can't contain it
    # and isn't worth the read.
    TEXT_SUFFIXES = {".html", ".htm", ".xml", ".js", ".css", ".json", ".txt"}
    for path in docs_site.rglob("*"):
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if placeholder not in content:
            continue
        path.write_text(content.replace(placeholder, site_url), encoding="utf-8")


if __name__ == "__main__":
    main()
