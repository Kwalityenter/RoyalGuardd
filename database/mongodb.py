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

        self.verifications = self.db["verifications"]
        self.admin_levels = self.db["admin_levels"]
        self.groupbinds = self.db["groupbinds"]
        self.rankbinds = self.db["rankbinds"]
        self.ticket_config = self.db["ticket_config"]
        self.tickets = self.db["tickets"]
        self.guild_config = self.db["guild_config"]
        self.oauth_states = self.db["oauth_states"]
        self.rank_requests = self.db["rank_requests"]
        self.reaction_roles = self.db["reaction_roles"]
        self.invites = self.db["invites"]
        self.invite_credits = self.db["invite_credits"]

    async def ensure_indexes(self):
        """Create indexes needed for fast lookups. Call once on startup."""
        await self.verifications.create_index("discord_id", unique=True)
        await self.verifications.create_index("roblox_id")
        await self.admin_levels.create_index([("guild_id", 1), ("discord_id", 1)], unique=True)
        await self.groupbinds.create_index("guild_id")
        await self.rankbinds.create_index("guild_id")
        await self.ticket_config.create_index("guild_id", unique=True)
        await self.tickets.create_index("channel_id", unique=True)
        await self.guild_config.create_index("guild_id", unique=True)
        await self.oauth_states.create_index("state", unique=True)
        await self.oauth_states.create_index("created_at", expireAfterSeconds=600)
        await self.rank_requests.create_index("status")
        await self.reaction_roles.create_index("message_id")
        await self.invites.create_index([("guild_id", 1), ("code", 1)], unique=True)
        await self.invite_credits.create_index([("guild_id", 1), ("inviter_id", 1)], unique=True)

    # ============================================================
    # VERIFICATION
    # (Kept global/per-Discord-user, not per-guild - a person's linked
    # Roblox account is the same regardless of which server they're in.)
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
    # ADMIN LEVELS (now per-guild - a level in one server no longer
    # carries over into another server the bot is installed in)
    # ============================================================
    async def get_admin_level(self, guild_id: int, discord_id: int) -> int:
        doc = await self.admin_levels.find_one({"guild_id": str(guild_id), "discord_id": str(discord_id)})
        return doc["level"] if doc else 0

    async def set_admin_level(self, guild_id: int, discord_id: int, level: int):
        await self.admin_levels.update_one(
            {"guild_id": str(guild_id), "discord_id": str(discord_id)},
            {"$set": {"guild_id": str(guild_id), "discord_id": str(discord_id), "level": level}},
            upsert=True,
        )

    async def remove_admin_level(self, guild_id: int, discord_id: int):
        await self.admin_levels.delete_one({"guild_id": str(guild_id), "discord_id": str(discord_id)})

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
        await self.rankbinds.delete_many({"guild_id": str(guild_id), "group_id": str(group_id)})

    async def list_groupbinds(self, guild_id: int):
        cursor = self.groupbinds.find({"guild_id": str(guild_id)})
        return [doc async for doc in cursor]

    # ============================================================
    # RANKBINDS (multiple Discord roles can be bound to the same rank)
    # ============================================================
    async def add_rankbind(self, guild_id: int, group_id: int, rank_id: int, role_id: int, rank_name: str = "", nickname_prefix: str = ""):
        await self.rankbinds.update_one(
            {"guild_id": str(guild_id), "group_id": str(group_id), "rank_id": rank_id, "role_id": str(role_id)},
            {"$set": {
                "guild_id": str(guild_id),
                "group_id": str(group_id),
                "rank_id": rank_id,
                "role_id": str(role_id),
                "rank_name": rank_name,
                "nickname_prefix": nickname_prefix,
            }},
            upsert=True,
        )

    async def remove_rankbind(self, guild_id: int, group_id: int, rank_id: int, role_id: int = None):
        query = {"guild_id": str(guild_id), "group_id": str(group_id), "rank_id": rank_id}
        if role_id is not None:
            query["role_id"] = str(role_id)
            await self.rankbinds.delete_one(query)
        else:
            await self.rankbinds.delete_many(query)

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
    # LOG CHANNELS
    # ============================================================
    async def get_log_channel(self, guild_id: int, log_type: str):
        config = await self.get_guild_config(guild_id)
        return config.get(f"{log_type}_log_channel_id")

    async def set_log_channel(self, guild_id: int, log_type: str, channel_id: int):
        await self.set_guild_config(guild_id, **{f"{log_type}_log_channel_id": str(channel_id)})

    # ============================================================
    # OAUTH STATE
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

    # ============================================================
    # RANK REQUESTS
    # ============================================================
    async def create_rank_request(self, guild_id: int, requester_id: int, group_id: int,
                                    rank_id: int, rank_name: str, group_name: str):
        from bson import ObjectId
        request_id = str(ObjectId())
        doc = {
            "_id": request_id,
            "guild_id": str(guild_id),
            "requester_id": str(requester_id),
            "group_id": str(group_id),
            "group_name": group_name,
            "rank_id": rank_id,
            "rank_name": rank_name,
            "status": "pending",
            "created_at": time.time(),
        }
        await self.rank_requests.insert_one(doc)
        return doc

    async def get_rank_request(self, request_id: str):
        return await self.rank_requests.find_one({"_id": request_id})

    async def update_rank_request_status(self, request_id: str, status: str, resolved_by: int = None):
        update = {"status": status, "resolved_at": time.time()}
        if resolved_by:
            update["resolved_by"] = str(resolved_by)
        await self.rank_requests.update_one({"_id": request_id}, {"$set": update})

    async def get_pending_rank_requests(self):
        cursor = self.rank_requests.find({"status": "pending"})
        return [doc async for doc in cursor]

    async def get_rank_request_config(self, guild_id: int):
        config = await self.get_guild_config(guild_id)
        return {
            "approver_role_id": config.get("rankrequest_approver_role_id"),
            "requests_channel_id": config.get("rankrequest_channel_id"),
        }

    async def set_rank_request_config(self, guild_id: int, approver_role_id: int = None, requests_channel_id: int = None):
        update = {}
        if approver_role_id is not None:
            update["rankrequest_approver_role_id"] = str(approver_role_id)
        if requests_channel_id is not None:
            update["rankrequest_channel_id"] = str(requests_channel_id)
        await self.set_guild_config(guild_id, **update)

    # ============================================================
    # REACTION ROLES
    # ============================================================
    async def add_reaction_role(self, guild_id: int, channel_id: int, message_id: int, emoji: str, role_id: int):
        await self.reaction_roles.update_one(
            {"guild_id": str(guild_id), "message_id": str(message_id), "emoji": emoji},
            {"$set": {
                "guild_id": str(guild_id),
                "channel_id": str(channel_id),
                "message_id": str(message_id),
                "emoji": emoji,
                "role_id": str(role_id),
            }},
            upsert=True,
        )

    async def remove_reaction_role(self, message_id: int, emoji: str):
        await self.reaction_roles.delete_one({"message_id": str(message_id), "emoji": emoji})

    async def get_reaction_role(self, message_id: int, emoji: str):
        return await self.reaction_roles.find_one({"message_id": str(message_id), "emoji": emoji})

    async def list_reaction_roles(self, message_id: int):
        cursor = self.reaction_roles.find({"message_id": str(message_id)})
        return [doc async for doc in cursor]

    async def get_all_reaction_role_message_ids(self):
        cursor = self.reaction_roles.find({})
        seen = set()
        async for doc in cursor:
            seen.add(doc["message_id"])
        return list(seen)

    # ============================================================
    # INVITE TRACKING
    # ============================================================
    async def snapshot_invites(self, guild_id: int, invite_data: list):
        for inv in invite_data:
            await self.invites.update_one(
                {"guild_id": str(guild_id), "code": inv["code"]},
                {"$set": {
                    "guild_id": str(guild_id),
                    "code": inv["code"],
                    "uses": inv["uses"],
                    "inviter_id": inv["inviter_id"],
                }},
                upsert=True,
            )

    async def get_invite_snapshot(self, guild_id: int, code: str):
        return await self.invites.find_one({"guild_id": str(guild_id), "code": code})

    async def get_all_invite_snapshots(self, guild_id: int):
        cursor = self.invites.find({"guild_id": str(guild_id)})
        return {doc["code"]: doc async for doc in cursor}

    async def add_invite_credit(self, guild_id: int, inviter_id: int, amount: int = 1):
        await self.invite_credits.update_one(
            {"guild_id": str(guild_id), "inviter_id": str(inviter_id)},
            {"$inc": {"count": amount}, "$set": {"guild_id": str(guild_id), "inviter_id": str(inviter_id)}},
            upsert=True,
        )

    async def get_invite_credit(self, guild_id: int, inviter_id: int) -> int:
        doc = await self.invite_credits.find_one({"guild_id": str(guild_id), "inviter_id": str(inviter_id)})
        return doc["count"] if doc else 0

    async def get_invite_leaderboard(self, guild_id: int, limit: int = 10):
        cursor = self.invite_credits.find({"guild_id": str(guild_id)}).sort("count", -1).limit(limit)
        return [doc async for doc in cursor]


# Global singleton, initialized in main.py
db = Database()