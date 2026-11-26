"""Entrypoint for the docs service

This script exists because we need to specify the mkdocs site URL at runtime, but since mkdocs is a static
generator, doesn't support that. Instead, we bake a placeholder into the static build and substitute it at runtime.
"""

import functools
import http.server
import logging
import os
import urllib.parse
from http import HTTPStatus
from pathlib import Path

logger = logging.getLogger(__name__)


class DocsRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Static file handler that redirects directory requests with a relative URL.

    The reverse proxy strips the path prefix of the docs site (e.g. `/docs`) before
    forwarding requests. The base class redirects a directory request lacking a
    trailing slash to an absolute path built from the stripped request path, which
    lies outside of the docs site. A redirect to the last path segment followed by a
    slash is resolved by the browser against the original URL, prefix included.
    """

    def send_head(self):
        parts = urllib.parse.urlsplit(self.path)
        if parts.path.endswith("/") or not os.path.isdir(
            self.translate_path(self.path)
        ):
            return super().send_head()
        self.send_response(HTTPStatus.MOVED_PERMANENTLY)
        self.send_header(
            "Location",
            urllib.parse.urlunsplit(
                ("", "", f"{parts.path.rsplit('/', 1)[-1]}/", parts.query, "")
            ),
        )
        self.send_header("Content-Length", "0")
        self.end_headers()
        return None


def main(
    substitution_placeholder: str,
    site_url: str,
) -> None:
    docs_site = Path(__file__).parents[2] / "docs-site"
    logger.debug(f"{substitution_placeholder=}")
    logger.debug(f"{site_url=}")
    logger.debug(f"{docs_site=}")
    if not docs_site.is_dir():
        raise RuntimeError(f"Docs site directory {docs_site} does not exist")
    substitute_site_url(
        placeholder=substitution_placeholder,
        site_url=site_url,
        docs_site=docs_site,
    )
    handler = functools.partial(DocsRequestHandler, directory=str(docs_site))
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
        logger.debug(f"re-wrote path {str(path)!r}")


if __name__ == "__main__":
    is_debug = os.getenv("DOCS_DEBUG", "false").lower() == "true"
    logging.basicConfig(level=logging.DEBUG if is_debug else logging.WARNING)
    main(
        substitution_placeholder="https://__SITE_URL_PLACEHOLDER__",
        site_url=os.environ.get("MKDOCS_SITE_URL", "http://localhost/"),
    )
