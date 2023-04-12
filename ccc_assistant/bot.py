import logging
import os

import discord
from discord import Intents

from ccc_assistant.cog import MoveCog
from ccc_assistant.misc import MiscCog

intents = Intents(messages=True, message_content=True, guilds=True)
logging.basicConfig(force=True,
                    format='[%(asctime)s.%(msecs)03d] %(levelname)s [%(thread)d] [%(process)d] [%(module)s.%(funcName)s] %(message)s',
                    datefmt='%d/%m/%Y %H:%M:%S',
                    level="INFO")
bot = discord.Bot()

bot.add_cog(MoveCog(bot))
bot.add_cog(MiscCog(bot))
bot.run(token=os.environ.get("CCC_BOT_TOKEN"))
