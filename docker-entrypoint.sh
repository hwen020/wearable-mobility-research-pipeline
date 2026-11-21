#!/bin/sh
set -eu

if python -c 'import os, sys; sys.exit(os.getenv("DEMO_PUBLIC_READONLY", "").strip().lower() != "true")'; then
    demo_dir=$(mktemp -d)
    export DATABASE_URL="sqlite:///$demo_dir/mobility.db"
fi

python -m app.demo_seed
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1
