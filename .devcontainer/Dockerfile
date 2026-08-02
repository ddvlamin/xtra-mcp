# See here for image contents: https://github.com/microsoft/vscode-dev-containers/tree/v0.245.2/containers/python-3
FROM mcr.microsoft.com/devcontainers/python:3.14

# Create a non-root user to use if preferred - see https://aka.ms/vscode-remote/containers/non-root-user.
USER root

# Install uv system-wide
RUN curl -LsSf https://astral.sh/uv/install.sh | UV_INSTALL_DIR=/usr/local/bin sh

# Set workspace
WORKDIR /workspace

# [Optional] Add sudo support for the non-root user
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends npm libsecret-1-0 sudo stow \
    && echo "vscode ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/vscode

RUN npm install -g npm@latest && \
    npm install -g @modelcontextprotocol/server-filesystem @modelcontextprotocol/server-github @modelcontextprotocol/server-sequential-thinking

RUN chown -R vscode:vscode /workspace

# [Optional] Set the default user. Omit if you want to connect as root.
USER vscode

# Copy project source code
COPY . .

RUN uvx --from omega-memory omega setup --download-model

RUN uv tool install git+https://github.com/sydasif/web-search-mcp.git

RUN curl -fsSL https://antigravity.google/cli/install.sh | sh
RUN curl -fsSL https://opencode.ai/install | bash

# Stow AI dotfiles
RUN cd .ai-dotfiles && stow -v -t ~ gemini claude codex vibe
RUN mkdir -p ~/.config/opencode/skills && cd .ai-dotfiles && stow -v -t ~/.config/opencode opencode
RUN stow -v -t ~/.config/opencode/skills --no-folding .skills
RUN mkdir -p ~/.agents/skills && stow -v -t ~/.agents/skills --no-folding .skills

# Preserve git config and ensure uv is in PATH for bash
RUN echo 'git config --global user.email "ddvlamin@gmail.com"' >> ~/.bashrc && \
    echo 'git config --global user.name "Dieter Devlaminck"' >> ~/.bashrc

#ENV PATH="/home/vscode/.opencode/bin:${PATH}"
ENV NO_BROWSER=true


