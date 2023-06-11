import asyncio
import calendar
import datetime
import logging
import re
from asyncio import CancelledError
from time import perf_counter
from typing import List

import discord
from discord import ApplicationContext, Option, Object
from discord.ext import commands
from discord.iterators import HistoryIterator
from discord.utils import time_snowflake

from .config import VERSION


class ProcessMessagesThenPublish:
    def __init__(self, context: ApplicationContext, origin: discord.TextChannel, destination: discord.Thread):
        self._destination = destination
        self._origin = origin
        self._context = context

        self._producer_completed = asyncio.Event()
        self._image_to_process_queue = asyncio.Queue(maxsize=20)

    async def _read_messages(self, messages: HistoryIterator):
        async for message in messages:
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
                    image_content_types = ("image/png", "image/jpg", "image/jpeg", "image/webp")
                    if attachement.content_type in image_content_types or (
                            attachement.filename and attachement.filename.endswith((".png", ".jpg", ".jpeg", ".webp"))):
                        image_file = await attachement.to_file()
                        attached_files.append(image_file)
                if len(current_urls) > 0 or len(attached_files) > 0:
                    arist_message = AristMessage(artist, source=message, when=message.created_at, urls=current_urls,
                                                 files=attached_files)
                    await self._image_to_process_queue.put(arist_message)
        self._producer_completed.set()

    async def _process_messages(self):
        do = True
        while do:
            artist_message: AristMessage = await self._image_to_process_queue.get()
            try:
                logging.info("Processing %s message link(s)=%s, attachement(s)=%s", artist_message.source.jump_url,
                             len(artist_message.urls),
                             len(artist_message.files))

                utc_time = calendar.timegm(artist_message.when.utctimetuple())
                posted_time = f"<t:{utc_time}:f>"
                separator = f"""``` Imported content from old channel ```
    {artist_message.author}
    Original date:{posted_time}
    """
                await self._destination.send(content=separator)

                urls = " ".join(artist_message.urls)
                if urls:
                    await self._destination.send(content=urls)

                for file in artist_message.files:
                    try:
                        await self._destination.send(file=file)
                    except:
                        await self._context.send(
                            f"Error while sending attachement {file.filename} for message {artist_message.source.jump_url}")
                        logging.exception("Error while sending attachement %s for message %s", file.filename,
                                          artist_message.source.jump_url)
            except CancelledError:
                do = False
            except:
                logging.exception("Error while processing message %s", artist_message.source.jump_url)
            finally:
                if do:
                    self._image_to_process_queue.task_done()

    async def _monitoring(self):
        do = True
        while do:
            max_size = self._image_to_process_queue.maxsize
            try:
                interval_refresh_in_sec = 30
                await self._context.send(
                    f"Queue size (update every {interval_refresh_in_sec}sec): {self._image_to_process_queue.qsize()}/{max_size}")
                await asyncio.sleep(interval_refresh_in_sec)
            except CancelledError:
                do = False

    async def _log_exceptions(self, awaitable):
        try:
            return await awaitable
        except asyncio.exceptions.CancelledError:
            logging.debug("coroutine was cancelled")
        except:
            logging.exception("Unhandled exception %s", awaitable)

    async def main(self, message_iter: HistoryIterator):

        start = perf_counter()
        coroutines = [
            asyncio.create_task(self._log_exceptions(self._read_messages(message_iter))),
            asyncio.create_task(self._log_exceptions(self._process_messages())),
            asyncio.create_task(self._log_exceptions(self._monitoring()))
        ]

        try:
            await self._producer_completed.wait()
            await self._image_to_process_queue.join()
        finally:
            for coroutine in coroutines:
                coroutine.cancel()

        end = perf_counter()
        await self._context.send(f"Finished in {end - start:.2f} seconds")


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

    @discord.Cog.listener()
    async def on_ready(self):
        logging.info("Start coroutines")

    @commands.slash_command(name="version", description="CCC Assistant version",
                            description_localizations={"fr": "Version de CCC Assistant"})
    async def version(self, ctx: ApplicationContext):
        await ctx.respond(content=f"Version: {VERSION}")

    @commands.slash_command(name="stats", description="Statistics about a channel",
                            name_localizations={"fr": "statistiques"},
                            description_localizations={"fr": "Statistiques sur un salon"})
    async def chan_stats(self, ctx: ApplicationContext, origin: Option(discord.TextChannel,
                                                                       name="origin",
                                                                       description="Choose your channel",
                                                                       name_localizations={"fr": "origine"},
                                                                       description_localizations={
                                                                           "fr": "Choisissez votre salon"},
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
                          after_message_id: Option(name="from-message", input_type=str,
                                                   name_localizations={"fr": "depuis-message"},
                                                   description="Message id to start from, fallback to the oldest message",
                                                   required=False, default=None, description_localizations={
                                  "fr": "Message id de départ, si non spécifié, depuis le premier message reçu"}),
                          before_message_id: Option(name="before-message", input_type=str,
                                                    name_localizations={"fr": "avant-message"},
                                                    description="Message id to stop at, if not specified, fallback to the most recent"
                                                                "message",
                                                    required=False, description_localizations={
                                  "fr": "Message id d'arrêt, si non spécifié, jusqu'au dernier message reçu"})):

        if origin.last_message_id is None:
            await ctx.respond(content="Origin channel has no messages, nothing to process")
            return

        if not before_message_id:
            before_message_id = origin.last_message_id
        before_message: discord.Message = await origin.fetch_message(int(before_message_id))

        after_message = None
        if after_message_id:
            after_message = await origin.fetch_message(int(after_message_id))
            content_message = f"Exporting images of {origin.mention} to {destination.mention} from message {before_message.jump_url} to " \
                              f"{after_message.jump_url}"
        else:
            content_message = f"Exporting images of {origin.mention} to {destination.mention} from message {before_message.jump_url} to the " \
                              f"first message"
        await ctx.respond(content_message)

        after_date = None
        before_date = None
        if before_message and after_message:
            after_date = Object(id=time_snowflake(after_message.created_at, high=False) - 1)
            before_date = Object(id=time_snowflake(before_message.created_at, high=True) + 1)
        elif before_message and not after_message:
            before_date = Object(id=time_snowflake(before_message.created_at, high=True) + 1)

        message_iter: HistoryIterator = origin.history(limit=None, after=after_date, before=before_date,
                                                       oldest_first=True)
        await ProcessMessagesThenPublish(ctx, origin, destination).main(message_iter)

    @discord.Cog.listener()
    async def on_error(self, event, *args, **kwargs):
        logging.error(f'event={event} args={args} kwargs={kwargs}')
