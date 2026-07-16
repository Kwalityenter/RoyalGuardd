"""
utils/embeds.py
----------------
Reusable embed factory functions so every part of the bot has a
consistent look and feel (matches config/settings.py branding).
"""

import discord
from config import settings


def base_embed(title: str = None, description: str = None, color: int = None) -> discord.Embed:
    embed = discord.Embed(
        title=title,
        description=description,
        color=color if color is not None else settings.EMBED_COLOR,
    )
    embed.set_footer(text=settings.FOOTER_TEXT, icon_url=settings.FOOTER_ICON)
    return embed


def success_embed(title: str, description: str = None) -> discord.Embed:
    return base_embed(title=title, description=description, color=settings.SUCCESS_COLOR)


def error_embed(title: str, description: str = None) -> discord.Embed:
    return base_embed(title=title, description=description, color=settings.ERROR_COLOR)


def warning_embed(title: str, description: str = None) -> discord.Embed:
    return base_embed(title=title, description=description, color=settings.WARNING_COLOR)


def info_embed(title: str, description: str = None) -> discord.Embed:
    return base_embed(title=title, description=description, color=settings.INFO_COLOR)


def verification_panel_embed() -> discord.Embed:
    embed = discord.Embed(
        title=settings.VERIFICATION_PANEL_TITLE,
        description=settings.VERIFICATION_PANEL_DESCRIPTION,
        color=settings.EMBED_COLOR,
    )
    embed.set_author(name=settings.BOT_NAME, icon_url=settings.AUTHOR_ICON)
    embed.set_thumbnail(url=settings.BOT_ICON_URL)
    embed.set_footer(text=settings.FOOTER_TEXT, icon_url=settings.FOOTER_ICON)
    return embed


def ticket_panel_embed() -> discord.Embed:
    embed = discord.Embed(
        title=settings.TICKET_PANEL_TITLE,
        description=settings.TICKET_PANEL_DESCRIPTION,
        color=settings.EMBED_COLOR,
    )
    embed.set_author(name=settings.BOT_NAME, icon_url=settings.AUTHOR_ICON)
    embed.set_footer(text=settings.FOOTER_TEXT, icon_url=settings.FOOTER_ICON)
    return embed