from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .api.room_api import RoomAPI
from .api.room_plugin import RoomPlugin

if TYPE_CHECKING:
    from .bot import Bot
    from .room import Room, RoomMessageText


class RoomModule:
    def __init__(self, bot: Bot, room: Room, pluginname: str):
        self._log = logging.getLogger(f"{__name__}:{room.room_id}:{pluginname}")

        self.pluginname = pluginname

        self._api = RoomAPI(bot, room, pluginname)
        self._plugin: RoomPlugin | None = None
        self._plugin_cls: type[RoomPlugin] = bot.get_plugins()[pluginname]

    async def load(self) -> bool:
        try:
            self._log.debug('creating module instance...')
            # instance the module for the room, it has to define a "Module(Plugin)" class.
            self._plugin = self._plugin_cls(self._api)  # initialize the plugin's Module

            self._log.debug("setting up module...")
            return await self._plugin.setup()

        except Exception:
            self._log.exception(f"failed to setup plugin {self.pluginname}")
            return False

        return False

    async def init(self) -> None:
        if self._plugin is None:
            raise Exception("called init on RoomModule without loaded RoomPlugin")
        try:
            self._log.debug("initializing module...")
            await self._plugin.init()

        except Exception:
            self._log.exception(f"failed to init plugin {self.pluginname}")

    async def on_text_message(self, event: RoomMessageText) -> None:
        # directly pass to plugin api
        await self._api.on_text_message(event)

    async def destroy(self):
        if self._plugin:
            await self._plugin.destroy()
        await self._api.destroy()
        self._plugin = None

    @property
    def plugin(self) -> RoomPlugin:
        if not self._plugin:
            raise ValueError("module plugin not initialized")
        return self._plugin

    async def about(self) -> str:
        return self._plugin_cls.about()
