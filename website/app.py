"""
website/app.py
---------------
Flask backend that hosts the Roblox OAuth2 verification flow. Deployed
as a separate Railway service (or the "web" process type) alongside the
bot's "worker" process. Both share the same MongoDB Atlas cluster, so
verification data written here is instantly visible to the bot.
"""

import os
from flask import Flask
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, template_folder="templates")
app.secret_key = os.getenv("WEBSITE_SECRET_KEY", "dev-secret-change-me")

from website.routes.oauth import oauth_bp
app.register_blueprint(oauth_bp)


@app.route("/")
def index():
    return {"status": "ok", "service": "Royal Guard OAuth Website"}


@app.route("/health")
def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    port = int(os.getenv("WEBSITE_PORT", 8080))
    app.run(host="0.0.0.0", port=port)