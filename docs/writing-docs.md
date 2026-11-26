# Writing documentation

The documentation you are reading is created using [mkdocs-material](https://squidfunk.github.io/mkdocs-material/).


!!! tip "Previewing docs in HTML"
    In order to preview the docs in HTML, run:

    ```shell
    uv run mkdocs serve
    ```

    This will automatically reload the docs whenever they change

1. Install [uv](https://docs.astral.sh/uv/)

2. Clone the seis-lab-data repository

    ```shell
    cd ~/dev  # or wherever you want to store the code

    git clone https://github.com/NaturalGIS/seis-lab-data.git
    cd seis-lab-data
    ```

3. install dependencies

    ```shell
    uv sync --group docs --locked
    ```

4.  Write docs in [Markdown](https://spec.commonmark.org/0.31.2/) format. Docs are stored in the
    `/docs` directory of the repository. Portuguese is the default language of the docs: Portuguese pages
    have no language suffix (_e.g._ `index.md`), while English pages must be named with a `.en.md` suffix
    (_e.g._ `index.en.md`). A page without an English version is shown in its default version in both
    languages.


## Building the docs locally

The docs can be built by running:

```shell
uv run mkdocs build
```

Docs will be built into a set of HTML pages and put in the  `site` directory
at the root of the repository.


### Building PDF documents for specific sections of the docs

This project includes a custom `mkdocs_hooks.py` module with extra instructions for mkdocs. If enabled, it makes the
docs build process also generate a set of additional PDF files being rendered for specific sections of the Portuguese
docs. Enable it by setting the `BUILD_PDFS` environment variable to any value:

```shell
BUILD_PDFS=1 uv run mkdocs build
```

It generates the following PDF files, in the `docs/assets/documents` directory:

- Development guide - `seis-lab-data-development-guide.pdf`
- Administration guide - `seis-lab-data-administration-guide.pdf`
- User guide - `seis-lab-data-user-guide.pdf`

Each PDF is configured by a mkdocs configuration file in the `mkdocs/pdf-configs` directory, and registered in the
`PDF_RESOURCES` of `mkdocs/mkdocs_hooks.py`.


## Deployment of docs

The docs, including the PDF documents, are built into the application's docker image when the image is
built. They are served by the `docs` service of each docker compose stack:

| Environment | URL |
|-------------|-----|
| Production | <https://seis-lab-data.ipma.pt/docs/> |
| Test | <https://seis-lab-data.naturalgis.pt/docs/> |
| Development | <http://docs.localhost:8888> |

In the production and test stacks, the site URL is set at runtime by the `MKDOCS_SITE_URL` environment
variable of the `docs` service. In the development stack, the `docs` service runs `mkdocs serve` on the
repository's `docs` directory, so changes are shown as they are saved.
