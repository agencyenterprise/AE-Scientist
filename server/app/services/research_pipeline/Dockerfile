FROM runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404

WORKDIR /workspace/AE-Scientist

# Pre-install LaTeX / PDF tooling so pods skip long apt installs
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
        texlive-latex-base \
        texlive-latex-extra \
        texlive-fonts-recommended \
        texlive-bibtex-extra \
        biber \
        poppler-utils \
        chktex \
        bash-completion \
        wget && \
    apt-get clean && rm -rf /var/lib/apt/lists/* && \
    ln -sf /usr/share/bash-completion/completions/git /etc/bash_completion.d/git && \
    grep -qxF 'if [ -f /etc/bash_completion ]; then . /etc/bash_completion; fi' ~/.bashrc || \
        echo 'if [ -f /etc/bash_completion ]; then . /etc/bash_completion; fi' >> ~/.bashrc

# Install yq (required for config scrubbing in runpod_manager.py)
ARG YQ_VERSION=v4.2.0
ARG TARGETPLATFORM
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "x86_64" ]; then PLATFORM="linux_amd64"; \
    elif [ "$ARCH" = "aarch64" ]; then PLATFORM="linux_arm64"; \
    else PLATFORM="linux_amd64"; fi && \
    wget -q https://github.com/mikefarah/yq/releases/download/${YQ_VERSION}/yq_${PLATFORM} -O /usr/local/bin/yq && \
    chmod +x /usr/local/bin/yq && \
    yq --version

