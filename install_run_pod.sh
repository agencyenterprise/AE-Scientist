uv venv --system-site-packages
source .venv/bin/activate
uv sync
apt-get update && apt-get install -y texlive-latex-base texlive-latex-extra texlive-fonts-recommended texlive-bibtex-extra biber poppler-utils chktex