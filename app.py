"""
Flask health-check server.
Required by Heroku (web dyno) and Render/Railway to confirm the process is alive.
"""
import os
from flask import Flask

app = Flask(__name__)

@app.route("/")
def index():
    return "✅ Master Extractor Bot is running!", 200

@app.route("/health")
def health():
    return {"status": "ok"}, 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
