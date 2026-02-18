# Desenvolvimento

<span class="no-pdf">
    [ :material-file-pdf-box: Descarregar versão PDF](assets/documents/seis-lab-data-development-guide.pdf){ .md-button .no-pdf }
</span>

Este projeto é composto por múltiplos serviços, que são orquestrados com `docker compose`.
O ficheiro `docker/compose.dev.yaml` contem as instruções adequadas para desenvolvimento.

!!! tip "Dica"
    Quando a _stack_ de desenvolvimento do Docker estiver ativa e em execução, execute os comandos docker compose
    com esta incantação:

    ```shell
    docker compose -f docker/compose.dev.yaml <docker-command> <service-name>
    ```

    Isto facilita o ajuste dos comandos ao âmbito deste projeto.

Os serviços mais relevantes são:

- `webapp` – a aplicação web principal, implementada com [starlette], [sqlmodel], [jinja] e [datastar].
- `processing-worker` – serviço executa a maior parte do processamento. É um _worker_ [dramatiq].
- `message-broker` – uma instância [redis] que gere a passagem de mensagens entre a webapp e o processing worker.
- `web-gateway` – uma instância [traefik] que atua como _reverse proxy_ para o sistema.
- `auth-webapp` – uma instância [authentik] que trata da autenticação de utilizadores.
- `caddy-file-server` – uma instância [caddy] que serve datasets locais via HTTP.

[authentik]: https://goauthentik.io/
[caddy]: https://caddyserver.com/
[datastar]: https://data-star.dev/
[dramatiq]: https://dramatiq.io/
[jinja]: https://jinja.palletsprojects.com/en/stable/
[redis]: https://redis.io/
[starlette]: https://starlette.dev/
[sqlmodel]: https://sqlmodel.tiangolo.com/
[traefik]: https://traefik.io/


## Configuração do ambiente

Comece por obter os datasets de exemplo que foram disponibilizados pelo cliente. Estes encontram-se no
ficheiro `ipma/2025-marine-data-catalog/sample-data/20251125_datasample01_restored_data.tar.gz`, que está disponível
na plataforma interna de base de conhecimento.

Crie uma diretoria base para os datasets do projeto (por exemplo em `~/data/seis-lab-data`), obtenha o arquivo
e extraia-o dentro desta diretoria:

```shell
mkdir -p ~/data/seis-lab-data
cd ~/data/seis-lab-data

# obtenha o arquivo tar para esta dir e extraia-o
tar -xvf 20251125_datasample01_restored_data.tar.gz

# remova o arquivo após a extração
rm 20251125_datasample01_restored_data.tar.gz
```

Deverá obter algo semelhante a isto (listagem abreviada):

```shell
ricardo@tygra:~/data/seis-lab-data/$ tree -L 4
.
└── prr_eolicas
    └── base-final
        └── surveys
            └── owf-2025
```

Agora, clone este repositório localmente:

```shell
cd ~/dev  # ou onde preferir guardar o código

git clone [https://github.com/NaturalGIS/seis-lab-data.git](https://github.com/NaturalGIS/seis-lab-data.git)
cd seis-lab-data
```

Para simplificar a montagem da diretoria de dados dentro dos serviços docker, o projeto assume que existe uma
diretoria `sample-data` na raiz do repositório. Como tal, crie um link simbólico (symlink) a apontar para a
diretoria de dados que criou acima:

```shell
# assumindo que a sua diretoria sample-data está em `~/data/seis-lab-data`
ln -s ~/data/seis-lab-data sample-data
```

Certifique-se de que tem o [docker] e o [uv] instalados na sua máquina. Utilize o uv para
instalar o projeto localmente:

```shell
uv sync --group dev --locked
```

Instale os hooks de pre-commit incluídos:

```shell
uv run pre-commit install
```

Efetue o _pull_ das imagens docker do projeto dos respetivos registos (poderá precisar de fazer login em ghcr.io):

```shell
docker compose -f docker/compose.dev.yaml pull
```

De seguida, lance a stack:

```shell
docker compose -f docker/compose.dev.yaml up -d
```

Deverá agora conseguir aceder à webapp em http://localhost:8888. Continue para a secção de arranque de uma
instalação nova.

Pode fazer login no sistema usando as credenciais:

- utilizador: `akadmin@email.com`
- password: `admin123`


## Arranque de uma instalação nova

O processo de arranque (_bootstrapping_) consiste em :

- Criar/atualizar a base de dados,
- Carregar as variáveis predefinidas
- Opcionalmente, adicionar dados de exemplo.

O _bootstrapping_ é feito utilizando a aplicação de linha de comandos (CLI) `seis-lab-data`, que está
disponível no serviço docker compose chamado `webapp`:

```shell
docker compose -f docker/compose.dev.yaml exec -ti webapp uv run seis-lab-data --help
```

Execute os seguintes comandos:

```shell
# inicializar a BD
docker compose -f docker/compose.dev.yaml exec -ti webapp uv run seis-lab-data db upgrade

# adicionar dados predefinidos
docker compose -f docker/compose.dev.yaml exec -ti webapp uv run seis-lab-data bootstrap all

# opcionalmente, carregar registos de exemplo
docker compose -f docker/compose.dev.yaml exec -ti webapp uv run seis-lab-data dev load-all-samples

# opcionalmente, gerar registos sintéticos (útil para a UI)
docker compose -f docker/compose.dev.yaml exec -ti webapp uv run seis-lab-data dev generate-many-projects --num-projects=50
```


## Notas adicionais

A imagem docker de desenvolvimento usa a tag `latest` e é reconstruída em cada commit no ramo chamado `main` do
repositório. Assim sendo, sempre que houver modificações no código, antes de iniciar a stack de serviços, é
aconselhável puxar a versão mais recente da imagem docker:

```shell
docker compose -f docker/compose.dev.yaml pull webapp
docker compose -f docker/compose.dev.yaml up -d
```


!!! note "Criar a imagem docker localmente"

    Se adicionar uma nova dependência Python, deverá criar a imagem localmente:

    ```shell
    docker build \
      --tag ghcr.io/naturalgis/seis-lab-data/seis-lab-data:$(git branch --show-current) \
      --file docker/Dockerfile \
      .
    ```

    Depois, reinicie a stack:

    ```shell
    CURRENT_GIT_BRANCH=$(git branch --show-current) docker compose -f docker/compose.dev.yaml up -d --force-recreate
    ```

!!! note "Traduções"

    Como a diretoria `src` é montada via usando um [bind mount](https://docs.docker.com/engine/storage/bind-mounts/),
    ficheiros `*.mo` da imagem são mascarados pelos que estiverem presentes no disco local. Como tal, de modo a que
    as traduções funcionem corretamente, será necessário correr o commando:

    ```shell
    seis-lab-data translations compile
    ```

    Em seguida, reinicie o serviço `webapp`.


# Execução de testes

Os testes normais correm dentro do contentor webapp:

```shell
docker compose --file docker/compose.dev.yaml exec webapp uv sync --locked --group gdal --group dev
docker compose --file docker/compose.dev.yaml exec webapp uv run pytest
```

Testes de integração:

```shell
docker compose --file docker/compose.dev.yaml exec webapp uv run pytest -m integration
```

## Testes end-to-end (E2E)

A execução dos testes E2E utiliza o [playwright](https://playwright.dev/python/). Como tal, a sua execução requer
a instalação de dependências adicionais:

```shell
uv run playwright install --with-deps chromium
```

Os testes podem ser executados com o comando:

```shell
uv run pytest tests/e2e/ \
    -m e2e \
    --confcutdir tests/e2e \
    --user-email akadmin@email.com \
    --user-password admin123 \
    --base-url http://localhost:8888
```

!!! TIP "Dica"

    Para correr os tests E2E no modo _headed_ (_i.e._ com execução de uma interface gráfica), adicione os
    parâmetros `--headed` e `--slowmo 1500`.

    ```shell
    uv run pytest tests/e2e/ \
        -m e2e \
        --confcutdir tests/e2e \
        --user-email akadmin@email.com \
        --user-password admin123 \
        --base-url http://localhost:8888 \
        --headed \
        --slowmo 1500
    ```


[docker]: https://www.docker.com/
[IPMA]: https://www.ipma.pt/pt/index.html
[pre-commit]: https://pre-commit.com/
[uv]: https://docs.astral.sh/uv/
[woodpecker]: https://woodpecker-ci.org/
