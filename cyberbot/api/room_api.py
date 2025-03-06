from __future__ import annotations

import asyncio
import io
import logging
from typing import TYPE_CHECKING, Awaitable, Callable

from nio.events.room_events import Event

from .kvstore import KVStore
from .text_handler import TextHandler
from .types import MessageText

if TYPE_CHECKING:
    from ..room_module import RoomModule
    from .bot import Bot
    from .room import Room
    from .service import Service


class RoomAPI:
    """
    the api available to a room plugin, you get one instance for the current room.
    """

    def __init__(self, bot: Bot, room: Room, plugin_name: str) -> None:
        self.log = logging.getLogger(f"{__name__}.{room.room_id}.{plugin_name}")

        self._bot = bot
        self._room = room
        self._kv = KVStore(bot.db, plugin_name, room.room_id)

        self._tasks: set[asyncio.Task] = set()

        # registered in the interaction room
        self._text_handlers: set[TextHandler] = set()

    async def destroy(self) -> None:
        # stop all running tasks
        while True:
            try:
                task = self._tasks.pop()
            except KeyError:
                break

            if not task.done():
                task.cancel()
            await task
            try:
                task.result()
            except Exception:
                self.log.exception("failed to cancel room task")

    def add_text_handler(self, handler: TextHandler) -> None:
        """
        register a text parser that processes messages in the interaction chat room.
        """
        self._text_handlers.add(handler)

    def remove_text_handler(self, handler: TextHandler) -> bool:
        """
        deregister a text parser.
        returns if it was removed successfully.
        """
        try:
            self._text_handlers.remove(handler)
            return True
        except KeyError:
            return False

    async def on_text_message(self, event: MessageText):
        # filter message edits
        # they need a cooler API.
        content = event.source["content"]
        if content.get("m.new_content"):
            if relates_to := content.get("m.relates_to"):
                if relates_to["rel_type"] == "m.replace":
                    return

        for handler in self._text_handlers:
            await handler.process(event)

    # helpers
    @property
    def botname(self) -> str:
        """
        get the bot's name as specified in the config file
        """
        return self._bot.botname

    def format_user(self, user_id: str, display_name: str | None = None) -> str:
        """
        Format a hightlight to reference a user in a room.
        This message needs to be sent as html.
        """
        if display_name is None:
            display_name = self._room.user_name(user_id)

        return f'<a href="https://matrix.to/#/{user_id}">{display_name}</a>'

    @staticmethod
    def format_code(text: str, lang=None) -> str:
        """
        format as code block, send this with `send_html`.
        """
        cls = f' class="language-{lang}"' if lang else ""
        return f'<pre><code{cls}>{text}</code></pre>\n'

    def get_sender_display_name(self, event: Event):
        """
        from a room event, figure out the matrix id of the sender
        """
        return self._room.user_name(event.sender)

    # database
    @property
    def storage(self) -> KVStore:
        """
        interact with the bot's persistent key value store
        """
        return self._kv

    # room message sending
    async def send_text(self, txt, notice=False):
        return await self._room.send_text(txt, notice)

    async def send_notice(self, txt):
        return await self._room.send_text(txt, notice=True)

    async def send_html(self, html_text: str, text: str = "", notice=False):
        return await self._room.send_html(html_text, text, notice)

    # private chat
    async def send_text_to_user(
        self,
        user_id: str,
        text: str | None = None,
        html: str | None = None,
        notice: bool = False,
    ):

        room = await self._bot.rooms.get_private_room_with_user(user_id)

        await room.send_text(text=text, html=html, notice=notice)

    # room management and information
    async def invite(self, user_id: str):
        return await self._room.invite(user_id)

    async def get_user_power_level(self, user_id: str) -> int:
        """
        get the permission power level of a user in this room.
        """
        return await self._room.get_user_power_level(user_id)

    async def set_room_topic(self, description: str):
        return await self._room.set_topic(description)

    async def send_image(self, handle: io.BytesIO, filename: str):
        return await self._room.send_image(handle, filename)

    async def is_dm_room(self, user_id: str) -> bool:
        return await self._room.is_dm_room(user_id)

    async def is_config_room(self) -> bool:
        """
        check if the room we're currently in allows to configure the bot.
        """
        return await self._room.is_config_room()

    async def get_config_target_rooms(self) -> dict[str, Room]:
        ret = dict()
        for room_id in await self._room.config_target_rooms():
            room = self._bot.rooms.get(room_id)
            if room:
                ret[room_id] = room
        return ret

    def get_room(self, room_id: str) -> Room | None:
        """
        fetch any known room
        """
        return self._bot.rooms.get(room_id)

    async def create_room(self, creator: str,
                          name: str,
                          topic: str | None = None,
                          preset: str | None = None) -> Room:
        """
        create a new room.
        type_preset: "public", "private"
        """
        return await self._bot.rooms.create_room(
            creator=creator,
            name=name,
            topic=topic,
            preset=preset,
        )

    # service management
    def get_service(self, service_name: str) -> Service:
        return self._bot.get_service(service_name)

    # plugin management
    async def get_available_plugins(self) -> dict[str, RoomModule]:
        return self._bot.get_plugins()

    # task management
    async def start_repeating_task(
        self,
        func: Callable[[], Awaitable[bool]],
        interval: float = 10,
        delay: float = 0,
        cleanup: Callable[[], Awaitable[None]] | None = None,
    ):
        """
        func: is run every interval seconds with a beginning delay of delay seconds and
        returns true if there should be another loop.
        cleanup: is called when after we leave the loop of calling func.
        """

        async def repeat_func():
            try:
                await asyncio.sleep(delay)
                while True:
                    ret = await func()
                    if not ret:
                        break
                    await asyncio.sleep(interval)

            except asyncio.CancelledError:
                if cleanup:
                    await cleanup()
                self._tasks.remove(t)
                raise

        t = asyncio.create_task(repeat_func())
        if cleanup:
            t.add_done_callback(lambda fut: cleanup())
        self._tasks.add(t)
        return t

    async def start_task(self, fun):
        task = asyncio.create_task(fun)
        task.add_done_callback(lambda fut: self._tasks.remove(fut))
        self._tasks.add(task)
        return task
