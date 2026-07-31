"""
check_cookie.py — standalone Roblox cookie validator.
Loads ROBLOX_SECURITY_COOKIE from .env automatically.
Run: python3 check_cookie.py
"""

import asyncio
import aiohttp
from dotenv import load_dotenv
import os

load_dotenv()


async def check():
    cookie = os.getenv("ROBLOX_SECURITY_COOKIE")

    if not cookie:
        print("[FAIL] ROBLOX_SECURITY_COOKIE is not set in .env")
        return

    print(f"[INFO] Cookie length: {len(cookie)}")

    async with aiohttp.ClientSession(cookies={".ROBLOSECURITY": cookie}) as session:
        async with session.get("https://users.roblox.com/v1/users/authenticated") as resp:
            body = await resp.text()
            print(f"[INFO] Status: {resp.status}")
            print(f"[INFO] Body: {body}")

            if resp.status == 200:
                print("[PASS] Cookie is VALID - authenticated successfully.")
            elif resp.status == 401:
                print("[FAIL] Cookie is INVALID or EXPIRED (401 Unauthorized).")
            else:
                print(f"[FAIL] Unexpected status {resp.status} - investigate body above.")


if __name__ == "__main__":
    asyncio.run(check())
