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
- `interactive-worker` – _worker_ [dramatiq] que executa as tarefas rápidas, iniciadas pelos utilizadores, como as modificações à BD (criar, atualizar, apagar, validar, publicar). Consome a fila `default`.
- `long-tasks-worker` – _worker_ [dramatiq] que executa as tarefas que podem demorar: pré-visualizações, miniaturas e exportações. Consome as filas `previews`, `thumbnails` e `exports`, para que estas tarefas nunca atrasem as interativas.
- `discovery-worker` – _worker_ [dramatiq] que executa as descobertas no arquivo, da fila `discovery`. Corre um processo, que descobre uma missão de cada vez; defina `DISCOVERY_WORKER_PROCESSES` no ambiente do `docker compose` para descobrir várias missões em paralelo.
- `message-broker` – uma instância [redis] que gere a passagem de mensagens entre a webapp e os _workers_.
- `web-gateway` – uma instância [traefik] que atua como _reverse proxy_ para o sistema.
- `auth-webapp` – uma instância [authentik] que trata da autenticação de utilizadores.

[authentik]: https://goauthentik.io/
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


## Traduções

A interface web está disponível em português (o idioma predefinido, `pt_PT`) e em inglês. Apenas a interface é
traduzida - os dados dos utilizadores, como os nomes e as descrições dos projetos, não o são. O inglês é o idioma de
origem: o catálogo inglês deixa as suas traduções vazias, pelo que a interface mostra os textos de origem.

Os textos são marcados como traduzíveis com `_()`:

-   No código Python, importe-o com `from starlette_babel import gettext_lazy as _`;
-   Nos templates Jinja, use `{{ _("algum texto") }}`, incluindo dentro de atributos como `placeholder`, `title` e
    `aria-label` sempre que estes contenham texto legível por humanos.

O texto marcado tem de ser um literal, dado que a extração não deteta textos construídos em tempo de execução.

As mensagens produzidas fora de um pedido, como as mensagens de erro das operações e os detalhes dos eventos emitidos
pelos workers, não podem ser traduzidas onde são produzidas, dado que aí não existe um idioma do utilizador. Em vez
disso, são marcadas com `errors.N_()`, que as mantém em inglês, e são traduzidas pelos stream handlers para o idioma
de quem estiver a ver a página:

-   Os valores são colocados em marcadores `%(nome)s` em vez de f-strings, para que o modelo da mensagem coincida com
    a sua entrada no catálogo - p. ex. `errors.SeisLabDataError(errors.N_("Project %(id)s does not exist."), id=str(project_id))`;
-   Os eventos transportam o modelo da mensagem em `details` e os seus valores em `details_params`. Um
    `SeisLabDataError` disponibiliza-os como `message` e `params`;
-   Um valor `status` contém o estado do recurso do evento, que os stream handlers também traduzem. Os restantes
    valores, como nomes e caminhos, são apresentados sem tradução;
-   Os detalhes que não constam dos catálogos, como o texto de erros de terceiros, são apresentados tal como estão.

As traduções são geridas com os comandos da CLI `seis-lab-data translations`. Após adicionar ou modificar textos
traduzíveis:

1.  Extraia os textos traduzíveis do código-fonte para um catálogo modelo (`src/messages.pot`, que não é registado
    no git):

    ```shell
    docker compose -f docker/compose.dev.yaml exec -ti webapp uv run seis-lab-data translations extract
    ```

2.  Atualize os catálogos de cada idioma (`src/seis_lab_data/translations/<idioma>/LC_MESSAGES/messages.po`) com os
    textos extraídos:

    ```shell
    docker compose -f docker/compose.dev.yaml exec -ti webapp uv run seis-lab-data translations update
    ```

3.  Traduza os novos textos no catálogo português. Quando um texto muda, a atualização copia a tradução de um texto
    semelhante e marca-a como `fuzzy`. Reveja cada entrada `fuzzy` e remova essa marca, dado que a compilação ignora
    as entradas `fuzzy`, o que faz com que a interface as mostre em inglês;

4.  Compile os catálogos para os ficheiros `.mo` usados pela aplicação web:

    ```shell
    docker compose -f docker/compose.dev.yaml exec -ti webapp uv run seis-lab-data translations compile
    ```

    Os ficheiros `.mo` não são registados no git - a imagem docker compila-os quando é construída. A stack docker
    compose de desenvolvimento monta a diretoria `src` via
    [bind mount](https://docs.docker.com/engine/storage/bind-mounts/), o que mascara os ficheiros `.mo` do próprio
    contentor, pelo que deve reiniciar o serviço `webapp` após a compilação para as alterações terem efeito.

O teste `tests/test_translations.py` falha sempre que um texto traduzível não tenha uma tradução portuguesa sem a
marca `fuzzy`.


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


##### GeoNode (opcional)

Instância [GeoNode](https://geonode.org/) v5.1.1, usada como destino para a exportação de registos
relacionados com campanhas. É composta por vários serviços (`geonode-db`, `geonode-django`,
`geonode-celery`, `geonode-nginx`, `geonode-geoserver` e `geonode-geoserver-data`). A sua
configuração está em `docker/geonode/geonode-dev.env`.

Estes serviços consomem bastantes recursos, pelo que apenas arrancam quando o perfil `geonode` do
compose está ativo:

```shell
docker compose -f docker/compose.dev.yaml --profile geonode up -d
```

O primeiro arranque é lento, pois o GeoNode executa as migrações da BD, carrega _fixtures_ e
recolhe os ficheiros estáticos.

- O GeoNode está acessível em http://geonode.localhost:8888, com as credenciais `admin` / `admin123`
- O GeoServer está acessível em http://geonode.localhost:8888/geoserver/, com as credenciais
  `admin` / `geoserver`
- Os outros serviços da stack (p. ex. `long-tasks-worker`) podem aceder diretamente à API do
  GeoNode em `http://django:8000`
- Os _logs_ de pedidos do uwsgi são escritos em `/var/log/geonode.log` dentro do contentor
  `geonode-django`

A exportação de registos relacionados com campanhas para o GeoNode é configurada com as seguintes
definições (a exportação fica desativada quando o URL não está definido):

- `SEIS_LAB_DATA__TARGET_GEONODE__URL` - URL através do qual o _backend_ acede à API do GeoNode
- `SEIS_LAB_DATA__TARGET_GEONODE__PUBLIC_URL` - URL através do qual os utilizadores acedem ao
  GeoNode, apenas necessário se for diferente do anterior, como acontece na stack de
  desenvolvimento
- `SEIS_LAB_DATA__TARGET_GEONODE__USERNAME` e `SEIS_LAB_DATA__TARGET_GEONODE__PASSWORD` -
  credenciais do utilizador do GeoNode em nome do qual o seis-lab-data atua, que fica como dono
  dos recursos exportados. Destina-se a ser uma conta de serviço, usada apenas pelo seis-lab-data
- `SEIS_LAB_DATA__TARGET_GEONODE__CLIENT_ID` e `SEIS_LAB_DATA__TARGET_GEONODE__CLIENT_SECRET` -
  credenciais de uma aplicação OAuth2 do GeoNode, que tem de ser _confidential_ e usar o tipo de
  _grant_ _resource owner password-based_. Cada exportação troca com ela as credenciais da conta
  de serviço por um _access token_, que é revogado no final
- `SEIS_LAB_DATA__PUBLIC_URL` - tem de estar definido também para os _workers_, uma vez que os
  recursos exportados para o GeoNode contêm uma ligação para a página do respetivo registo

Tanto a conta de serviço como a aplicação OAuth2 são criadas no GeoNode, seja na sua administração
Django (_People_ > _Users_ e _Django OAuth Toolkit_ > _Applications_) ou a partir da linha de
comandos.

As exportações correm na fila `exports`, consumida pelo serviço `long-tasks-worker`. A stack de
desenvolvimento já define todas estas definições, com credenciais fixas, cujas contrapartes no
GeoNode podem ser criadas com:

```shell
docker compose -f docker/compose.dev.yaml exec geonode-django python manage.py shell -c "
from django.contrib.auth import get_user_model
from oauth2_provider.models import get_application_model
Application = get_application_model()
user, _ = get_user_model().objects.get_or_create(username='sld-exporter')
user.set_password('sld-exporter-pass')
user.save()
Application.objects.update_or_create(
    client_id='sld-geonode-client-id',
    defaults=dict(
        name='seis-lab-data',
        user=user,
        client_secret='sld-geonode-client-secret',
        client_type=Application.CLIENT_CONFIDENTIAL,
        authorization_grant_type=Application.GRANT_PASSWORD,
    ),
)
"
```

Após o que os serviços que as utilizam têm de ser recriados:

```shell
docker compose -f docker/compose.dev.yaml --profile geonode up -d
```


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

## Relatório de testes

Pode ser gerado um relatório PDF dos resultados dos testes para o cliente, de quem não se espera que leia os registos
do CI. O relatório contém uma introdução estática, um resumo dos resultados e depois todos os testes, agrupados por
módulo de testes, cada um descrito pela sua _docstring_ e apresentado com o seu resultado. A introdução é o ficheiro
Markdown `scripts/test-report/intro.md` e a paginação é definida pelo modelo Jinja `scripts/test-report/report.j2.html`.

Como as _docstrings_ constituem o conteúdo do relatório, os módulos de testes e os testes têm de as ter, o que é
verificado pelo ruff (regras `D100` e `D103`, aplicadas apenas a `tests/**/test_*.py`). São escritas para o cliente, em
inglês formal e sem termos de implementação:

- a primeira linha da _docstring_ do módulo é o título da sua secção no relatório (um grupo nominal, sem ponto final),
  seguida de uma linha em branco e de uma breve descrição da área funcional abrangida pelo módulo
- a _docstring_ de cada teste enuncia o comportamento que verifica, por exemplo _A published project can be deleted,
  and the notification of its deletion still shows its name._

O relatório é gerado a partir dos ficheiros JSON escritos pelo plugin [pytest-json-report], um por conjunto de testes.
Execute cada conjunto com as opções do plugin e copie depois os ficheiros para fora do contentor `webapp`:

```shell
JSON_REPORT_OPTIONS="--json-report --json-report-omit collectors log streams"

docker compose --file docker/compose.dev.yaml exec webapp \
    uv run pytest ${JSON_REPORT_OPTIONS} --json-report-file=/tmp/unit.json
docker compose --file docker/compose.dev.yaml exec webapp \
    uv run pytest -m integration ${JSON_REPORT_OPTIONS} --json-report-file=/tmp/integration.json
docker compose --file docker/compose.dev.yaml cp webapp:/tmp/unit.json .
docker compose --file docker/compose.dev.yaml cp webapp:/tmp/integration.json .

uv run pytest \
    tests/e2e/ \
    -m e2e \
    --confcutdir tests/e2e \
    --user-email akadmin@email.com \
    --user-password admin123 \
    --base-url http://localhost:8888 \
    ${JSON_REPORT_OPTIONS} \
    --json-report-file=e2e.json
```

O relatório é gerado fora da stack docker, porque o [WeasyPrint], que o converte em PDF, requer a biblioteca Pango (em
Debian e Ubuntu, os pacotes `libpango-1.0-0` e `libpangoft2-1.0-0`), que a imagem docker não inclui. Gere-o a partir da
raiz do repositório, com a mesma versão do código que executou os testes, pois as descrições são lidas dos ficheiros
fonte dos testes:

```shell
uv run --only-group report python scripts/render_test_report.py \
    --results unit.json integration.json e2e.json \
    --release v1.0.0 \
    --commit $(git rev-parse HEAD) \
    --output test-report.pdf
```

Execute `uv run --only-group report python scripts/render_test_report.py --help` para conhecer as restantes opções, por
exemplo `--html-output`, que guarda o documento HTML intermédio, útil para modificar o modelo.

O fluxo de trabalho de CI guarda os ficheiros JSON de cada execução no artefacto `test-results-json`. Para cada _tag_,
gera também o relatório e guarda-o no artefacto `test-report-<tag>`, que é mantido durante 90 dias e é gerado mesmo
quando há testes que falham, apresentando as falhas.


[docker]: https://www.docker.com/
[IPMA]: https://www.ipma.pt/pt/index.html
[playwright]: https://playwright.dev/python/
[pre-commit]: https://pre-commit.com/
[pytest-json-report]: https://pypi.org/project/pytest-json-report/
[uv]: https://docs.astral.sh/uv/
[WeasyPrint]: https://weasyprint.org/
[woodpecker]: https://woodpecker-ci.org/
