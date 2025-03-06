from __future__ import annotations

import typing

from cyberbot.api.room_api import RoomAPI
from cyberbot.api.room_plugin import PluginConfigParser, RoomPlugin

from ..util.git_hook_handler import GitHookHandler
from .formatting import GitLabFormatter

if typing.TYPE_CHECKING:
    from argparse import ArgumentParser


class GitLab(RoomPlugin):
    def __init__(self, api: RoomAPI):
        self._handler = GitHookHandler(
            api,
            git_variant="gitlab",
            formatter=GitLabFormatter(),
            info_url="https://docs.gitlab.com/ee/user/project/integrations/webhooks.html",
        )

    @classmethod
    def about(cls) -> str:
        return "GitLab notifications"

    def config_setup(self, parser: ArgumentParser) -> PluginConfigParser | None:
        return self._handler.config_setup(parser)

    async def init(self):
        await self._handler.init()


Module = GitLab
