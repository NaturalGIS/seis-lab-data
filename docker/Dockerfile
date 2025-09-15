FROM ghcr.io/osgeo/gdal:ubuntu-small-3.11.4
COPY --from=ghcr.io/astral-sh/uv:0.7.18 /uv /uvx /bin/

# Compile python stuff to bytecode to improve startup times
RUN python -c "import compileall; compileall.compile_path(maxlevels=10)"

RUN apt-get update \
  && apt-get install --yes --no-install-recommends \
    tini

USER ubuntu

# create relevant directories
RUN mkdir /home/ubuntu/app  && \
    mkdir /home/ubuntu/data && \
    mkdir --parents /home/ubuntu/.cache/uv

ARG GIT_COMMIT
ENV GIT_COMMIT=$GIT_COMMIT \
    PYTHONUNBUFFERED=1 \
    # This allows us to get traces whenever some C code segfaults
    PYTHONFAULTHANDLER=1 \
    UV_COMPILE_BYTECODE=1 \
    SEIS_LAB_DATA__BIND_HOST=0.0.0.0

# Write git commit identifier into the image
RUN echo $GIT_COMMIT > /home/ubuntu/git-commit.txt

WORKDIR /home/ubuntu/app

EXPOSE 5000

# Install dependencies
RUN --mount=type=cache,uid=1000,gid=1000,target=/home/ubuntu/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --compile-bytecode

# Copy project into the image
COPY --chown=ubuntu:ubuntu . .

# Sync the project
RUN --mount=type=cache,uid=1000,gid=1000,target=/home/ubuntu/.cache/uv \
    uv sync --locked --compile-bytecode

ENV UV_NO_SYNC=true \
    UV_LOCKED=true

# Compile translations
RUN uv run seis-lab-data translations compile

# use tini as the init process
ENTRYPOINT ["tini", "-g", "--", "uv", "run", "seis-lab-data"]

CMD ["run-web-server"]
