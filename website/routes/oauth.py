"""
website/routes/oauth.py
------------------------
Handles the Roblox OAuth2 authorization + callback flow.

/authorize?state=<state>   -> redirects the user to Roblox's consent screen
/callback?code=...&state=... -> exchanges the code for a token, fetches the
                                  Roblox profile, and writes the verification
                                  record directly into MongoDB (sync pymongo,
                                  since Flask here is synchronous).

The `state` value is created by the bot (cogs/verification.py) and stored
in the `oauth_states` collection so we know which Discord user is verifying,
and so the flow is protected against CSRF.
"""

import os
import time
import requests
from flask import Blueprint, request, redirect, render_template
from pymongo import MongoClient

oauth_bp = Blueprint("oauth", __name__)

ROBLOX_AUTHORIZE_URL = "https://apis.roblox.com/oauth/v1/authorize"
ROBLOX_TOKEN_URL = "https://apis.roblox.com/oauth/v1/token"
ROBLOX_USERINFO_URL = "https://apis.roblox.com/oauth/v1/userinfo"

CLIENT_ID = os.getenv("ROBLOX_CLIENT_ID")
CLIENT_SECRET = os.getenv("ROBLOX_CLIENT_SECRET")
REDIRECT_URI = os.getenv("ROBLOX_REDIRECT_URI")

_client = MongoClient(os.getenv("MONGODB_URI"))
_db = _client[os.getenv("MONGODB_DB_NAME", "royalguard")]


@oauth_bp.route("/authorize")
def authorize():
    state = request.args.get("state")
    if not state:
        return "Missing state parameter.", 400

    # Confirm this state was actually issued by the bot
    record = _db["oauth_states"].find_one({"state": state})
    if not record:
        return render_template("error.html", message="This verification link is invalid or has expired. Please request a new one in Discord."), 400

    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": "openid profile",
        "response_type": "code",
        "state": state,
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return redirect(f"{ROBLOX_AUTHORIZE_URL}?{query}")


@oauth_bp.route("/callback")
def callback():
    code = request.args.get("code")
    state = request.args.get("state")

    if not code or not state:
        return render_template("error.html", message="Missing code or state in callback."), 400

    record = _db["oauth_states"].find_one({"state": state})
    if not record:
        return render_template("error.html", message="This verification link has expired. Please try again."), 400

    discord_id = record["discord_id"]

    # Exchange the authorization code for an access token
    token_resp = requests.post(ROBLOX_TOKEN_URL, data={
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    })

    if token_resp.status_code != 200:
        return render_template("error.html", message="Failed to exchange authorization code with Roblox."), 400

    access_token = token_resp.json().get("access_token")

    # Fetch the Roblox profile
    userinfo_resp = requests.get(
        ROBLOX_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}
    )
    if userinfo_resp.status_code != 200:
        return render_template("error.html", message="Failed to fetch your Roblox profile."), 400

    profile = userinfo_resp.json()
    roblox_id = profile.get("sub")
    roblox_username = profile.get("preferred_username") or profile.get("nickname")

    # Store the verification record
    _db["verifications"].update_one(
        {"discord_id": discord_id},
        {"$set": {
            "discord_id": discord_id,
            "roblox_id": str(roblox_id),
            "roblox_username": roblox_username,
            "verified_at": time.time(),
        }},
        upsert=True,
    )

    # Clean up the used state
    _db["oauth_states"].delete_one({"state": state})

    return render_template("success.html", roblox_username=roblox_username)