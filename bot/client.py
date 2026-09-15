from __future__ import annotations

import logging

import discord
from discord.ext import commands

from bot.cogs.builder import setup as setup_builder
from bot.config import Settings
from bot.views.builder_plus import BuilderPlusView

log = logging.getLogger("helzerx")


class HelzerXBot(commands.Bot):
    def __init__(self, settings: Settings):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix=commands.when_mentioned, intents=intents)
        self.settings = settings

    async def setup_hook(self) -> None:
        await setup_builder(self, self.settings)

        if self.settings.dev_guild_ids:
            for guild_id in self.settings.dev_guild_ids:
                guild = discord.Object(id=guild_id)
                self.tree.copy_global_to(guild=guild)
                await self.tree.sync(guild=guild)
                log.info("Synced commands to development guild %s", guild_id)
        else:
            await self.tree.sync()
            log.info("Synced global application commands")

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return

        # Prefix-free trigger plus arbitrary prefix support:
        # `container`, `!container`, `.container`, `hxcontainer`, etc.
        first = message.content.strip().split(maxsplit=1)[0].lower() if message.content.strip() else ""
        if first == "container" or first.endswith("container"):
            view = BuilderPlusView(
                owner_id=message.author.id,
                accent_color=self.settings.default_accent_color,
            )
            await message.channel.send(view=view)
            return

        await self.process_commands(message)

    async def on_ready(self) -> None:
        if self.user:
            log.info("Logged in as %s (%s)", self.user, self.user.id)
