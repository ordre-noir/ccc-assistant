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
                 files: List[discord.File] = None):
        self.author = author
        self.when = when
        self.urls = urls if urls else []
        self.files = files if files else []
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

    @commands.slash_command(name="version", description="CCC Assistant version", description_localizations={"fr": "Version de CCC Assistant"})
    async def version(self, ctx: ApplicationContext):
        await ctx.respond(content=f"Version: {VERSION}")

    @commands.slash_command(name="stats", description="Statistics about a channel", name_localizations={"fr": "statistiques"},
                            description_localizations={"fr": "Statistiques sur un salon"})
    async def chan_stats(self, ctx: ApplicationContext, origin: Option(discord.TextChannel,
                                                                       name="origin",
                                                                       description="Choose your channel",
                                                                       name_localizations={"fr": "origine"},
                                                                       description_localizations={"fr": "Choisissez votre salon"},
                                                                       required=True)):
        await ctx.respond(content="Calculating...", ephemeral=True)

        async with ctx.typing():
            histories = await origin.history(limit=None).flatten()
            current_urls = []
            attachements = []
            for message in histories:
                if message.content:
                    current_urls.extend(ExtractImages(message.content).images_urls())
                for attachement in message.attachments:
                    image_content_types = ("image/png", "image/jpg", "image/jpeg", "image/webp")
                    if attachement.content_type in image_content_types:
                        attachements.append(attachement)

        await ctx.send(
            content=f"Total messages: {len(histories)}\n:frame_photo: Images: {len(current_urls)}\n:link: Attachements: {len(attachements)}")

    @commands.slash_command(name="copy-images", name_localizations={"fr": "copier-images"},
                            description="Export images from one channel to a forum thread",
                            description_localizations={"fr": "Exporte les images d'un salon vers un sujet du forum"})
    async def move_images(self, ctx: ApplicationContext,
                          origin: Option(discord.TextChannel,
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
                          before_message_id: Option(name="before-message", input_type=str,
                                                    name_localizations={"fr": "depuis-le-message"},
                                                    description="Message id to start from, if not specified, fallback to the most recent "
                                                                "message",
                                                    required=False, description_localizations={
                                  "fr": "Message id de départ, si non spécifié, depuis le dernier message reçu"}),
                          until_message_id: Option(name="until-message", input_type=str,
                                                   name_localizations={"fr": "jusqu-au-message"},
                                                   description="Message id to stop at, fallback to the oldest message",
                                                   required=False, default=None, description_localizations={
                                  "fr": "Message id d'arrêt, si non spécifié, remonter tout l'historique"})):
        start = perf_counter()
        if origin.last_message_id is None:
            await ctx.respond(content="Origin channel has no messages, nothing to process")
            return

        if not before_message_id:
            before_message_id = origin.last_message_id

        before_message: discord.Message = await origin.fetch_message(before_message_id)
        before_date = before_message.created_at
        until_date = None
        if until_message_id:
            until_message = await origin.fetch_message(until_message_id)
            until_date = until_message.created_at
            content_message = f"Exporting images of {origin.mention} to {destination.mention} from message {before_message.jump_url} to " \
                              f"{until_message.jump_url}"
        else:
            content_message = f"Exporting images of {origin.mention} to {destination.mention} from message {before_message.jump_url} to the " \
                              f"first message"
        await ctx.respond(content_message)

        histories = await origin.history(limit=None, before=before_date, after=until_date, oldest_first=True).flatten()
        to_process = len(histories)
        artist_messages: List[AristMessage] = []
        for message in histories:
            if message.type == discord.MessageType.default and not message.author.bot:
                if isinstance(message.author, discord.Member):
                    nick = f"/{message.author.nick}"
                else:
                    nick = ""
                artist = f"{message.author.name}#{message.author.discriminator}{nick}"
                current_urls = []
                attached_files = []
                if message.content:
                    current_urls.extend(ExtractImages(message.content).images_urls())
                for attachement in message.attachments:
                    logging.info("Attachement: %s", attachement.content_type)
                    image_content_types = ("image/png", "image/jpg", "image/jpeg", "image/webp")
                    if attachement.content_type in image_content_types:
                        image_file = await attachement.to_file()
                        attached_files.append(image_file)
                if len(current_urls) > 0 or len(attached_files) > 0:
                    artist_messages.append(
                        AristMessage(artist, source=message, when=message.created_at, urls=current_urls, files=attached_files))
        await ctx.send(
            f"Total messages processed: **{to_process}**. Valid messages (with images) **{len(artist_messages)}**.")

        for artist_message in artist_messages:
            await asyncio.sleep(0.5)
            await ctx.send(
                f"Processing {artist_message.source.jump_url} message. "
                f"link(s)={len(artist_message.urls)}, "
                f"attachement(s)={len(artist_message.files)} "),

            utc_time = calendar.timegm(artist_message.when.utctimetuple())
            posted_time = f"<t:{utc_time}:f>"
            separator = f"""``` Imported content from old channel ```
{artist_message.author}
Original date:{posted_time}
"""
            await destination.send(content=separator)

            urls = " ".join(url for url in artist_message.urls)
            for url in urls:
                await destination.send(content=url)

            for file in artist_message.files:
                try:
                    await destination.send(file=file)
                except:
                    await ctx.send(f"Error while sending attachement {file.filename}for message {artist_message.source.jump_url}")

        end = perf_counter()
        logging.info("Finished in %s seconds", end - start)
