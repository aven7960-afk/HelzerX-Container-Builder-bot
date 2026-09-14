from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from bot.config import Settings
from bot.views.builder_plus import BuilderPlusView


class BuilderCog(commands.Cog):
    """Entry point for the HelzerX Components V2 builder."""

    def __init__(self, bot: commands.Bot, settings: Settings):
        self.bot = bot
        self.settings = settings

    @app_commands.command(name="builder", description="Open the HelzerX Components V2 builder")
    async def builder(self, interaction: discord.Interaction) -> None:
        view = BuilderPlusView(
            owner_id=interaction.user.id,
            accent_color=self.settings.default_accent_color,
        )
        await interaction.response.send_message(view=view)


async def setup(bot: commands.Bot, settings: Settings) -> None:
    await bot.add_cog(BuilderCog(bot, settings))
