import asyncio
import calendar
import datetime
import logging
import re
from time import perf_counter
from typing import List

import discord
from discord import ApplicationContext, Option
from discord.ext import commands

from .config import VERSION


class ExtractImages:
    def __init__(self, content: str):
        self.content: str = content

    def images_urls(self) -> List[str]:
        urls = re.findall(r"(https?://\S+)", self.content)
        without_queries = list(map(lambda url: url.split("?")[0], urls))
        return list(filter(lambda url: url.endswith((".png", ".jpg", ".jpeg", ".webp")), without_queries))


class AristMessage:
    def __init__(self, author: str, source: discord.Message, when: datetime.datetime, urls: List[str] = None,
                 attachments: List[discord.File] = None):
        self.author = author
        self.when = when
        self.urls = urls if urls else []
        self.attachments = attachments if attachments else []
        self.source = source


class MoveCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.send_to_forum_queue = asyncio.Queue(maxsize=50)
        self.producer_completed: asyncio.Event = asyncio.Event()

    async def send_to_forum(self):
        while True:
            artist_message = await self.send_to_forum_queue.get()
            logging.info(f'Send {artist_message.author} message to forum')
            self.send_to_forum_queue.task_done()

    @discord.Cog.listener()
    async def on_ready(self):
        logging.info("Start coroutines")

    @commands.slash_command(name="version", description="Hermes version", description_localizations={"fr": "Version d'Hermes"})
    async def version(self, ctx: ApplicationContext):
        await ctx.respond(content=f"Version actuelle: {VERSION}")

    @commands.slash_command(name="move-images", name_localizations={"fr": "déplacer-images"},
                            description="Export images from one channel to a forum thread",
                            description_localizations={"fr": "Exporte les images d'un salon vers un sujet du forum"})
    async def move_images(self, ctx: ApplicationContext, origin: Option(discord.TextChannel,
                                                                        name="origin",
                                                                        description="Choose your channel",
                                                                        name_localizations={"fr": "origine"},
                                                                        description_localizations={"fr": "Choisissez votre salon"},
                                                                        required=True),
                          destination: Option(discord.Thread,
                                              name="destination",
                                              description="Choose forum thread",
                                              name_localizations={"fr": "destination"},
                                              required=True,
                                              description_localizations={"fr": "Choisissez le fils d'un forum"}),
                          before_message: Option(name="before-message", input_type=str,
                                                 name_localizations={"fr": "depuis-le-message"},
                                                 description="Message id to start from, if not specified, since the last message",
                                                 required=False, description_localizations={
                                  "fr": "Message id de départ, si non spécifié, depuis le dernier message reçu"}),
                          until_message: Option(name="until-message", input_type=str,
                                                name_localizations={"fr": "jusqu-au-message"},
                                                description="Message id to stop at, all messages otherwise",
                                                required=False, default=None, description_localizations={
                                  "fr": "Message id d'arrêt, si non spécifié, remonter tout l'historique"})):
        start = perf_counter()
        if not before_message and origin.last_message_id is not None:
            before_message = origin.last_message_id
        else:
            await ctx.respond(content="Destination channel is empty, nothing to do")
            return

        b_message: discord.Message = await origin.fetch_message(before_message)
        before_date = b_message.created_at
        until_date = None
        if until_message:
            u_message = await origin.fetch_message(until_message)
            until_date = u_message.created_at
            await ctx.respond(content=f"Exporting from {origin} to {destination} from {b_message.jump_url} to {u_message.jump_url}")
        else:
            await ctx.respond(content=f"Exporting from {origin} to {destination} from {b_message.jump_url} to the beginning")

        histories = await origin.history(limit=None, before=before_date, after=until_date, oldest_first=True).flatten()
        to_process = len(histories)
        artist_messages: List[AristMessage] = []
        for message in histories:
            if message.type == discord.MessageType.default:
                nick = f"/{message.author.nick}" if not message.author.bot and isinstance(message.author, discord.Member) else ""
                artist = f"{message.author.name}#{message.author.discriminator}{nick}"
                current_urls = []
                current_attachements = []
                if message.content:
                    current_urls.extend(ExtractImages(message.content).images_urls())
                for attachement in message.attachments:
                    logging.info("Attachement: %s", attachement.content_type)
                    image_content_types = ("image/png", "image/jpg", "image/jpeg", "image/webp")
                    if attachement.content_type in image_content_types:
                        image_file = await attachement.to_file()
                        current_attachements.append(image_file)
                if len(current_urls) > 0 or len(current_attachements) > 0:
                    artist_messages.append(
                        AristMessage(artist, source=message, when=message.created_at, urls=current_urls, attachments=current_attachements))
        await ctx.send(
            f"Total messages processed: **{to_process}**. Valid messages **{len(artist_messages)}**.")

        for artist_message in artist_messages:
            await asyncio.sleep(0.5)
            utc_time = calendar.timegm(artist_message.when.utctimetuple())
            posted_time = f"<t:{utc_time}:f>"
            await ctx.send(f"Processing {artist_message.source.jump_url} message"),
            separator = f"``` Content from creator: {artist_message.author}``` Posted: {posted_time}"
            await destination.send(content=separator)

            urls = " ".join(url for url in artist_message.urls)
            if len(urls) > 0:
                await destination.send(content=urls)

            for attachement in artist_message.attachments:
                try:
                    await destination.send(file=attachement)
                except:
                    logging.exception(f"Error while sending attachement for message {artist_message.source.jump_url}")
                    await ctx.send(f"Error while sending attachement for message {artist_message.source.jump_url}")

        end = perf_counter()
        logging.info("Finished in %s seconds", end - start)
