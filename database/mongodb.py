"""
database/mongodb.py
--------------------
Async MongoDB Atlas connection layer using Motor.
All collections used by the bot are defined and exposed here so cogs
never touch pymongo/motor directly - they just call Database methods.
"""

import os
import time
from motor.motor_asyncio import AsyncIOMotorClient


class Database:
    """Thin async wrapper around all Royal Guard MongoDB collections."""

    def __init__(self):
        uri = os.getenv("MONGODB_URI")
        db_name = os.getenv("MONGODB_DB_NAME", "royalguard")

        if not uri:
            raise RuntimeError("MONGODB_URI is not set in the environment (.env)")

        self.client = AsyncIOMotorClient(uri)
        self.db = self.client[db_name]

        # Collections
        self.verifications = self.db["verifications"]      # discord_id -> roblox link
        self.admin_levels = self.db["admin_levels"]         # discord_id -> level
        self.groupbinds = self.db["groupbinds"]             # guild_id -> [group configs]
        self.rankbinds = self.db["rankbinds"]                # guild_id -> [rankbind configs]
        self.ticket_config = self.db["ticket_config"]        # guild_id -> ticket settings
        self.tickets = self.db["tickets"]                    # channel_id -> ticket data
        self.guild_config = self.db["guild_config"]           # guild_id -> misc settings
        self.oauth_states = self.db["oauth_states"]            # state -> discord_id (CSRF-safe OAuth)

    async def ensure_indexes(self):
        """Create indexes needed for fast lookups. Call once on startup."""
        await self.verifications.create_index("discord_id", unique=True)
        await self.verifications.create_index("roblox_id")
        await self.admin_levels.create_index("discord_id", unique=True)
        await self.groupbinds.create_index("guild_id")
        await self.rankbinds.create_index("guild_id")
        await self.ticket_config.create_index("guild_id", unique=True)
        await self.tickets.create_index("channel_id", unique=True)
        await self.guild_config.create_index("guild_id", unique=True)
        await self.oauth_states.create_index("state", unique=True)
        await self.oauth_states.create_index("created_at", expireAfterSeconds=600)  # auto-expire after 10 min

    # ============================================================
    # VERIFICATION
    # ============================================================
    async def get_verification(self, discord_id: int):
        return await self.verifications.find_one({"discord_id": str(discord_id)})

    async def get_verification_by_roblox(self, roblox_id: int):
        return await self.verifications.find_one({"roblox_id": str(roblox_id)})

    async def set_verification(self, discord_id: int, roblox_id: int, roblox_username: str):
        doc = {
            "discord_id": str(discord_id),
            "roblox_id": str(roblox_id),
            "roblox_username": roblox_username,
            "verified_at": time.time(),
        }
        await self.verifications.update_one(
            {"discord_id": str(discord_id)},
            {"$set": doc},
            upsert=True,
        )
        return doc

    async def remove_verification(self, discord_id: int):
        await self.verifications.delete_one({"discord_id": str(discord_id)})

    # ============================================================
    # ADMIN LEVELS
    # ============================================================
    async def get_admin_level(self, discord_id: int) -> int:
        doc = await self.admin_levels.find_one({"discord_id": str(discord_id)})
        return doc["level"] if doc else 0

    async def set_admin_level(self, discord_id: int, level: int):
        await self.admin_levels.update_one(
            {"discord_id": str(discord_id)},
            {"$set": {"discord_id": str(discord_id), "level": level}},
            upsert=True,
        )

    async def remove_admin_level(self, discord_id: int):
        await self.admin_levels.delete_one({"discord_id": str(discord_id)})

    # ============================================================
    # GROUPBINDS
    # ============================================================
    async def add_groupbind(self, guild_id: int, group_id: int, group_name: str):
        await self.groupbinds.update_one(
            {"guild_id": str(guild_id), "group_id": str(group_id)},
            {"$set": {
                "guild_id": str(guild_id),
                "group_id": str(group_id),
                "group_name": group_name,
            }},
            upsert=True,
        )

    async def remove_groupbind(self, guild_id: int, group_id: int):
        await self.groupbinds.delete_one({"guild_id": str(guild_id), "group_id": str(group_id)})
        # Also clean up rankbinds tied to this group
        await self.rankbinds.delete_many({"guild_id": str(guild_id), "group_id": str(group_id)})

    async def list_groupbinds(self, guild_id: int):
        cursor = self.groupbinds.find({"guild_id": str(guild_id)})
        return [doc async for doc in cursor]

    # ============================================================
    # RANKBINDS
    # ============================================================
    async def add_rankbind(self, guild_id: int, group_id: int, rank_id: int, role_id: int, rank_name: str = ""):
        await self.rankbinds.update_one(
            {"guild_id": str(guild_id), "group_id": str(group_id), "rank_id": rank_id},
            {"$set": {
                "guild_id": str(guild_id),
                "group_id": str(group_id),
                "rank_id": rank_id,
                "role_id": str(role_id),
                "rank_name": rank_name,
            }},
            upsert=True,
        )

    async def remove_rankbind(self, guild_id: int, group_id: int, rank_id: int):
        await self.rankbinds.delete_one(
            {"guild_id": str(guild_id), "group_id": str(group_id), "rank_id": rank_id}
        )

    async def list_rankbinds(self, guild_id: int, group_id: int = None):
        query = {"guild_id": str(guild_id)}
        if group_id is not None:
            query["group_id"] = str(group_id)
        cursor = self.rankbinds.find(query)
        return [doc async for doc in cursor]

    # ============================================================
    # TICKET CONFIG / TICKETS
    # ============================================================
    async def get_ticket_config(self, guild_id: int):
        return await self.ticket_config.find_one({"guild_id": str(guild_id)})

    async def set_ticket_config(self, guild_id: int, **kwargs):
        kwargs["guild_id"] = str(guild_id)
        await self.ticket_config.update_one(
            {"guild_id": str(guild_id)},
            {"$set": kwargs},
            upsert=True,
        )

    async def create_ticket(self, channel_id: int, guild_id: int, owner_id: int, category: str):
        doc = {
            "channel_id": str(channel_id),
            "guild_id": str(guild_id),
            "owner_id": str(owner_id),
            "category": category,
            "created_at": time.time(),
            "closed": False,
        }
        await self.tickets.insert_one(doc)
        return doc

    async def close_ticket(self, channel_id: int):
        await self.tickets.update_one(
            {"channel_id": str(channel_id)},
            {"$set": {"closed": True, "closed_at": time.time()}},
        )

    async def get_ticket(self, channel_id: int):
        return await self.tickets.find_one({"channel_id": str(channel_id)})

    # ============================================================
    # GUILD CONFIG (generic key/value settings per guild)
    # ============================================================
    async def get_guild_config(self, guild_id: int):
        return await self.guild_config.find_one({"guild_id": str(guild_id)}) or {}

    async def set_guild_config(self, guild_id: int, **kwargs):
        kwargs["guild_id"] = str(guild_id)
        await self.guild_config.update_one(
            {"guild_id": str(guild_id)},
            {"$set": kwargs},
            upsert=True,
        )

    # ============================================================
    # OAUTH STATE (CSRF protection for the verification flow)
    # ============================================================
    async def create_oauth_state(self, state: str, discord_id: int):
        await self.oauth_states.insert_one({
            "state": state,
            "discord_id": str(discord_id),
            "created_at": time.time(),
        })

    async def consume_oauth_state(self, state: str):
        doc = await self.oauth_states.find_one({"state": state})
        if doc:
            await self.oauth_states.delete_one({"state": state})
        return doc


# Global singleton, initialized in main.py
db = Database()