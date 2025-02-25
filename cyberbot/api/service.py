from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...bot import Bot


class Service(ABC):
    @abstractmethod
    async def setup(self, bot: Bot):
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
