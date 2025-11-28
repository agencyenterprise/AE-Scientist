cd /workspace/AE-Scientist/research_pipeline/
uv venv --system-site-packages
source .venv/bin/activate
uv sync

apt-get update && apt-get install -y \
    texlive-latex-base texlive-latex-extra texlive-fonts-recommended \
    texlive-bibtex-extra biber poppler-utils chktex \
    bash-completion

# Enable git autocomplete
ln -sf /usr/share/bash-completion/completions/git /etc/bash_completion.d/git

# Ensure bash loads completion on login
grep -qxF 'if [ -f /etc/bash_completion ]; then . /etc/bash_completion; fi' ~/.bashrc \
    || echo 'if [ -f /etc/bash_completion ]; then . /etc/bash_completion; fi' >> ~/.bashrc
