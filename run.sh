#!/bin/bash
set -e

if [ ! -d "venv" ]; then
  python3 -m venv venv
fi

source venv/bin/activate
pip install -q -r requirements.txt

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo ".env created from .env.example — fill in your values then re-run."
  exit 0
fi

export $(grep -v '^#' .env | xargs)

if [ ! -f "chores.db" ]; then
  python3 init_db.py
fi

python3 app.py
