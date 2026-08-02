"""tenant_manager.py — Runs one discord.py bot instance per tenant, concurrently."""

import asyncio
import logging
import discord
from discord.ext import commands

from database.mongodb import db
from utils.token_crypto import decrypt_token

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] TenantManager: %(message)s")
log = logging.getLogger("tenant_manager")

TENANT_COGS = [
    "cogs.adminlevels",
    "cogs.groupbinds",
    "cogs.rankbinds",
    "cogs.update",
    "cogs.verification",
    "cogs.tickets",
    "cogs.bgcheck",
    "cogs.moderation",
    "cogs.setrank",
    "cogs.reactionroles",
    "cogs.invites",
    "cogs.automod",
    "cogs.antinuke",
]


class TenantRuntime:
    def __init__(self, tenant_id: str, owner_discord_id: int, token: str):
        self.tenant_id = tenant_id
        self.owner_discord_id = owner_discord_id
        self.token = token
        self.bot = None
        self.task = None
        self.status = "starting"
        self.last_error = None

    async def start(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        self.bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

        @self.bot.event
        async def on_ready():
            log.info(f"Tenant {self.tenant_id} ({self.bot.user}) is online in {len(self.bot.guilds)} server(s).")
            await db.set_tenant_status(self.tenant_id, "active")

        for cog in TENANT_COGS:
            try:
                await self.bot.load_extension(cog)
            except Exception as e:
                log.error(f"Tenant {self.tenant_id}: failed to load {cog}: {e}")

        try:
            await self.bot.start(self.token)
        except discord.LoginFailure:
            self.status = "error"
            self.last_error = "Invalid token"
            log.error(f"Tenant {self.tenant_id}: invalid token, marking errored.")
            await db.set_tenant_status(self.tenant_id, "error", last_error="Invalid token")
        except Exception as e:
            self.status = "error"
            self.last_error = str(e)
            log.error(f"Tenant {self.tenant_id}: crashed: {e}")
            await db.set_tenant_status(self.tenant_id, "error", last_error=str(e))

    async def stop(self):
        if self.bot and not self.bot.is_closed():
            await self.bot.close()
        self.status = "stopped"


class TenantManager:
    def __init__(self):
        self.runtimes = {}

    async def load_and_start_all(self):
        tenants = await db.list_tenants(status="active")
        log.info(f"Loading {len(tenants)} active tenant(s)...")

        for tenant in tenants:
            try:
                token = decrypt_token(tenant["encrypted_token"])
            except ValueError as e:
                log.error(f"Tenant {tenant['_id']}: {e} — skipping, marking errored.")
                await db.set_tenant_status(str(tenant["_id"]), "error", last_error=str(e))
                continue

            runtime = TenantRuntime(str(tenant["_id"]), tenant["owner_discord_id"], token)
            self.runtimes[runtime.tenant_id] = runtime
            runtime.task = asyncio.create_task(runtime.start())

        if not self.runtimes:
            log.info("No active tenants to run. Idling.")

    async def run_forever(self):
        await self.load_and_start_all()
        while True:
            await asyncio.sleep(60)


async def main():
    manager = TenantManager()
    await manager.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
