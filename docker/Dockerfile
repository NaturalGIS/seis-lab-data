# Multi-stage Dockerfile for Seis Lab Data application with GDAL Python bindings

# Build stage - includes build dependencies for GDAL Python bindings
FROM ghcr.io/osgeo/gdal:ubuntu-small-3.11.4 AS builder

COPY --from=ghcr.io/astral-sh/uv:0.7.18 /uv /uvx /bin/

# Install build dependencies needed for GDAL Python bindings compilation
RUN apt-get update \
  && apt-get install --yes --no-install-recommends \
    build-essential \
    python3-dev \
  && rm -rf /var/lib/apt/lists/*

USER ubuntu
RUN mkdir /home/ubuntu/app && \
    mkdir --parents /home/ubuntu/.cache/uv

WORKDIR /home/ubuntu/app

ARG GIT_COMMIT
ENV GIT_COMMIT=$GIT_COMMIT \
    UV_COMPILE_BYTECODE=1

RUN --mount=type=cache,uid=1000,gid=1000,target=/home/ubuntu/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --group gdal --no-install-project --compile-bytecode

COPY --chown=ubuntu:ubuntu . .

# Sync the project
RUN --mount=type=cache,uid=1000,gid=1000,target=/home/ubuntu/.cache/uv \
    uv sync --locked --group gdal --compile-bytecode

RUN uv run seis-lab-data translations compile

# Runtime stage - clean GDAL base without build tools
FROM ghcr.io/osgeo/gdal:ubuntu-small-3.11.4

COPY --from=ghcr.io/astral-sh/uv:0.7.18 /uv /uvx /bin/

RUN python -c "import compileall; compileall.compile_path(maxlevels=10)"

# Install only tini - no build dependencies needed
RUN apt-get update \
  && apt-get install --yes --no-install-recommends \
    tini \
  && rm -rf /var/lib/apt/lists/*

USER ubuntu

RUN mkdir /home/ubuntu/app && \
    mkdir /home/ubuntu/data

ARG GIT_COMMIT
ENV GIT_COMMIT=$GIT_COMMIT \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    UV_COMPILE_BYTECODE=1 \
    SEIS_LAB_DATA__BIND_HOST=0.0.0.0 \
    UV_NO_SYNC=true \
    UV_LOCKED=true

RUN echo $GIT_COMMIT > /home/ubuntu/git-commit.txt

WORKDIR /home/ubuntu/app

EXPOSE 5000

# Copy the entire built environment from builder stage
COPY --from=builder --chown=ubuntu:ubuntu /home/ubuntu/app .

ENTRYPOINT ["tini", "-g", "--", "uv", "run", "seis-lab-data"]

CMD ["run-web-server"]
