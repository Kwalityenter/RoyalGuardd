"""tenant_manager.py — Runs one discord.py bot instance per tenant, concurrently,
reusing the same cogs as the main Royal Guard bot. Polls MongoDB every 30s for
newly registered, stopped, or removed tenants and starts/stops them live —
no redeploy needed when a new tenant is registered via /tenant register.
"""

import asyncio
import logging
import discord
from discord.ext import commands

from database.mongodb import db
from utils.token_crypto import decrypt_token
from config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] TenantManager: %(message)s")
log = logging.getLogger("tenant_manager")

POLL_INTERVAL_SECONDS = 30

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
        self.bot: commands.Bot | None = None
        self.task: asyncio.Task | None = None
        self.status = "starting"
        self.last_error: str | None = None

    async def start(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True

        self.bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

        async def setup_hook():
            for cog in TENANT_COGS:
                try:
                    await self.bot.load_extension(cog)
                except Exception as e:
                    log.error(f"Tenant {self.tenant_id}: failed to load {cog}: {e}")
            synced = await self.bot.tree.sync()
            log.info(f"Tenant {self.tenant_id}: synced {len(synced)} slash commands.")

        self.bot.setup_hook = setup_hook

        @self.bot.event
        async def on_ready():
            log.info(f"Tenant {self.tenant_id} ({self.bot.user}) is online in {len(self.bot.guilds)} server(s).")
            self.status = "active"
            await db.set_tenant_status(self.tenant_id, "active")
            await self._grant_owner_admin_on_fresh_guilds()
            await self.bot.change_presence(
                activity=discord.Streaming(
                    name="Made by Royal Guard Services \u00a9 All Rights Reserved",
                    url="https://discord.gg/UZ7raGDKhV",
                )
            )

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

    async def _grant_owner_admin_on_fresh_guilds(self):
        """If a guild this bot is in has no admin_levels records at all yet,
        grant the tenant owner full admin so they aren't locked out of their
        own bot. Never overrides an existing admin setup."""
        for guild in self.bot.guilds:
            if not await db.guild_has_any_admin(guild.id):
                await db.set_admin_level(guild.id, self.owner_discord_id, settings.OWNER_LEVEL)
                log.info(f"Tenant {self.tenant_id}: granted owner admin level in guild {guild.id} ({guild.name}).")

    async def stop(self):
        if self.bot and not self.bot.is_closed():
            await self.bot.close()
        self.status = "stopped"


class TenantManager:
    def __init__(self):
        self.runtimes: dict[str, TenantRuntime] = {}

    async def _start_tenant(self, tenant: dict):
        tenant_id = str(tenant["_id"])
        try:
            token = decrypt_token(tenant["encrypted_token"])
        except ValueError as e:
            log.error(f"Tenant {tenant_id}: {e} — skipping, marking errored.")
            await db.set_tenant_status(tenant_id, "error", last_error=str(e))
            return

        runtime = TenantRuntime(tenant_id, tenant["owner_discord_id"], token)
        self.runtimes[tenant_id] = runtime
        runtime.task = asyncio.create_task(runtime.start())
        log.info(f"Starting new tenant {tenant_id} ({tenant.get('bot_name') or 'unnamed'})...")

    async def _stop_tenant(self, tenant_id: str):
        runtime = self.runtimes.pop(tenant_id, None)
        if runtime:
            log.info(f"Stopping tenant {tenant_id}...")
            await runtime.stop()
            if runtime.task and not runtime.task.done():
                runtime.task.cancel()

    async def sync_once(self):
        """Compare DB state against currently-running tenants and reconcile.
        Called on startup and every POLL_INTERVAL_SECONDS afterward."""
        active_tenants = await db.list_tenants(status="active")
        active_ids = {str(t["_id"]) for t in active_tenants}
        running_ids = set(self.runtimes.keys())

        for tenant in active_tenants:
            tenant_id = str(tenant["_id"])
            if tenant_id not in running_ids:
                await self._start_tenant(tenant)

        for tenant_id in running_ids - active_ids:
            await self._stop_tenant(tenant_id)

    async def run_forever(self):
        log.info("Starting tenant sync loop...")
        await self.sync_once()
        while True:
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
            try:
                await self.sync_once()
            except Exception as e:
                log.error(f"Sync cycle failed: {e}")


async def main():
    manager = TenantManager()
    await manager.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
