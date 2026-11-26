# Development

This document is project deliverable _D11 - Final version of developer-oriented documentation_. It contains
information on how to set up a local development environment suitable for working on the SeisLabData project, along
with an overview of the system's architecture.

This project is composed of a set of multiple services which are deployed with `docker compose`. The
`docker/compose.dev.yaml` file is a compose file suitable for development.

!!! tip
    When the development docker stack is up and running, run docker compose commands with this incantation:

    ```shell
    docker compose -f docker/compose.dev.yaml <docker-command> <service-name>
    ```

    This makes it easier to scope the commands to this project.

The more relevant services are:

- `webapp` - the main web application, which is implemented with [starlette], [sqlmodel], [jinja] and [datastar]
- `interactive-worker` - the [dramatiq] worker that runs the quick, user-facing tasks, such as
  the state-changing DB modifications (create, update, delete, validate, publish). It consumes the
  `default` queue
- `long-tasks-worker` - the [dramatiq] worker that runs the tasks which may take long: previews,
  thumbnails and exports. It consumes the `previews`, `thumbnails` and `exports` queues, so these
  tasks never delay the interactive ones
- `discovery-worker` - the [dramatiq] worker that runs archive discoveries, from the `discovery`
  queue. It runs one process, discovering one mission at a time; set `DISCOVERY_WORKER_PROCESSES`
  in the environment of `docker compose` to discover several missions in parallel
- `db` - a [PostGIS] instance that holds the application's database
- `message-broker` - a [redis] instance that passes messages between the webapp and the workers
- `web-gateway` - a [traefik] instance that acts as a reverse proxy for the system
- `auth-webapp` - an [authentik] instance that takes care of user authentication
- `martin-tile-server` - a [martin] instance that serves the bathymetry base map tiles, from the PMTiles files in the
  `sample-data/pmtiles` directory
- `docs` - serves this documentation, as explained in [Writing documentation](writing-docs.md)

[authentik]: https://goauthentik.io/
[datastar]: https://data-star.dev/
[dramatiq]: https://dramatiq.io/
[jinja]: https://jinja.palletsprojects.com/en/stable/
[martin]: https://martin.maplibre.org/
[PostGIS]: https://postgis.net/
[redis]: https://redis.io/
[starlette]: https://starlette.dev/
[sqlmodel]: https://sqlmodel.tiangolo.com/
[traefik]: https://traefik.io/


## Environment set up

Start by retrieving the sample datasets that have been made available by the
client. These are contained in the file

```ipma/2025-marine-data-catalog/sample-data/20251125_datasample01_restored_data.tar.gz```

which is available at the internal knowledge base platform.

Create a base directory for the project's datasets (for example at `~/data/seis-lab-data`)
and then get the archive and extract it inside this directory:

```shell
mkdir -p ~/data/seis-lab-data
cd ~/data/seis-lab-data

# now get the tar archive into this dir and extract it
tar -xvf 20251125_datasample01_restored_data.tar.gz

# remove the archive after extraction
rm 20251125_datasample01_restored_data.tar.gz
```

You should get something that looks like this (this is an abbreviated listing):

```shell
$ tree -L 4
.
└── prr_eolicas
    └── base-final
        └── surveys
            └── owf-2025
```

Now clone this repo locally:

```shell
cd ~/dev  # or wherever you want to store the code

git clone https://github.com/NaturalGIS/seis-lab-data.git
cd seis-lab-data
```

In order to simplify mounting the data directory inside docker services, the project assumes
there is a `sample-data` directory under the root of the repo. As such, make a symlink
pointing to the data directory you created above:

```shell
# assuming your sample-data directory lives at `~/data/seis-lab-data`
ln -s ~/data/seis-lab-data sample-data
```

Ensure you have installed [docker] and [uv] on your machine.

Use `uv` to get the project installed locally:

```shell
uv sync --group dev --locked
```

Install the included [pre-commit] hooks:

```shell
uv run pre-commit install
```

Pull the project docker images from their respective registries. You will likely need to log in
to the `ghcr.io` registry.

```shell
docker compose -f docker/compose.dev.yaml pull
```

Then launch the stack:

```shell
docker compose -f docker/compose.dev.yaml up -d
```

You should now be able to access the webapp at

    http://localhost:8888

Please continue with the [bootstrapping](#bootstrapping-a-fresh-installation) section.


## Bootstrapping a fresh installation

The bootstrap process consists of:

- Creating/upgrading the database;
- Loading all default variables into the appropriate DB tables;
- Optionally adding some default projects, survey missions and survey-related records.

Bootstrapping is done by using the `seis-lab-data` CLI, which is available in the `webapp`
service. It contains many commands and can be called like this:

```shell
docker compose -f docker/compose.dev.yaml exec -ti webapp uv run seis-lab-data --help
```

Run the following commands:

```shell
# initialize the DB
docker compose -f docker/compose.dev.yaml exec -ti webapp uv run seis-lab-data db upgrade

# add default data
docker compose -f docker/compose.dev.yaml exec -ti webapp uv run seis-lab-data bootstrap all

# optionally, load sample records
docker compose -f docker/compose.dev.yaml exec -ti webapp uv run seis-lab-data dev load-all-samples

# also optionally, generate a large number of synthetic records
# (this is perhaps more useful when working on the web UI)
docker compose -f docker/compose.dev.yaml exec -ti webapp uv run seis-lab-data dev generate-many-projects --num-projects=50
```

## Additional notes

The docker image used for development uses docker's `latest` tag and is rebuilt whenever there are commits to the
repo's `main` branch. As such you should be sure to run

```shell
docker compose -f docker/compose.dev.yaml pull webapp
docker compose -f docker/compose.dev.yaml up -d
```

whenever you know there have been recent merges.


!!! note "Building the docker image locally"

    Most of the time you will be using a prebuilt docker image. However, there is a special case where you will need
    to build it locally. This case is when you add a new Python dependency to the project. In this case, build the
    image with:

    ```shell
    docker build \
      --tag ghcr.io/naturalgis/seis-lab-data/seis-lab-data:$(git branch --show-current) \
      --file docker/Dockerfile \
      .
    ```

    Then stand up the docker compose stack with:

    ```shell
    CURRENT_GIT_BRANCH=$(git branch --show-current) docker compose -f docker/compose.dev.yaml up -d --force-recreate
    ```


## Mounting the production archive locally

If needed, you can use sshfs to mount the production archive locally.

Install sshfs, then enable the `user_allow_other` option in the fuse config and you should be able to mount it locally.
In the commands below, `<your-data-root>` is the directory that the `sample-data` symlink points to (_e.g._
`~/data/seis-lab-data`), which the docker services mount at `/data`. The archive thus becomes available inside the
containers at `/data/production-archive`.

```shell
sudo apt install sshfs

# now edit /etc/fuse.conf and uncomment the line that has `user_allow_other`

mkdir <your-data-root>/production-archive

# this mounts the archive
sshfs <name-of-your-ssh-alias>:/mnt/seislab_data \
    <your-data-root>/production-archive \
    -o allow_other \
    -o reconnect \
    -o ServerAliveInterval=15

# now you must restart the docker compose stack in order for docker to be able to see the mount
docker compose -f docker/compose.dev.yaml up -d --force-recreate
```

You can later unmount it with:

```shell
fusermount -u <your-data-root>/production-archive
```


## Architecture

### Domain model

The catalog is organized in this hierarchy:

```
Project
  └── SurveyMission (many per project)
        └── SurveyRelatedRecord (many per mission)
              └── RecordAsset (many per record)
```

Projects, survey missions and survey-related records each have a status (`DRAFT`, `PUBLISHED`, plus
some transient processing states), a validation result and a spatial and temporal extent. Survey-related records
also reference the `DatasetCategory` and `WorkflowStage` lookup tables and can be linked to other records. The
database models are defined in `src/seis_lab_data/db/models.py`.

### Source layout

The code lives in the `src/seis_lab_data` Python package:

| Module | Contents |
|--------|----------|
| `webapp/` | The [starlette] web application: `routes/` holds the route handlers, `streamhandlers/` the handlers that turn pub/sub messages into SSE events, `forms/` the form definitions, `templates/` the [jinja] templates and `stacapi/` a read-only STAC API, mounted at `/stac` |
| `operations/` | Business logic, used by both the routes and the workers |
| `permissions/` | Permission checks |
| `db/` | Database models, along with `queries/` (read operations) and `commands/` (write operations) |
| `migrations/` | Alembic database migrations |
| `schemas/` | Pydantic schemas, identifiers, events and messages |
| `tasks/` | The [dramatiq] actors, broker and middleware, along with the `extractors/`, which read the metadata of the files found by discovery, and the `derivers/`, which generate previews and thumbnails |
| `cliapp/` | The `seis-lab-data` CLI |
| `translations/` | The UI translation catalogs |
| `dispatch.py`, `subscribers.py` | Publishing of events to Redis and subscription to them |
| `config.py` | Application settings, which are read from `SEIS_LAB_DATA__*` environment variables |

### Request flow

Requests follow the path routes → operations → permissions, queries and commands:

-   **Routes** get the current user from the request (`None` for anonymous users), get a DB session and call an
    operation;
-   **Operations** fetch the relevant DB objects, check the user's permissions, call a command and emit an event
    reporting what happened;
-   **Permissions** are plain synchronous functions which receive model instances and the user, and make no DB calls;
-   **Queries** come in two variants for listing each entity: `list_published_*`, for anonymous users, and `list_*`,
    for authenticated users. The operations pick the right one.

### Authentication and permissions

Users authenticate with [authentik], via OpenID Connect. There is no self-registration: user accounts are created
by a system administrator in authentik. The local `appuser` table is merely a cache of authentik's user data,
updated on each login and on each renewal of the access token.

The session is kept in a signed cookie, which holds the user info claims together with the access token and the
refresh token. The access token is valid for one hour and is checked with authentik's introspection endpoint at
most once every `auth_token_introspection_cache_seconds`. Once it has expired, or authentik reports it as no
longer active, it is renewed with the refresh token (the `offline_access` scope), and the user info claims,
roles included, are fetched again. The user is logged out only when authentik refuses the renewal. The refresh
token is valid for a week (the provider's `refresh_token_validity`, in the authentik blueprints), which the
`session_max_age_seconds` setting must not exceed, and authentik only replaces it once less than
`refresh_token_threshold` of its validity remains, so that concurrent requests renewing the access token with
the same refresh token all succeed. Logging out revokes both tokens in authentik, since ending the authentik
session does not invalidate them.

Permissions are based on the user's roles, which authentik derives from the user account:

-   Anonymous users can only read published resources;
-   Authenticated users can read all resources, including unpublished ones;
-   Users with the `system-admin` role (authentik superusers) or the `catalog-editor` role (members of the
    `seis-lab-data-catalog-editors` authentik group) can also create, modify, validate, publish and delete
    resources.

### Asynchronous processing

State-changing actions (create, update, delete, validate, publish, discover, export, ...) are not performed in the
web request. They are instead run by the [dramatiq] workers, which report their outcome back to the browser:

```
Browser ── request ──► webapp route ── enqueue task ──► Redis broker
   ▲                                                         │
   │                                                         ▼
   └── SSE stream ◄── webapp route ◄── Redis pub/sub ◄── worker runs the task
```

1.  When a page that triggers tasks loads, it opens a long-lived server-sent events (SSE) stream, carrying a request
    ID generated when the page was rendered;
2.  The browser sends the action to a route, along with the request ID. The route enqueues the corresponding actor
    and returns immediately;
3.  A worker runs the actor, which calls the operations layer. The operation emits typed events (defined in
    `schemas/events.py`), which are published as messages on a Redis pub/sub topic for the resource type;
4.  The SSE stream route of the page is subscribed to that topic. It passes each message to the stream handler
    registered for its type, which yields [datastar] events: showing notifications, updating page signals or
    reloading the page;
5.  Datastar applies these events to the page.

Tasks which may take long run in their own queues (`previews`, `thumbnails`, `exports` and `discovery`), consumed by
worker services separate from the `interactive-worker`, so that they never delay the interactive tasks. While a task
works on a record, it keeps it in a busy status (_e.g._ `UNDER_EXPORT`), which prevents the record from being
modified or deleted meanwhile.


## Modifying the database

We are using [alembic](https://alembic.sqlalchemy.org/en/latest/) for tracking database modifications. This means that
all modifications to the database schema must be done through alembic migrations. In order to generate a new migration:

-   Perform whatever modifications you need to the database models in the code - these are located in
    `src/seis_lab_data/db/models.py`;

-   Ask alembic to autogenerate a suitable DB migration file by running a custom seis-lab-data CLI command:

    ```shell
    docker compose \
        -f docker/compose.dev.yaml \
        exec -ti webapp \
        uv run \
        seis-lab-data db generate-migration "short description of the migration"
    ```

-   Manually inspect the autogenerated file in order to check that it is correct and make any necessary modifications.
    Migration files are located in `src/seis_lab_data/migrations/versions/` and are named with a timestamp and a short
    description of the migration;

-   If the migration is correct, apply it to the database with:

    ```shell
    docker compose -f docker/compose.dev.yaml exec -ti webapp uv run seis-lab-data db upgrade
    ```


## Translations

The web UI is available in Portuguese (the default, `pt_PT`) and English. Only the UI is translated - user data,
such as the names and descriptions of projects, is not. English is the source language: the English catalog leaves
its translations empty, which makes the UI show the source strings.

Strings are marked as translatable with `_()`:

-   In Python code, import it with `from starlette_babel import gettext_lazy as _`;
-   In Jinja templates, use `{{ _("some text") }}`, including inside attributes such as `placeholder`, `title` and
    `aria-label` whenever they hold human-readable text.

The marked string must be a literal, as the extraction does not see strings built at runtime.

Messages produced outside of a request, such as the error messages of the operations and the details of the events
emitted by the workers, cannot be translated where they are produced, as there is no user locale there. They are
marked with `errors.N_()` instead, which leaves them in English, and are translated by the stream handlers into the
locale of whoever is viewing the page:

-   Values go into `%(name)s` placeholders rather than f-strings, so that the template stays the same as its catalog
    entry - e.g. `errors.SeisLabDataError(errors.N_("Project %(id)s does not exist."), id=str(project_id))`;
-   Events carry the template in `details` and its values in `details_params`. A `SeisLabDataError` provides them as
    its `message` and `params`;
-   A `status` value holds the raw status of the event's resource, which the stream handlers translate as well. Other
    values, such as names and paths, are shown untranslated;
-   Details missing from the catalogs, such as the text of third-party errors, are shown as they are.

Translations are managed with the `seis-lab-data translations` CLI commands. After adding or modifying translatable
strings:

1.  Extract the translatable strings from the source code into a template catalog (`src/messages.pot`, which is
    not tracked by git):

    ```shell
    docker compose -f docker/compose.dev.yaml exec -ti webapp uv run seis-lab-data translations extract
    ```

2.  Update the catalogs of each locale (`src/seis_lab_data/translations/<locale>/LC_MESSAGES/messages.po`) with the
    extracted strings:

    ```shell
    docker compose -f docker/compose.dev.yaml exec -ti webapp uv run seis-lab-data translations update
    ```

3.  Translate the new strings in the Portuguese catalog. When a string changes, the update copies the translation of
    a similar string and flags it as `fuzzy`. Review each fuzzy entry and remove its flag, since the compilation
    skips fuzzy entries, which makes the UI show them in English;

4.  Compile the catalogs into the `.mo` files used by the web application:

    ```shell
    docker compose -f docker/compose.dev.yaml exec -ti webapp uv run seis-lab-data translations compile
    ```

    The `.mo` files are not tracked by git - the docker image compiles them when it is built. The dev docker compose
    stack bind mounts the `src` directory, which masks the container's own `.mo` files, so restart the `webapp`
    service after compiling for the changes to take effect.

The `tests/test_translations.py` test fails whenever a translatable string lacks a non-fuzzy Portuguese translation.


## Auxiliary dev services

The development docker compose stack includes some additional relevant services:


### dozzle

This is a [dozzle](https://dozzle.dev/) instance, useful for monitoring the logs of the various services in the stack.
It is accessible at http://localhost:8888/monitoring


### jupyter

This is a [jupyter](https://jupyter.org/) instance, useful for writing notebooks or interacting
with a Python REPL. It is accessible at http://localhost:5002


### pg-admin

A [pg-admin](https://www.pgadmin.org/) instance, useful for inspecting the stack's databases.
It is accessible at http://pgadmin.localhost:8888 and login credentials are:

- user: `dev@dev.dev`
- password: `dev`


### GeoNode (optional)

!!! note

    The GeoNode service is only meant for use during development, as the production environment will have
    an externally managed GeoNode as its target.

A [GeoNode](https://geonode.org/) v5.1.1 instance, used as the target for exporting survey-related
records. It is made up of several services (`geonode-db`, `geonode-django`, `geonode-celery`,
`geonode-nginx`, `geonode-geoserver` and `geonode-geoserver-data`). Its configuration lives in
`docker/geonode/geonode-dev.env`.

These services are resource-hungry, so they only start when the `geonode` compose profile is
active:

```shell
docker compose -f docker/compose.dev.yaml --profile geonode up -d
```

The first boot is slow, because GeoNode runs its DB migrations, loads fixtures and collects
static files.

- GeoNode is accessible at http://geonode.localhost:8888, with credentials `admin` / `admin123`
- GeoServer is accessible at http://geonode.localhost:8888/geoserver/, with credentials
  `admin` / `geoserver`
- Other services in the stack (e.g. `long-tasks-worker`) can reach the GeoNode API directly at
  `http://django:8000`
- uwsgi request logs are written to `/var/log/geonode.log` inside the `geonode-django` container

Exporting survey-related records to GeoNode is configured with these settings (exporting is
disabled when the URL is not set):

- `SEIS_LAB_DATA__TARGET_GEONODE__URL` - URL where the backend reaches the GeoNode API
- `SEIS_LAB_DATA__TARGET_GEONODE__PUBLIC_URL` - URL where users reach GeoNode, only needed if it
  differs from the previous one, as happens in the dev stack
- `SEIS_LAB_DATA__TARGET_GEONODE__USERNAME` and `SEIS_LAB_DATA__TARGET_GEONODE__PASSWORD` -
  credentials of the GeoNode user which seis-lab-data acts as, which becomes the owner of the
  exported resources. This is meant to be a service account, used only by seis-lab-data
- `SEIS_LAB_DATA__TARGET_GEONODE__CLIENT_ID` and `SEIS_LAB_DATA__TARGET_GEONODE__CLIENT_SECRET` -
  credentials of a GeoNode OAuth2 application, which must be _confidential_ and use the
  _resource owner password-based_ grant type. Each export exchanges the service account's
  credentials for an access token with it, revoking the token when done
- `SEIS_LAB_DATA__PUBLIC_URL` - must also be set for the workers, as exported GeoNode resources
  link back to their record's page

Both the service account and the OAuth2 application are created in GeoNode, either in its Django administration
(_People_ > _Users_ and _Django OAuth Toolkit_ > _Applications_) or from the command line.

Exports run in the `exports` queue, consumed by the `long-tasks-worker` service. The dev stack already
sets all of these settings, using fixed credentials, the GeoNode counterparts of which can be
created with:

```shell
docker compose -f docker/compose.dev.yaml exec geonode-django python manage.py shell -c "
import os
from django.contrib.auth import get_user_model
from oauth2_provider.models import get_application_model

Application = get_application_model()
user, _ = get_user_model().objects.get_or_create(
    username=os.environ['SLD_BOT_USERNAME'])
user.set_password(os.environ['SLD_BOT_PASSWORD'])
user.save()
Application.objects.update_or_create(
    client_id=os.environ['SLD_OAUTH_APP_CLIENT_ID'],
    defaults=dict(
        name=os.environ['SLD_OAUTH_APP_NAME'],
        user=user,
        client_secret=os.environ['SLD_OAUTH_APP_CLIENT_SECRET'],
        client_type=Application.CLIENT_CONFIDENTIAL,
        authorization_grant_type=Application.GRANT_PASSWORD,
    ),
)
"
```

After which the services that use them need to be recreated:

```shell
docker compose -f docker/compose.dev.yaml --profile geonode up -d
```


## Running tests

Normal tests can be run from inside the `webapp` compose container, after installing the required dependencies:

```shell
docker compose --file docker/compose.dev.yaml exec -ti webapp uv sync --locked --group gdal --group dev
docker compose --file docker/compose.dev.yaml exec -ti webapp uv run pytest
```

Integration tests can be run with the following incantation:

```shell
docker compose --file docker/compose.dev.yaml exec webapp uv run pytest -m integration
```

### End to end tests

End to end tests are run from outside the docker stack. They require that [playwright] is installed locally.
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

### Test report

It is possible to generate a PDF report of the test results for the client, who is not expected to read the CI logs.
It contains a static introduction,
a summary of the results and then every test, grouped by test module, each described by its
docstring and shown with its result. The introduction is taken from the Markdown
file at `scripts/test-report/intro.md`, the layout is the Jinja template at `scripts/test-report/report.j2.html`.

Since the docstrings are the contents of the report, test modules and tests must have them, which ruff checks (rules
`D100` and `D103`, enforced only in `tests/**/test_*.py`). These are written for non-technical users, in formal English and without implementation terms:

- the first line of the module docstring is the title of its section in the report (a noun phrase, without a final
  period), followed by a blank line and a short description of the area of functionality the module covers
- the docstring of each test states the behaviour it verifies, e.g. _A published project can be deleted, and the
  notification of its deletion still shows its name._

The report is generated from the JSON files written by the [pytest-json-report] plugin, one per test suite. Run each suite with the plugin's options, then copy the files out of the `webapp` container:

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

The report is rendered outside the docker stack, because [WeasyPrint], which converts it to PDF, requires the Pango library (in Debian and Ubuntu, the `libpango-1.0-0` and `libpangoft2-1.0-0` packages), which the docker image does not have, as this is not needed at runtime.

Render it from the root of the repository, with the same version of the code that ran the tests,
as the descriptions are read from the test source files:

```shell
uv run --only-group report python scripts/render_test_report.py \
    --results unit.json integration.json e2e.json \
    --release v1.0.0 \
    --commit $(git rev-parse HEAD) \
    --output test-report.pdf
```

Run `uv run --only-group report python scripts/render_test_report.py --help` for the remaining options, e.g. `--html-output`, which keeps the intermediate HTML document, useful when modifying the template.

The CI workflow stores the JSON files of each run as the `test-results-json` artifact. For each
tag, it also renders the report and stores it as the `test-report-<tag>` artifact, which is
kept for 90 days and is generated even when tests fail, showing the failures.


[docker]: https://www.docker.com/
[playwright]: https://playwright.dev/python/
[pre-commit]: https://pre-commit.com/
[pytest-json-report]: https://pypi.org/project/pytest-json-report/
[uv]: https://docs.astral.sh/uv/
[WeasyPrint]: https://weasyprint.org/
