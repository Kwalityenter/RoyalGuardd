"""cogs/bgcheck.py — !bgcheck @user, paginated Discord/Roblox/Regiment info embed.
Pagination via message reactions: ⬅️ (previous), ➡️ (next), 🏁 (jump to last page).
Bot requires 'Add Reactions' and 'Manage Messages' permissions.
"""

import asyncio
import discord
from discord.ext import commands
from datetime import datetime, timezone

from database.mongodb import db
from utils import embeds, roblox
from config import settings

PREV_EMOJI = "⬅️"
NEXT_EMOJI = "➡️"
LAST_EMOJI = "🏁"

DATE_FORMAT = "%a, %d %b %Y %H:%M:%S GMT"


def _build_alerts(member: discord.Member) -> str:
    alerts = []
    if (datetime.now(timezone.utc) - member.joined_at).days < 7:
        alerts.append("* [This user is new to our discord server.]")
    if not alerts:
        alerts.append("* [No alerts.]")
    return "\n".join(alerts)


class BGCheck(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _build_pages(self, ctx: commands.Context, member: discord.Member):
        verification = await db.get_verification(member.id)
        alerts_text = _build_alerts(member)

        # Page 1/3 — User Discord Account Details
        discord_embed = embeds.base_embed()
        discord_embed.set_author(name=str(member), icon_url=member.display_avatar.url)
        discord_embed.title = "User Discord Account Details"
        discord_embed.add_field(name="Joined Date", value=member.joined_at.strftime(DATE_FORMAT), inline=False)
        discord_embed.add_field(name="Registered Date", value=member.created_at.strftime(DATE_FORMAT), inline=False)
        roles = [r.mention for r in member.roles if r.name != "@everyone"]
        discord_embed.add_field(name=f"User Roles [{len(roles)}]", value=" ".join(roles) if roles else "None", inline=False)
        discord_embed.add_field(name="Alerts", value=alerts_text, inline=False)

        # Page 2/3 — User ROBLOX Account Details
        roblox_embed = embeds.base_embed()
        roblox_embed.set_author(name=str(member), icon_url=member.display_avatar.url)
        roblox_embed.title = "User ROBLOX Account Details"

        if verification:
            roblox_id = int(verification["roblox_id"])
            roblox_user = await roblox.get_user_by_id(roblox_id)
            avatar_url = await roblox.get_avatar_headshot_url(roblox_id)
            followers = await roblox.get_followers_count(roblox_id)
            following = await roblox.get_following_count(roblox_id)
            friends = await roblox.get_friends_count(roblox_id)
            groups = await roblox.get_user_groups(roblox_id)

            if avatar_url:
                roblox_embed.set_thumbnail(url=avatar_url)

            if roblox_user and roblox_user.get("created"):
                created_dt = datetime.fromisoformat(roblox_user["created"].replace("Z", "+00:00"))
                age_days = (datetime.now(timezone.utc) - created_dt).days
                roblox_embed.add_field(name="ROBLOX Account Age", value=f"{age_days} days", inline=False)

            description = (roblox_user.get("description") or "").strip() if roblox_user else ""
            roblox_embed.add_field(name="ROBLOX Account Description", value=description if description else "No description set.", inline=False)
            roblox_embed.add_field(name="ROBLOX Account Groups", value=str(len(groups)), inline=False)
            roblox_embed.add_field(name="ROBLOX Account Friends", value=str(friends), inline=False)
            roblox_embed.add_field(name="ROBLOX Account Followers", value=str(followers), inline=False)
            roblox_embed.add_field(name="ROBLOX Account Following", value=str(following), inline=False)
            roblox_embed.add_field(name="ROBLOX Account Gamepasses Owned", value="Not Programmed.", inline=False)
            roblox_embed.add_field(name="ROBLOX Account Badges Owned", value="Not Programmed.", inline=False)
        else:
            roblox_embed.add_field(name="ROBLOX Account Status", value="This user has not verified their Roblox account.", inline=False)

        roblox_embed.add_field(name="Alerts", value=alerts_text, inline=False)

        # Page 3/3 — User Regiment Details
        regiment_embed = embeds.base_embed()
        regiment_embed.set_author(name=str(member), icon_url=member.display_avatar.url)
        regiment_embed.title = "User Regiment Details"
        regiments = await db.get_user_regiments(ctx.guild.id, member.id) if hasattr(db, "get_user_regiments") else None
        if regiments:
            regiment_embed.add_field(name="Regiments", value="\n".join(regiments), inline=False)
        else:
            regiment_embed.add_field(name="\u200b", value="[This user is not in any regiments]", inline=False)
        regiment_embed.add_field(name="Alerts", value=alerts_text, inline=False)

        pages = [discord_embed, roblox_embed, regiment_embed]
        total = len(pages)
        for i, page in enumerate(pages, start=1):
            page.set_footer(text=f"Viewing Page {i}/{total}")

        return pages

    @commands.command(name="bgcheck")
    async def bgcheck(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author

        pages = await self._build_pages(ctx, member)
        current = 0
        message = await ctx.send(content=f"Hello {member.mention}", embed=pages[current])

        for emoji in (PREV_EMOJI, NEXT_EMOJI, LAST_EMOJI):
            try:
                await message.add_reaction(emoji)
            except discord.HTTPException:
                pass

        def check(reaction: discord.Reaction, user: discord.User):
            return (
                reaction.message.id == message.id
                and user.id == ctx.author.id
                and str(reaction.emoji) in (PREV_EMOJI, NEXT_EMOJI, LAST_EMOJI)
            )

        while True:
            try:
                reaction, user = await self.bot.wait_for("reaction_add", timeout=120.0, check=check)
            except asyncio.TimeoutError:
                try:
                    await message.clear_reactions()
                except discord.HTTPException:
                    pass
                break

            emoji = str(reaction.emoji)

            try:
                await message.remove_reaction(emoji, user)
            except discord.HTTPException:
                pass

            if emoji == NEXT_EMOJI and current < len(pages) - 1:
                current += 1
                await message.edit(embed=pages[current])
            elif emoji == PREV_EMOJI and current > 0:
                current -= 1
                await message.edit(embed=pages[current])
            elif emoji == LAST_EMOJI:
                current = len(pages) - 1
                await message.edit(embed=pages[current])


async def setup(bot: commands.Bot):
    await bot.add_cog(BGCheck(bot))
