import logging

import discord
from discord.ext import commands

from .config import VERSION


class MiscCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @discord.Cog.listener()
    async def on_ready(self):
        logging.info(f'Bot {VERSION} is ready : Logged as %s', self.bot.user.name)
