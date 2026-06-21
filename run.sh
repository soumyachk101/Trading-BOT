#!/bin/bash
# AlgoForge Terminal Bootstrapper
# Activates virtual environment and starts the paper trading loop on port 8080.

export PYTHONPATH=.

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
fi

echo "Starting AlgoForge Terminal..."
echo "Open http://localhost:8080/ in your browser once started."
echo "Press Ctrl+C to terminate."
echo "--------------------------------------------------------"

.venv/bin/python scripts/step4_paper_run.py
