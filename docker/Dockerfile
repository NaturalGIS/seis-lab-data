FROM python:3.13
COPY --from=ghcr.io/astral-sh/uv:0.7.18 /uv /uvx /bin/

# Compile python stuff to bytecode to improve startup times
RUN python -c "import compileall; compileall.compile_path(maxlevels=10)"

RUN apt-get update \
  && apt-get install --yes --no-install-recommends \
    tini

# Create a normal non-root user so that we can use it to run
RUN useradd --create-home appuser

USER appuser

# create relevant directories
RUN mkdir /home/appuser/app  && \
    mkdir /home/appuser/data && \
    mkdir --parents /home/appuser/.cache/uv

ARG GIT_COMMIT
ENV GIT_COMMIT=$GIT_COMMIT \
    PYTHONUNBUFFERED=1 \
    # This allows us to get traces whenever some C code segfaults
    PYTHONFAULTHANDLER=1 \
    UV_COMPILE_BYTECODE=1 \
    SEIS_LAB_DATA__BIND_HOST=0.0.0.0

# Write git commit identifier into the image
RUN echo $GIT_COMMIT > /home/appuser/git-commit.txt

WORKDIR /home/appuser/app

EXPOSE 5000

# Install dependencies
RUN --mount=type=cache,uid=1000,gid=1000,target=/home/appuser/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

# Copy the project into the image
COPY --chown=appuser:appuser . .

# Sync the project
RUN --mount=type=cache,uid=1000,gid=1000,target=/home/appuser/.cache/uv \
    uv sync --locked

# use tini as the init process
ENTRYPOINT ["tini", "-g", "--", "uv", "run", "seis-lab-data"]

CMD ["run-web-server"]
