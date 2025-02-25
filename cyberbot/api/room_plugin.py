from __future__ import annotations

import abc
from argparse import ArgumentParser, Namespace
from typing import Callable, Coroutine

from .room_api import RoomAPI

# coroutine for room configuration parsing
# async def handle_args(args: Namespace, answer_api: RoomAPI) -> None:
type PluginConfigParser = Callable[[Namespace, RoomAPI], Coroutine[None, None, None]]


class RoomPlugin(abc.ABC):
    """
    Base class for every bot plugin that's active in a room.
    This is instanced once per plugin per room.
    """

    @classmethod
    @abc.abstractmethod
    def about(cls) -> str:
        """
        returns a short description what this plugin is about.
        """
        raise NotImplementedError()

    def __init__(self, api: RoomAPI):
        pass

    async def setup(self) -> bool:
        """
        called before other rooms are loaded for setting up this plugin.
        returns if the module setup was successful.
        """
        return True

    @abc.abstractmethod
    async def init(self) -> None:
        """
        initialization of the plugin.
        called after all rooms were loaded and had setup() called.
        """
        raise NotImplementedError()

    def config_setup(self, parser: ArgumentParser) -> PluginConfigParser | None:
        """
        register configuration parsing of this plugin.
        """
        return None

    async def destroy(self) -> None:
        """
        deinitialization for a module, called when deactivated in a room.
        """
        pass
