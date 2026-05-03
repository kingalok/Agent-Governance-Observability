#!/usr/bin/env bash

set -euo pipefail

cd "$(dirname "$0")/../backend"
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
echo "Backend bootstrap complete."
