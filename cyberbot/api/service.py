from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...bot import Bot


class Service(ABC):
    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    @abstractmethod
    async def setup(self):
        """
        initialization of this service module
        """
        pass

    @abstractmethod
    async def start(self):
        """
        activate the service module's service
        """
        pass
