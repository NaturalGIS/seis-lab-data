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
    `/docs` directory of the repository. Translated pages must be named with a `.pt.md`
    suffix (_e.g._ `index.pt.md`).


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
docs. Enable it by setting the `BUILD_PDF` environment variable to any value. It generates the following PDF files:

- Development guide - This produces the `docs/assets/documents/seis-lab-data-development-guide.pdf` file:

    ```shell
    BUILD_PDF=1 uv run mkdocs build`
    ```


## Deployment of docs

The docs are currently live at

<https://naturalgis.github.io/seis-lab-data/>

They are deployed automatically by the `.github/workflows/docs.yaml` GitHub Actions workflow on every
commit to the repository's `main` branch.
