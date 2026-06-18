# Desenvolvimento

<span class="no-pdf">
    [ :material-file-pdf-box: Descarregar versão PDF](assets/documents/seis-lab-data-development-guide.pdf){ .md-button .no-pdf }
</span>

Este documento é o entregável de projeto _D03 - Documentação orientada ao programador sobre como configurar o projeto_.
Contém informação sobre como configurar um ambiente de desenvolvimento local adequado para trabalhar no projeto
SeisLabData.

Este projeto é composto por múltiplos serviços, que são orquestrados com `docker compose`.
O ficheiro `docker/compose.dev.yaml` contém as instruções adequadas para desenvolvimento.

!!! tip "Dica"
    Quando a _stack_ de desenvolvimento do Docker estiver ativa e em execução, execute os comandos docker compose
    com esta incantação:

    ```shell
    docker compose -f docker/compose.dev.yaml <docker-command> <service-name>
    ```

    Isto facilita o ajuste dos comandos ao âmbito deste projeto.

Os serviços mais relevantes são:

- `webapp` – a aplicação web principal, implementada com [starlette], [sqlmodel], [jinja] e [datastar].
- `processing-worker` – serviço que executa a maior parte do processamento e das modificações à BD. É um _worker_ [dramatiq].
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
ficheiro

```ipma/2025-marine-data-catalog/sample-data/20251125_datasample01_restored_data.tar.gz```

que está disponível na plataforma interna de base de conhecimento.

Crie uma diretoria base para os datasets do projeto (por exemplo em `~/data/seis-lab-data`),
obtenha o arquivo e extraia-o dentro desta diretoria:

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

git clone https://github.com/NaturalGIS/seis-lab-data.git
cd seis-lab-data
```

Para simplificar a montagem da diretoria de dados dentro dos serviços docker, o projeto assume que existe uma
diretoria `sample-data` na raiz do repositório. Como tal, crie um link simbólico a apontar para a
diretoria de dados que criou acima:

```shell
# assumindo que a sua diretoria sample-data está em `~/data/seis-lab-data`
ln -s ~/data/seis-lab-data sample-data
```

Certifique-se de que tem o [docker] e o [uv] instalados na sua máquina.

Utilize o `uv` para instalar o projeto localmente:

```shell
uv sync --group dev --locked
```

Instale os hooks de [pre-commit] incluídos:

```shell
uv run pre-commit install
```

Efetue o _pull_ das imagens docker do projeto dos respetivos registos (poderá precisar de fazer login
em `ghcr.io`):

```shell
docker compose -f docker/compose.dev.yaml pull
```

De seguida, lance a stack:

```shell
docker compose -f docker/compose.dev.yaml up -d
```

Deverá agora conseguir aceder à webapp em

    http://localhost:8888

Continue para a secção de [arranque de uma instalação nova](#arranque-de-uma-instalacao-nova).


## Arranque de uma instalação nova

O processo de arranque (_bootstrapping_) consiste em:

- Criar/atualizar a base de dados;
- Carregar as variáveis predefinidas nas tabelas apropriadas da BD;
- Opcionalmente, adicionar alguns projetos, missões de levantamento e registos de exemplo.

O _bootstrapping_ é feito utilizando a CLI `seis-lab-data`, que está disponível no serviço
`webapp`. Contém muitos comandos e pode ser invocada assim:

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

# opcionalmente, gerar um grande número de registos sintéticos
# (mais útil quando se trabalha na interface web)
docker compose -f docker/compose.dev.yaml exec -ti webapp uv run seis-lab-data dev generate-many-projects --num-projects=50
```


## Notas adicionais

A imagem docker de desenvolvimento usa a tag `latest` e é reconstruída em cada commit no ramo `main`
do repositório. Assim sendo, deverá executar

```shell
docker compose -f docker/compose.dev.yaml pull webapp
docker compose -f docker/compose.dev.yaml up -d
```

sempre que souber que houve _merges_ recentes.


!!! note "Criar a imagem docker localmente"

    Na maior parte das vezes irá utilizar uma imagem docker pré-construída. No entanto, existe um caso
    especial em que será necessário criá-la localmente: quando adicionar uma nova dependência Python ao
    projeto. Nesse caso, crie a imagem com:

    ```shell
    docker build \
      --tag ghcr.io/naturalgis/seis-lab-data/seis-lab-data:$(git branch --show-current) \
      --file docker/Dockerfile \
      .
    ```

    Depois, reinicie a stack com:

    ```shell
    CURRENT_GIT_BRANCH=$(git branch --show-current) docker compose -f docker/compose.dev.yaml up -d --force-recreate
    ```


!!! note "Traduções no ambiente de desenvolvimento local"

    Como o ficheiro docker compose de desenvolvimento monta a diretoria `src` inteira via
    [bind mount](https://docs.docker.com/engine/storage/bind-mounts/), os ficheiros `*.mo` compilados
    do contentor são mascarados pelos ficheiros presentes no disco local. Isto significa que após
    executar `seis-lab-data translations compile` é necessário reiniciar o serviço `webapp` para as
    alterações terem efeito.


## Serviços auxiliares de desenvolvimento

A stack de desenvolvimento inclui alguns serviços adicionais relevantes:


##### dozzle

Instância [dozzle](https://dozzle.dev/), útil para monitorizar os _logs_ dos vários serviços da
stack. Acessível em http://localhost:8888/monitoring


##### jupyter

Instância [jupyter](https://jupyter.org/), útil para escrever notebooks ou interagir com um REPL
Python. Acessível em http://localhost:5002


##### pg-admin

Instância [pg-admin](https://www.pgadmin.org/), útil para inspecionar as bases de dados da stack.
Acessível em http://pgadmin.localhost:8888 com as credenciais:

- utilizador: `dev@dev.dev`
- password: `dev`


# Execução de testes

Os testes normais correm dentro do contentor `webapp`, após instalar as dependências necessárias:

```shell
docker compose --file docker/compose.dev.yaml exec -ti webapp uv sync --locked --group gdal --group dev
docker compose --file docker/compose.dev.yaml exec -ti webapp uv run pytest
```

Os testes de integração correm com:

```shell
docker compose --file docker/compose.dev.yaml exec webapp uv run pytest -m integration
```

## Testes end-to-end (E2E)

Os testes E2E correm fora da stack docker e requerem a instalação do [playwright] localmente:

```shell
uv run playwright install --with-deps chromium
```

Os testes podem então ser executados com:

```shell
uv run pytest \
    tests/e2e/ \
    -m e2e \
    --confcutdir tests/e2e \
    --user-email akadmin@email.com \
    --user-password admin123 \
    --base-url http://localhost:8888
```

A incantação anterior executa todos os testes E2E em modo _headless_.
Para os executar em modo _headed_:

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


[docker]: https://www.docker.com/
[IPMA]: https://www.ipma.pt/pt/index.html
[playwright]: https://playwright.dev/python/
[pre-commit]: https://pre-commit.com/
[uv]: https://docs.astral.sh/uv/
[woodpecker]: https://woodpecker-ci.org/
