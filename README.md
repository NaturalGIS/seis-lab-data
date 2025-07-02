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


[docker]: https://www.docker.com/
[IPMA]: https://www.ipma.pt/pt/index.html
[pre-commit]: https://pre-commit.com/
[uv]: https://docs.astral.sh/uv/
