"""
utils/roblox.py
----------------
Thin async wrapper around Roblox's public (unauthenticated) APIs used
for bgcheck, rank syncing, and group lookups. Uses aiohttp so it plays
nicely inside the discord.py event loop.

Note: Ranking members in-game requires an authenticated group-management
API call using a service account's ROBLOSECURITY cookie + X-CSRF-TOKEN,
handled in `set_group_rank`.
"""

import os
import aiohttp

USERS_API = "https://users.roblox.com/v1"
GROUPS_API = "https://groups.roblox.com/v1"
GROUPS_API_V2 = "https://groups.roblox.com/v2"
THUMBNAILS_API = "https://thumbnails.roblox.com/v1"
FRIENDS_API = "https://friends.roblox.com/v1"
PREMIUM_API = "https://premiumfeatures.roblox.com/v1"


async def _get_json(session: aiohttp.ClientSession, url: str, **kwargs):
    async with session.get(url, **kwargs) as resp:
        if resp.status != 200:
            return None
        return await resp.json()


async def get_user_by_id(roblox_id: int):
    async with aiohttp.ClientSession() as session:
        return await _get_json(session, f"{USERS_API}/users/{roblox_id}")


async def get_user_by_username(username: str):
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{USERS_API}/usernames/users",
            json={"usernames": [username], "excludeBannedUsers": False},
        ) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            results = data.get("data", [])
            return results[0] if results else None


async def get_avatar_headshot_url(roblox_id: int, size: str = "420x420"):
    async with aiohttp.ClientSession() as session:
        data = await _get_json(
            session,
            f"{THUMBNAILS_API}/users/avatar-headshot",
            params={"userIds": roblox_id, "size": size, "format": "png", "isCircular": "false"},
        )
        if data and data.get("data"):
            return data["data"][0].get("imageUrl")
        return None


async def get_friends_count(roblox_id: int):
    async with aiohttp.ClientSession() as session:
        data = await _get_json(session, f"{FRIENDS_API}/users/{roblox_id}/friends/count")
        return data.get("count", 0) if data else 0


async def get_followers_count(roblox_id: int):
    async with aiohttp.ClientSession() as session:
        data = await _get_json(session, f"{FRIENDS_API}/users/{roblox_id}/followers/count")
        return data.get("count", 0) if data else 0


async def get_following_count(roblox_id: int):
    async with aiohttp.ClientSession() as session:
        data = await _get_json(session, f"{FRIENDS_API}/users/{roblox_id}/followings/count")
        return data.get("count", 0) if data else 0


async def get_premium_status(roblox_id: int):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{PREMIUM_API}/users/{roblox_id}/validate-membership") as resp:
            if resp.status != 200:
                return False
            try:
                return bool(await resp.json())
            except Exception:
                return False


async def get_user_groups(roblox_id: int):
    """Returns list of {group: {...}, role: {...}} for every group the user is in."""
    async with aiohttp.ClientSession() as session:
        data = await _get_json(session, f"{GROUPS_API}/users/{roblox_id}/groups/roles")
        return data.get("data", []) if data else []


async def get_group_info(group_id: int):
    async with aiohttp.ClientSession() as session:
        return await _get_json(session, f"{GROUPS_API}/groups/{group_id}")


async def get_group_roles(group_id: int):
    async with aiohttp.ClientSession() as session:
        data = await _get_json(session, f"{GROUPS_API}/groups/{group_id}/roles")
        return data.get("roles", []) if data else []


async def get_user_rank_in_group(roblox_id: int, group_id: int):
    """Returns (rank_id, rank_name) for a user in a specific group, or (0, 'Guest')."""
    groups = await get_user_groups(roblox_id)
    for entry in groups:
        if str(entry["group"]["id"]) == str(group_id):
            return entry["role"]["rank"], entry["role"]["name"]
    return 0, "Guest"


# ============================================================
# AUTHENTICATED GROUP RANKING (service account required)
# ============================================================
async def set_group_rank(group_id: int, roblox_user_id: int, role_id: int):
    """Sets a member's rank in a group using the service account cookie.

    Requires ROBLOX_SECURITY_COOKIE in the environment. Roblox requires a
    fresh X-CSRF-TOKEN per request, obtained from a 403 response header.
    """
    cookie = os.getenv("ROBLOX_SECURITY_COOKIE")
    if not cookie:
        raise RuntimeError("ROBLOX_SECURITY_COOKIE not configured - cannot rank users.")

    cookies = {".ROBLOSECURITY": cookie}
    url = f"{GROUPS_API}/groups/{group_id}/users/{roblox_user_id}"

    async with aiohttp.ClientSession(cookies=cookies) as session:
        # Step 1: trigger a 403 to obtain a valid CSRF token
        async with session.patch(url, json={"roleId": role_id}) as resp:
            if resp.status == 403:
                csrf_token = resp.headers.get("x-csrf-token")
            else:
                return resp.status == 200

        # Step 2: retry with the CSRF token attached
        headers = {"x-csrf-token": csrf_token} if csrf_token else {}
        async with session.patch(url, json={"roleId": role_id}, headers=headers) as resp:
            return resp.status == 200