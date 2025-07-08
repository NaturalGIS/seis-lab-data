# seis-lab-data

Marine data catalog for internal usage at [IPMA]


## Development

- Clone this repo
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

- You should now be able to access the webapp at

    http://localhost:8888


## Running tests

Normal tests can be run from inside the `webapp` compose container, after installing the required dependencies:

```shell
docker compose --file docker/compose.dev.yaml exec webapp uv sync --locked --group dev
docker compose --file docker/compose.dev.yaml exec webapp uv run pytest
```

End to end tests can be run with the `end-to-end-tester` compose service, by issuing a one-off run:

```shell
docker compose --file docker/compose.dev.yaml run --rm end-to-end-tester
```


[docker]: https://www.docker.com/
[IPMA]: https://www.ipma.pt/pt/index.html
[pre-commit]: https://pre-commit.com/
[uv]: https://docs.astral.sh/uv/
