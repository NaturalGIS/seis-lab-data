# seis-lab-data

Marine data catalog for internal usage at [IPMA]


## Development

- Clone this repo
- Make a symlink to the directory where you have your sample data into a `sample-data` directory under the root of the
  project - For example:

   ```shell
   # assuming your sample-data directory lives at `~/my-seis-lab-data-sample-data`
   ln -s ~/my-seis-lab-data-sample-data sample-data
   ```

- Ensure you have installed [docker] and [uv] on your machine
- Create a Python virtualenv and install the project dependencies into it with:

    ```shell
    cd seis-lab-data
    uv sync --group dev --locked
    ```

- Install the included [pre-commit] hooks:

    ```shell
    uv run pre-commit install
    ```

- Setup your favorite IDE for working on the project
- Launch the services with docker compose:

    ```shell
    docker compose -f docker/compose.dev.yaml up -d
    ```

- Ensure the database is up to date by running:

    ```shell
    docker compose -f docker/compose.dev.yaml exec -ti webapp uv run seis-lab-data db upgrade
    ```

- Add default data:

    ```shell
    docker compose -f docker/compose.dev.yaml exec -ti webapp uv run seis-lab-data bootstrap all
    ```

- Optionally, load sample records into the DB:

    ```shell
    docker compose -f docker/compose.dev.yaml exec -ti webapp uv run seis-lab-data dev load-all-samples
    ```

- You should now be able to access the webapp at

    http://localhost:8888

- Additional relevant URLs:

  - http://localhost:8887 - the traefik dashboard
  - http://localhost:8887/auth/ - the authentik landing page


> [!NOTE]
> ### Building the docker image locally
>
> Most of the time you will be using a prebuilt docker image. However, there is a special case where you will need
> to build it locally. This case is when you add a new python dependency to the project. In this case, build the
> image with:
>
> ```shell
> docker build \
>   --tag ghcr.io/naturalgis/seis-lab-data/seis-lab-data:$(git branch --show-current) \
>   --file docker/Dockerfile \
>   .
> ```
>
> Then stand up the docker compose stack with:
>
> ```shell
> CURRENT_GIT_BRANCH=$(git branch --show-current) docker compose -f docker/compose.dev.yaml up -d --force-recreate
> ```

> [!NOTE]
> ### Getting translations to work correctly in your local dev environment
>
> Because the docker compose file used for dev bind mounts the entire `src` directory, it will
> mask the container's own compiled `*.mo` files. This means that after running
> `seis-lab-data translations compile` you need to restart the `webapp` service for the changes to take effect.


### Data


## Running tests

Normal tests can be run from inside the `webapp` compose container, after installing the required dependencies:

```shell
docker compose --file docker/compose.dev.yaml exec webapp uv sync --locked --group dev
docker compose --file docker/compose.dev.yaml exec webapp uv run pytest
```

Integration tests can be run with the following incantation:

```shell
docker compose --file docker/compose.dev.yaml exec webapp uv run pytest -m integration
```

### End to end tests

End to end tests are run from outside the docker stack. They require that playwright is installed locally.
You can do this with:

```shell
uv run playwright install --with-deps chromium
```

Then tests can be run with:

```shell
uv run pytest \
    tests/e2e/ \
    -m e2e \
    --confcutdir tests/e2e \
    --user-email akadmin@email.com \
    --user-password admin123 \
    --base-url http://localhost:8888
```

The previous incantation will run all end to end tests in headless mode.
To run them in headed mode, you can use:

```shell
uv run pytest \
    tests/e2e/ \
    -m e2e \
    --confcutdir tests/e2e \
    --user-email akadmin@email.com \
    --user-password admin123 \
    --base-url http://localhost:8888 \
    --headed \
    --slowmo 1500
```

> [!NOTE]
> ##### Writing end to end tests
>
> Run an interactive shell with ipython. Start the browser in headed mode:
>
> ```python
> # when using ipython, playwright must be used in async mode
> from playwright.async_api import (
>     async_playwright,
>     expect,
> )
> async with async_playwright() as p:
>     browser = await p.chromium.launch(headless=False, slow_mo=1500)
>     page = await browser.new_page()
>     await page.goto("http://localhost:8888")
>
> ```

[docker]: https://www.docker.com/
[IPMA]: https://www.ipma.pt/pt/index.html
[pre-commit]: https://pre-commit.com/
[uv]: https://docs.astral.sh/uv/
