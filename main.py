"""
main.py
-------
Royal Guard bot entrypoint. Loads environment variables, connects to
MongoDB, registers persistent views, loads all cogs, and syncs slash
commands.

Run locally:   python main.py
Run on Railway: this is your "worker" process (see Procfile)
"""

import os
import asyncio
import logging

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("RoyalGuard")

from config import settings
from database.mongodb import db

INTENTS = discord.Intents.default()
INTENTS.members = True          # Required for fetch_members / update all
INTENTS.message_content = True  # Required for prefix commands like !bgcheck

COGS = [
    "cogs.adminlevels",
    "cogs.groupbinds",
    "cogs.rankbinds",
    "cogs.update",
    "cogs.verification",
    "cogs.tickets",
    "cogs.panels",
    "cogs.bgcheck",
]


class RoyalGuardBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=settings.COMMAND_PREFIX, intents=INTENTS, help_command=None)

    async def setup_hook(self):
        # Ensure MongoDB indexes exist
        await db.ensure_indexes()
        log.info("MongoDB indexes ensured.")

        # Load cogs
        for cog in COGS:
            try:
                await self.load_extension(cog)
                log.info(f"Loaded cog: {cog}")
            except Exception as e:
                log.exception(f"Failed to load cog {cog}: {e}")

        # Register persistent views so buttons survive restarts
        from cogs.verification import VerificationView
        from cogs.tickets import ReportTicketView, OtherTicketView, CloseTicketView
        self.add_view(VerificationView())
        self.add_view(ReportTicketView())
        self.add_view(OtherTicketView())
        self.add_view(CloseTicketView())

        # Sync slash commands
        dev_guild_id = os.getenv("DEV_GUILD_ID")
        if dev_guild_id:
            guild = discord.Object(id=int(dev_guild_id))
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            log.info(f"Synced {len(synced)} slash commands to dev guild {dev_guild_id}.")
        else:
            synced = await self.tree.sync()
            log.info(f"Synced {len(synced)} global slash commands.")

    async def on_ready(self):
        log.info(f"Logged in as {self.user} (ID: {self.user.id})")
        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching, name="the Royal Guard")
        )


async def main():
    bot = RoyalGuardBot()
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN is not set in the environment (.env)")
    async with bot:
        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())