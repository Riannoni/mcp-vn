#!/usr/bin/env bash
set -euo pipefail
# Separate QA environment: production torch/SmolVLM/transformers are untouched.
ROOT="${HOME}/.local/share/mcp-vn"
BASE="${ROOT}/venv/lib/python3.14/site-packages"
DEST="${ROOT}/qa-shadow-venv"
test -d "${BASE}" || { echo "Expected existing CPU vision venv at ${BASE}" >&2; exit 2; }
python3 -m venv --system-site-packages "${DEST}"
SITE="${DEST}/lib/python3.14/site-packages"
# Reuse installed CPU torch without re-downloading or altering the production venv.
printf '%s\n' "${BASE}" > "${SITE}/mcp-vn-production-torch.pth"
"${DEST}/bin/python" -m pip install --disable-pip-version-check --no-input 'transformers==5.22.0'
"${DEST}/bin/python" -c 'import torch,transformers; from transformers import AutoModelForMultimodalLM; print("shadow ready",torch.__version__,transformers.__version__)'
