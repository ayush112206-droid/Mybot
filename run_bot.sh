#!/bin/bash
cd "/mnt/c/Users/natra/Desktop/online courses/Without-ID-Pass-Test-main"
find . -name __pycache__ -type d -not -path './venv/*' -exec rm -rf {} + 2>/dev/null
echo "Cleared __pycache__"
echo "Starting bot..."
python3 main.py
