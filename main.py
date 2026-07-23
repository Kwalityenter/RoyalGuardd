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
INTENTS.members = True
INTENTS.message_content = True
INTENTS.invites = True

COGS = [
    "cogs.adminlevels",
    "cogs.groupbinds",
    "cogs.rankbinds",
    "cogs.update",
    "cogs.verification",
    "cogs.tickets",
    "cogs.panels",
    "cogs.bgcheck",
    "cogs.moderation",
    "cogs.setrank",
    "cogs.rankrequest",
    "cogs.reactionroles",
    "cogs.invites",
]


class RoyalGuardBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=settings.COMMAND_PREFIX, intents=INTENTS, help_command=None)

    async def setup_hook(self):
        await db.ensure_indexes()
        log.info("MongoDB indexes ensured.")

        for cog in COGS:
            try:
                await self.load_extension(cog)
                log.info(f"Loaded cog: {cog}")
            except Exception as e:
                log.exception(f"Failed to load cog {cog}: {e}")

        from cogs.verification import VerificationView
        from cogs.tickets import ReportPanelView, OtherPanelView, CloseTicketView
        from cogs.rankrequest import RankRequestView

        self.add_view(VerificationView())
        self.add_view(ReportPanelView())
        self.add_view(OtherPanelView())
        self.add_view(CloseTicketView())

        pending_requests = await db.get_pending_rank_requests()
        for req in pending_requests:
            self.add_view(RankRequestView(req["_id"]))
        log.info(f"Re-registered {len(pending_requests)} pending rank request views.")

        # NOTE ON MULTI-SERVER SUPPORT:
        # DEV_GUILD_ID, if set, syncs slash commands instantly to ONLY that
        # one guild - useful while actively testing changes. Once you're
        # ready for the bot to work across multiple servers, remove
        # DEV_GUILD_ID from Railway's environment variables entirely; the
        # bot will then sync commands globally (available in every server
        # it's in), though global syncs can take up to an hour to propagate.
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
        log.info(f"Currently in {len(self.guilds)} server(s).")
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