#!/bin/bash
set -e
echo "🚀 Starting Master Extractor Bot..."

# Start Flask health-check in background
python app.py &
FLASK_PID=$!
echo "✅ Flask health-check started (PID: $FLASK_PID)"

# Start the bot
python main.py

# If bot exits, kill flask too
kill $FLASK_PID 2>/dev/null || true
