# See here for image contents: https://github.com/microsoft/vscode-dev-containers/tree/v0.245.2/containers/python-3
FROM mcr.microsoft.com/devcontainers/python:3.12

# Install uv system-wide
RUN curl -LsSf https://astral.sh/uv/install.sh | UV_INSTALL_DIR=/usr/local/bin sh

# Set workspace
WORKDIR /workspace

# Copy project source code
COPY . .

# Install project dependencies
RUN uv sync --frozen

RUN uvx --from omega-memory omega setup --download-model

RUN uv tool install git+https://github.com/sydasif/web-search-mcp.git

# Create a non-root user to use if preferred - see https://aka.ms/vscode-remote/containers/non-root-user.
USER root

# [Optional] Add sudo support for the non-root user
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends npm libsecret-1-0 sudo \
    && npm install -g @google/gemini-cli \
    && echo "vscode ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/vscode

RUN npm install -g @modelcontextprotocol/server-filesystem

# Preserve git config and ensure uv is in PATH for bash
RUN echo 'git config --global user.email "ddvlamin@gmail.com"' >> /root/.bashrc && \
    echo 'git config --global user.name "Dieter Devlaminck"' >> /root/.bashrc

ENV NO_BROWSER=true